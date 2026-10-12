from datetime import time, timedelta

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from progress.models import RegistroEntrenamiento
from routines.models import DiaRutina, Rutina
from users.models import Proceso, Usuario

from .models import Habitos, RegistroHabito

HOY = timezone.localdate


class CumplimientoGlobalTest(APITestCase):
    def setUp(self):
        self.usuario = Usuario.objects.create_user(username='c@x.co', email='c@x.co', nombre='C',
                                                   password='clave-segura-123')
        Usuario.objects.filter(pk=self.usuario.pk).update(date_joined=timezone.now() - timedelta(days=10))
        self.usuario.refresh_from_db()
        self.client.force_authenticate(self.usuario)
        Habitos.objects.create(usuario=self.usuario, agua_ml=2000, vaso_ml=500, hora_dormir=time(22, 0))

    def pedir(self, desde=None, hasta=None):
        params = {k: v.isoformat() for k, v in (('desde', desde), ('hasta', hasta)) if v}
        r = self.client.get(reverse('cumplimiento-global'), params)
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        return r.data

    def agua(self, vasos, fecha=None):
        for _ in range(vasos):
            RegistroHabito.objects.create(usuario=self.usuario, tipo='agua', fecha=fecha or HOY(), ml=500)

    def test_antes_del_proceso_solo_cuentan_agua_y_dormir(self):
        Proceso.objects.create(usuario=self.usuario, objetivo='ganar_musculo',
                               fecha_inicio=HOY() + timedelta(days=3))
        self.agua(4)
        dia = self.pedir()['dias'][0]
        self.assertFalse(dia['en_proceso'])
        self.assertEqual([b['id'] for b in dia['bloques']], ['agua', 'dormir'])
        # Agua completa (peso 15) y sin acostarse aún (peso 10): 15/25.
        self.assertEqual(dia['porcentaje'], 60)

    def test_cumpliendo_agua_y_dormir_antes_del_proceso_es_cien(self):
        self.agua(4)
        RegistroHabito.objects.create(usuario=self.usuario, tipo='dormir', fecha=HOY())
        self.assertEqual(self.pedir()['dias'][0]['porcentaje'], 100)

    def test_en_proceso_suma_el_entreno_si_tocaba(self):
        Proceso.objects.create(usuario=self.usuario, objetivo='ganar_musculo', incluye_entrenamiento=True,
                               fecha_inicio=HOY() - timedelta(days=2))
        rutina = Rutina.objects.create(usuario=self.usuario, nombre='R')
        DiaRutina.objects.create(rutina=rutina, dia_semana=HOY().isoweekday())
        self.agua(4)
        RegistroHabito.objects.create(usuario=self.usuario, tipo='dormir', fecha=HOY())
        dia = self.pedir()['dias'][0]
        self.assertTrue(dia['en_proceso'])
        self.assertEqual({b['id'] for b in dia['bloques']}, {'agua', 'dormir', 'entreno'})
        # Sin entrenar: (15 + 10 + 0) / 45.
        self.assertEqual(dia['porcentaje'], 56)
        self.assertIn('No entrenaste', next(b for b in dia['bloques'] if b['id'] == 'entreno')['faltas'])
        RegistroEntrenamiento.objects.create(usuario=self.usuario)
        self.assertEqual(self.pedir()['dias'][0]['porcentaje'], 100)

    def test_semana_con_promedio_por_bloque_y_racha(self):
        for atras in (3, 2, 1):
            self.agua(4, HOY() - timedelta(days=atras))
            RegistroHabito.objects.create(usuario=self.usuario, tipo='dormir', fecha=HOY() - timedelta(days=atras))
        self.agua(1, HOY() - timedelta(days=4))
        datos = self.pedir(HOY() - timedelta(days=4), HOY())
        self.assertEqual(len(datos['dias']), 5)
        self.assertEqual(datos['racha_actual'], 3)   # hoy, sin terminar, no corta la racha
        self.assertEqual(datos['mejor_racha'], 3)
        agua = next(b for b in datos['bloques'] if b['id'] == 'agua')
        self.assertEqual(agua['porcentaje'], round((25 + 100 * 3 + 0) / 5))

    def test_no_pasa_de_un_trimestre_ni_de_hoy(self):
        r = self.client.get(reverse('cumplimiento-global'),
                            {'desde': (HOY() - timedelta(days=200)).isoformat(), 'hasta': HOY().isoformat()})
        self.assertEqual(r.status_code, status.HTTP_200_OK)  # se recorta a cuando se registró
        self.assertLessEqual(len(r.data['dias']), 11)
        futuro = self.pedir(HOY() + timedelta(days=2), HOY() + timedelta(days=5))
        self.assertEqual(futuro['dias'], [])


class CumplimientoConComidasTest(APITestCase):
    """Con plan de comida, las comidas son el bloque más pesado del día."""

    def setUp(self):
        from nutricion.models import Minuta, PreferenciasComida
        from nutricion.tests import datos_minuta
        self.usuario = Usuario.objects.create_user(username='m@x.co', email='m@x.co', nombre='M',
                                                   password='clave-segura-123')
        Usuario.objects.filter(pk=self.usuario.pk).update(date_joined=timezone.now() - timedelta(days=3))
        self.usuario.refresh_from_db()
        self.client.force_authenticate(self.usuario)
        Proceso.objects.create(usuario=self.usuario, objetivo='ganar_musculo', fase='volumen',
                               fecha_inicio=HOY() - timedelta(days=2), fecha_fin_plan=HOY() + timedelta(days=60))
        PreferenciasComida.objects.create(usuario=self.usuario)
        datos = datos_minuta()
        r = self.client.post(reverse('minutas'), {
            'origen': 'nutricionista', 'porciones': datos['porciones'], 'kcal': datos['kcal'],
            'menu_ejemplo': datos['menu_ejemplo']}, format='json')
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        Minuta.objects.update(fecha_creacion=timezone.now() - timedelta(days=2))

    def test_comida_sin_contar_cuenta_cero_y_se_avisa(self):
        ayer = HOY() - timedelta(days=1)
        r = self.client.get(reverse('cumplimiento-global'), {'desde': ayer.isoformat(), 'hasta': ayer.isoformat()})
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        dia = r.data['dias'][0]
        comidas = next(b for b in dia['bloques'] if b['id'] == 'comidas')
        self.assertEqual(comidas['porcentaje'], 0)
        self.assertTrue(any('sin contar' in f for f in comidas['faltas']))

    def test_hoy_ya_trae_las_comidas_del_plan(self):
        dia = self.client.get(reverse('cumplimiento-global')).data['dias'][0]
        comidas = next(b for b in dia['bloques'] if b['id'] == 'comidas')
        self.assertEqual(comidas['peso'], 40)
        self.assertEqual(comidas['porcentaje'], 0)
