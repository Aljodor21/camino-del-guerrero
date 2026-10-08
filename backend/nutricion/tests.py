from datetime import timedelta
from unittest import mock

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from agenda.models import Recordatorio
from users.models import Proceso, Usuario

from .models import Suplemento


class ModulosDelProcesoTest(APITestCase):
    """Alimentación y entrenamiento son independientes: uno no exige el otro."""

    def setUp(self):
        self.usuario = Usuario.objects.create_user(username='n@x.co', email='n@x.co', nombre='N',
                                                   password='clave-segura-123')
        self.client.force_authenticate(self.usuario)

    @mock.patch('nutricion.views.AIService')
    def test_rutina_rechazada_si_el_proceso_es_solo_alimentacion(self, ai):
        Proceso.objects.create(usuario=self.usuario, objetivo='ganar_musculo')
        r = self.client.post(reverse('generar-rutina'))
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        ai.assert_not_called()

    @mock.patch('nutricion.views.AIService')
    def test_plan_rechazado_si_el_proceso_es_solo_entrenamiento(self, ai):
        Proceso.objects.create(usuario=self.usuario, objetivo='ganar_musculo',
                               incluye_alimentacion=False, incluye_entrenamiento=True)
        r = self.client.post(reverse('mi-plan-nutricional'))
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        ai.assert_not_called()

    @mock.patch('nutricion.views.AIService')
    def test_plan_de_solo_alimentacion_se_genera_sin_rutina(self, ai):
        proceso = Proceso.objects.create(usuario=self.usuario, objetivo='ganar_musculo', fase='volumen')
        ai.return_value.generar_plan_nutricional.return_value = {'dias': [
            {'dia_semana': 1, 'desayuno': 'a', 'almuerzo': 'b', 'cena': 'c', 'snacks': '', 'calorias_aprox': 2700}]}
        r = self.client.post(reverse('mi-plan-nutricional'))
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        ai.return_value.generar_plan_nutricional.assert_called_once_with(self.usuario, proceso)


class SuplementoTest(APITestCase):
    """La proteína se asume a 3 meses hasta que el usuario lo confirme, y la agenda sugiere qué hacer."""

    def setUp(self):
        self.usuario = Usuario.objects.create_user(username='s@x.co', email='s@x.co', nombre='S',
                                                   password='clave-segura-123')
        self.client.force_authenticate(self.usuario)
        self.hoy = timezone.localdate()
        self.proceso = Proceso.objects.create(usuario=self.usuario, objetivo='ganar_musculo', fase='volumen',
                                              fecha_fin_plan=self.hoy + timedelta(days=60))

    def crear(self, **datos):
        r = self.client.post(reverse('suplementos'), datos, format='json')
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        return r.data

    def sugeridos(self):
        return {r.motivo: r for r in Recordatorio.objects.filter(usuario=self.usuario, completado_en__isnull=True)}

    def accion(self, sup, accion, **datos):
        return self.client.post(reverse('suplemento-accion', args=[sup['id'], accion]), datos, format='json')

    def test_proteina_asumida_pide_confirmar_y_revisar_al_final(self):
        sup = self.crear(tipo='proteina', duracion_dias=90, porciones_envase=30, porciones_dia=1)
        self.assertEqual(sup['fin_estimado'], (self.hoy + timedelta(days=89)).isoformat())
        self.assertEqual(sup['se_acaba'], (self.hoy + timedelta(days=29)).isoformat())

        s = self.sugeridos()
        self.assertEqual(set(s), {'confirmar', 'reponer', 'revisar'})
        self.assertEqual(s['confirmar'].titulo, 'Confirma si la proteína va 3 meses')
        self.assertEqual(s['revisar'].fecha, self.hoy + timedelta(days=89))
        self.assertEqual(s['revisar'].proceso, self.proceso)

        url = reverse('suplemento-detail', args=[sup['id']])
        self.client.patch(url, {'duracion_confirmada': True}, format='json')
        s = self.sugeridos()
        self.assertNotIn('confirmar', s)
        self.assertTrue(Recordatorio.objects.filter(motivo='confirmar', completado_en__isnull=False).exists())

        # Siguió con la misma un mes más: el aviso de revisión se corre.
        r = self.accion(sup, 'continuar', dias=30)
        self.assertEqual(r.data['duracion_dias'], 120)
        self.assertEqual(self.sugeridos()['revisar'].fecha, self.hoy + timedelta(days=119))

    def test_hipercalorico_va_hasta_el_fin_del_plan(self):
        sup = self.crear(tipo='hipercalorico', porciones_envase=20, porciones_dia=2, duracion_confirmada=True)
        self.assertEqual(sup['fin_estimado'], self.proceso.fecha_fin_plan.isoformat())
        self.assertEqual(sup['dias_envase'], 10)
        self.assertEqual(set(self.sugeridos()), {'reponer'})

        # Si el envase alcanza hasta el final del plan, no hay nada que reponer.
        self.client.patch(reverse('proceso-detail', args=[self.proceso.id]),
                          {'fecha_fin_plan': (self.hoy + timedelta(days=5)).isoformat()}, format='json')
        self.assertEqual(self.sugeridos(), {})

    def test_abrir_envase_resuelve_y_reprograma(self):
        sup = self.crear(tipo='proteina', duracion_dias=90, duracion_confirmada=True, porciones_envase=30)
        Suplemento.objects.filter(pk=sup['id']).update(envase_desde=self.hoy - timedelta(days=28))
        self.accion(sup, 'abrir-envase')
        self.assertEqual(self.sugeridos()['reponer'].fecha, self.hoy + timedelta(days=29))
        self.assertEqual(Recordatorio.objects.filter(motivo='reponer', completado_en__isnull=False).count(), 1)

    def test_cambiar_de_proteina(self):
        sup = self.crear(tipo='proteina', nombre='Whey A', duracion_dias=90, duracion_confirmada=True)
        r = self.accion(sup, 'reemplazar', nombre='Whey B', duracion_dias=60, duracion_confirmada=True)
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        self.assertEqual(r.data['tipo'], 'proteina')

        lista = self.client.get(reverse('suplementos')).data
        self.assertEqual([(x['nombre'], x['fecha_fin']) for x in lista],
                         [('Whey B', None), ('Whey A', self.hoy.isoformat())])
        self.assertEqual([x.titulo for x in self.sugeridos().values()], ['Terminan los 2 meses de Whey B: ¿qué sigue?'])
        self.assertEqual(self.accion(sup, 'terminar').status_code, status.HTTP_400_BAD_REQUEST)

    def test_los_sugeridos_se_resuelven_desde_el_suplemento(self):
        self.crear(tipo='proteina', duracion_dias=90)
        url = reverse('recordatorio-detail', args=[self.sugeridos()['revisar'].id])
        for cambio in ({'titulo': 'Otro'}, {'completado': True}):
            self.assertEqual(self.client.patch(url, cambio, format='json').status_code,
                             status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.client.delete(url).status_code, status.HTTP_400_BAD_REQUEST)

    def test_se_cierran_con_el_proceso_y_vuelven_si_se_cancela_el_nuevo(self):
        self.crear(tipo='proteina', duracion_dias=90, duracion_confirmada=True)
        r = self.client.post(reverse('procesos'), {
            'objetivo': 'ganar_musculo', 'fase': 'definicion', 'incluye_alimentacion': True,
            'fecha_inicio': (self.hoy + timedelta(days=10)).isoformat()}, format='json')
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        self.assertEqual(Suplemento.objects.get().fecha_fin, self.hoy + timedelta(days=9))
        self.assertEqual(self.sugeridos(), {})

        nuevo = self.client.post(reverse('suplementos'), {'tipo': 'hipercalorico', 'proceso': r.data['id']},
                                 format='json').data
        self.assertEqual((nuevo['proceso'], nuevo['fecha_inicio']), (r.data['id'], r.data['fecha_inicio']))

        self.client.delete(reverse('proceso-detail', args=[r.data['id']]))
        self.assertIsNone(Suplemento.objects.get().fecha_fin)
        self.assertEqual(set(self.sugeridos()), {'revisar'})

    def test_solo_los_propios(self):
        sup = self.crear(tipo='creatina')
        otro = Usuario.objects.create_user(username='o@x.co', email='o@x.co', nombre='O', password='clave-segura-123')
        self.client.force_authenticate(otro)
        self.assertEqual(self.accion(sup, 'terminar').status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(self.client.post(reverse('suplementos'), {'tipo': 'proteina'}, format='json').status_code,
                         status.HTTP_400_BAD_REQUEST)
