from datetime import time, timedelta

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from progress.models import RegistroEntrenamiento
from users.models import Usuario

from . import logros
from .models import Habitos, HitoVisto, RegistroHabito

HOY = timezone.localdate


class LogrosBase(APITestCase):
    def setUp(self):
        self.usuario = Usuario.objects.create_user(username='l@x.co', email='l@x.co', nombre='L',
                                                   password='clave-segura-123')
        Usuario.objects.filter(pk=self.usuario.pk).update(date_joined=timezone.now() - timedelta(days=30))
        self.usuario.refresh_from_db()
        self.client.force_authenticate(self.usuario)
        Habitos.objects.create(usuario=self.usuario, agua_ml=2000, vaso_ml=500, hora_dormir=time(22, 0))

    def dia_bueno(self, fecha):
        for _ in range(4):
            RegistroHabito.objects.create(usuario=self.usuario, tipo='agua', fecha=fecha, ml=500)
        RegistroHabito.objects.create(usuario=self.usuario, tipo='dormir', fecha=fecha)

    def lunes_hace(self, semanas):
        return logros.lunes_de(HOY()) - timedelta(days=7 * semanas)


class RachaTest(LogrosBase):
    def test_un_comodin_por_semana_salva_un_mal_dia_pero_no_dos(self):
        lunes = self.lunes_hace(2)
        for i in (0, 1, 3):                  # lun, mar y jue bien; el miércoles se salva
            self.dia_bueno(lunes + timedelta(days=i))
        # el viernes también falla: ya se usó el comodín de esa semana, la racha se corta
        for i in (5, 6):
            self.dia_bueno(lunes + timedelta(days=i))
        r = self.client.get(reverse('logros')).data['racha']
        self.assertEqual(r['mejor'], 3)
        # El miércoles lo salva el comodín de esa semana; el lunes siguiente (otra semana) también,
        # y el martes ya no queda comodín: la racha se corta.
        self.assertEqual(r['dias_salvados'], [lunes + timedelta(days=2), lunes + timedelta(days=7)])
        self.assertEqual(r['actual'], 0)
        self.assertTrue(r['comodin_disponible'])    # la semana de hoy aún no lo ha gastado

    def test_hoy_no_corta_la_racha_mientras_no_se_acabe(self):
        for atras in (3, 2, 1):
            self.dia_bueno(HOY() - timedelta(days=atras))
        r = self.client.get(reverse('logros')).data['racha']
        self.assertEqual(r['actual'], 3)
        self.assertEqual(r['mejor'], 3)

    def test_el_hito_de_la_racha_se_logra_con_su_fecha(self):
        for atras in (3, 2, 1):
            self.dia_bueno(HOY() - timedelta(days=atras))
        hito = next(h for h in self.client.get(reverse('logros')).data['hitos'] if h['id'] == 'racha-3')
        self.assertTrue(hito['logrado'])
        self.assertEqual(hito['logrado_en'], HOY() - timedelta(days=1))
        siete = next(h for h in self.client.get(reverse('logros')).data['hitos'] if h['id'] == 'racha-7')
        self.assertEqual((siete['logrado'], siete['actual'], siete['meta']), (False, 3, 7))


class HitosTest(LogrosBase):
    def hitos(self):
        return {h['id']: h for h in self.client.get(reverse('logros')).data['hitos']}

    def test_el_agua_acumulada_cuenta_lo_que_se_tomo(self):
        for _ in range(20):
            RegistroHabito.objects.create(usuario=self.usuario, tipo='agua', ml=500)
        h = self.hitos()
        self.assertTrue(h['agua-10']['logrado'])
        self.assertFalse(h['agua-50']['logrado'])
        self.assertEqual(h['agua-50']['actual'], 10)

    def test_un_hito_nuevo_se_celebra_una_vez(self):
        RegistroEntrenamiento.objects.create(usuario=self.usuario)
        self.assertTrue(self.hitos()['entreno-1']['nuevo'])
        r = self.client.post(reverse('logros-vistos'), {'ids': ['entreno-1', 'racha-90']}, format='json')
        self.assertEqual(r.data, {'vistos': 1})    # el de la racha no se logró: no cuenta
        self.assertFalse(self.hitos()['entreno-1']['nuevo'])
        self.assertTrue(self.hitos()['entreno-1']['logrado'])

    def test_lo_logrado_hace_tiempo_no_se_celebra_de_golpe(self):
        RegistroEntrenamiento.objects.create(usuario=self.usuario, fecha=HOY() - timedelta(days=10))
        h = self.hitos()['entreno-1']
        self.assertTrue(h['logrado'])
        self.assertFalse(h['nuevo'])
        self.assertTrue(HitoVisto.objects.filter(usuario=self.usuario, clave='entreno-1').exists())

    def test_los_ids_deben_ser_una_lista_de_textos(self):
        for malo in ({'ids': 'x'}, {'ids': [1]}, {}):
            r = self.client.post(reverse('logros-vistos'), malo, format='json')
            self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_sin_registros_no_hay_hitos_logrados(self):
        self.assertEqual(self.client.get(reverse('logros')).data['logrados'], 0)


class CapituloTest(LogrosBase):
    def test_la_semana_con_su_titulo_sus_estaciones_y_lo_que_mirar(self):
        lunes = self.lunes_hace(1)
        for i in range(7):
            self.dia_bueno(lunes + timedelta(days=i))
        r = self.client.get(reverse('capitulo'), {'lunes': lunes.isoformat()})
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        self.assertEqual((r.data['porcentaje'], r.data['titulo'], r.data['completa']),
                         (100, 'Semana de guerrero', True))
        self.assertEqual(len(r.data['estaciones']), 7)
        self.assertIsNone(r.data['para_mirar'])
        self.assertEqual(r.data['mejor_dia']['porcentaje'], 100)

    def test_dice_cuanto_subio_frente_a_la_anterior_y_que_mirar(self):
        anterior, lunes = self.lunes_hace(2), self.lunes_hace(1)
        for i in range(7):
            RegistroHabito.objects.create(usuario=self.usuario, tipo='agua', fecha=anterior + timedelta(days=i), ml=500)
            self.dia_bueno(lunes + timedelta(days=i))
        r = self.client.get(reverse('capitulo'), {'lunes': lunes.isoformat()}).data
        self.assertGreater(r['diferencia'], 0)
        r2 = self.client.get(reverse('capitulo'), {'lunes': anterior.isoformat()}).data
        self.assertEqual(r2['para_mirar']['nombre'], 'Dormir')    # lo que más faltó esa semana

    def test_la_semana_debe_empezar_en_lunes_y_no_ser_futura(self):
        martes = logros.lunes_de(HOY()) + timedelta(days=1)
        self.assertEqual(self.client.get(reverse('capitulo'), {'lunes': martes.isoformat()}).status_code,
                         status.HTTP_400_BAD_REQUEST)
        futuro = logros.lunes_de(HOY()) + timedelta(days=7)
        self.assertEqual(self.client.get(reverse('capitulo'), {'lunes': futuro.isoformat()}).status_code,
                         status.HTTP_400_BAD_REQUEST)

    def test_por_defecto_es_la_semana_de_hoy(self):
        r = self.client.get(reverse('capitulo')).data
        self.assertTrue(r['es_actual'])
        self.assertEqual(r['lunes'], logros.lunes_de(HOY()))

    def test_una_semana_sin_terminar_no_se_juzga_todavia(self):
        self.dia_bueno(HOY())
        r = self.client.get(reverse('capitulo')).data
        self.assertFalse(r['completa'])
        self.assertEqual(r['titulo'], 'Así va tu semana')
        # Lleva la semana entera (7 días), no solo los días que van; y no se compara con la anterior.
        self.assertEqual(r['porcentaje_semana'], round(100 / 7))   # un solo día al 100 % de los 7
        self.assertIsNone(r['diferencia'])
