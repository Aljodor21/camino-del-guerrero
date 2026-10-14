from contextlib import contextmanager
from datetime import datetime, time, timedelta
from unittest import mock

from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import status
from rest_framework.test import APITestCase

from users.models import Usuario

from . import notificaciones, sueno
from .models import Habitos, Notificacion, RegistroHabito

HOY = timezone.localdate


def a_las(dia, hora, minuto=0):
    return timezone.make_aware(datetime.combine(dia, time(hora, minuto)))


@contextmanager
def a_la_hora(hora, minuto=0, dia=None):
    """Hace como si fueran las `hora:minuto` de hoy (o de `dia`)."""
    with mock.patch('django.utils.timezone.now', return_value=a_las(dia or HOY(), hora, minuto)):
        yield


class SuenoTest(APITestCase):
    def setUp(self):
        self.usuario = Usuario.objects.create_user(username='s@x.co', email='s@x.co', nombre='S',
                                                   password='clave-segura-123')
        Usuario.objects.filter(pk=self.usuario.pk).update(date_joined=timezone.now() - timedelta(days=20))
        self.usuario.refresh_from_db()
        self.client.force_authenticate(self.usuario)
        Habitos.objects.create(usuario=self.usuario, agua_ml=2000, vaso_ml=500,
                               hora_levantarse=time(6, 0), hora_dormir=time(22, 0))

    def noche(self, dia, acostado, levantado):
        """Se acostó la noche de `dia` a la hora `acostado` y se levantó a la mañana siguiente."""
        RegistroHabito.objects.create(usuario=self.usuario, tipo='dormir', fecha=dia,
                                      momento=a_las(dia, *acostado))
        manana = dia + timedelta(days=1)
        RegistroHabito.objects.create(usuario=self.usuario, tipo='levantar', fecha=manana,
                                      momento=a_las(manana, *levantado))

    def test_el_promedio_sale_de_acostarse_a_levantarse(self):
        self.noche(HOY() - timedelta(days=3), (22, 30), (6, 15))      # 7 h 45 min
        self.noche(HOY() - timedelta(days=2), (23, 0), (6, 0))        # 7 h
        r = self.client.get(reverse('sueno')).data
        self.assertEqual([n['horas'] for n in r['noches']], [7.75, 7.0])
        self.assertEqual(r['promedio_horas'], 7.38)

    def test_se_acostar_pasada_la_medianoche_tambien_cuenta(self):
        ayer = HOY() - timedelta(days=1)
        RegistroHabito.objects.create(usuario=self.usuario, tipo='dormir', fecha=ayer, momento=a_las(HOY(), 0, 30))
        RegistroHabito.objects.create(usuario=self.usuario, tipo='levantar', fecha=HOY(), momento=a_las(HOY(), 6, 30))
        self.assertEqual(sueno.anoche(self.usuario)['horas'], 6.0)

    def test_sin_una_de_las_dos_horas_o_con_horas_absurdas_no_cuenta(self):
        RegistroHabito.objects.create(usuario=self.usuario, tipo='levantar', fecha=HOY() - timedelta(days=2),
                                      momento=a_las(HOY() - timedelta(days=2), 6))      # sin acostarse
        self.noche(HOY() - timedelta(days=5), (6, 0), (6, 0))          # 24 h: se olvidó una
        r = self.client.get(reverse('sueno')).data
        self.assertEqual(r['noches'], [])
        self.assertIsNone(r['promedio_horas'])

    def test_el_aviso_de_levantarse_sale_a_la_hora_y_se_confirma_con_su_boton(self):
        notificaciones.generar(self.usuario, a_las(HOY(), 7))
        n = Notificacion.objects.get(usuario=self.usuario, tipo='levantar')
        self.assertEqual(n.titulo, 'Buenos días: ¿ya te levantaste?')
        self.assertEqual(notificaciones.accion_de(n), 'Ya me levanté')
        r = self.client.post(reverse('aviso-confirmar', args=[n.id]))
        self.assertEqual(r.status_code, status.HTTP_204_NO_CONTENT)
        self.assertTrue(RegistroHabito.objects.filter(usuario=self.usuario, tipo='levantar', notificacion=n).exists())

    def test_el_boton_me_levante_anota_una_sola_vez_al_dia(self):
        with a_la_hora(6, 10):
            a = self.client.post(reverse('registrar-levantar'))
            b = self.client.post(reverse('registrar-levantar'))
        self.assertEqual(a.status_code, status.HTTP_201_CREATED)
        self.assertEqual(a.data['id'], b.data['id'])
        self.assertEqual(RegistroHabito.objects.filter(tipo='levantar').count(), 1)

    def test_el_boton_me_acoste_anota_la_noche_y_lo_de_hoy_lo_cuenta(self):
        with a_la_hora(21, 30):
            r = self.client.post(reverse('registrar-dormir'))
            self.assertEqual(r.status_code, status.HTTP_201_CREATED)
            self.assertEqual(self.client.post(reverse('registrar-dormir')).data['id'], r.data['id'])
            hoy = self.client.get(reverse('hoy')).data
        self.assertEqual(RegistroHabito.objects.filter(usuario=self.usuario, tipo='dormir').count(), 1)
        self.assertIn('dormir', hoy)

    def test_hoy_dice_si_ya_te_levantaste_y_cuanto_dormiste(self):
        ayer = HOY() - timedelta(days=1)
        RegistroHabito.objects.create(usuario=self.usuario, tipo='dormir', fecha=ayer, momento=a_las(ayer, 23))
        self.assertIsNone(self.client.get(reverse('hoy')).data['levantar']['levantado'])
        RegistroHabito.objects.create(usuario=self.usuario, tipo='levantar', fecha=HOY(), momento=a_las(HOY(), 6, 30))
        d = self.client.get(reverse('hoy')).data['levantar']
        self.assertIsNotNone(d['levantado'])
        self.assertEqual(d['dormiste_horas'], 7.5)

    def test_el_periodo_no_pasa_de_un_trimestre(self):
        r = self.client.get(reverse('sueno'), {'desde': (HOY() - timedelta(days=200)).isoformat()})
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_se_puede_apagar_el_aviso_de_levantarse(self):
        Habitos.objects.filter(usuario=self.usuario).update(avisos_apagados=['levantar'])
        notificaciones.generar(self.usuario, a_las(HOY(), 7))
        self.assertFalse(Notificacion.objects.filter(usuario=self.usuario, tipo='levantar').exists())


class SinAvisosRetroactivosTest(APITestCase):
    """Los avisos de levantarse y de acostarse solo valen cerca de su hora: no aparecen horas después."""

    def setUp(self):
        SuenoTest.setUp(self)

    def test_no_pregunta_si_ya_te_levantaste_cuando_ya_pasaron_horas(self):
        # Hora prevista 6:00; la app lo calcula por primera vez a las 11 (se acaba de estrenar o de cambiar la hora).
        notificaciones.generar(self.usuario, a_las(HOY(), 11))
        self.assertFalse(Notificacion.objects.filter(usuario=self.usuario, tipo='levantar').exists())

    def test_si_lo_calcula_a_tiempo_si_lo_crea(self):
        notificaciones.generar(self.usuario, a_las(HOY(), 7, 15))     # 75 minutos después de las 6:00
        self.assertTrue(Notificacion.objects.filter(usuario=self.usuario, tipo='levantar').exists())

    def test_uno_que_se_quedo_pendiente_se_quita_solo_horas_despues(self):
        notificaciones.generar(self.usuario, a_las(HOY(), 6, 5))
        n = Notificacion.objects.get(usuario=self.usuario, tipo='levantar')
        self.assertIsNone(n.resuelta_en)
        notificaciones.generar(self.usuario, a_las(HOY(), 11))
        n.refresh_from_db()
        self.assertEqual(n.resolucion, 'automatica')
        # Y no quedó ningún dato inventado: no hay registro de que se levantó.
        self.assertFalse(RegistroHabito.objects.filter(usuario=self.usuario, tipo='levantar').exists())

    def test_lo_mismo_con_el_aviso_de_dormir(self):
        notificaciones.generar(self.usuario, a_las(HOY(), 23, 50))    # el aviso era a las 21:30
        self.assertFalse(Notificacion.objects.filter(usuario=self.usuario, tipo='dormir').exists())
        notificaciones.generar(self.usuario, a_las(HOY(), 21, 40))
        self.assertTrue(Notificacion.objects.filter(usuario=self.usuario, tipo='dormir').exists())

    def test_lo_demas_si_aparece_aunque_la_app_lo_calcule_tarde(self):
        notificaciones.generar(self.usuario, a_las(HOY(), 15))
        self.assertTrue(Notificacion.objects.filter(usuario=self.usuario, tipo='agua').exists())


class LaUltimaPalabraTest(SuenoTest):
    """La hora es un valor: se anota al momento y no se cambia. Si por algún motivo hay más de un registro del
    mismo día (datos de antes), vale el último."""

    def test_no_hay_forma_de_poner_otra_hora_por_la_api(self):
        # A tiempo no se acepta una hora; se anota la de ahora.
        with a_la_hora(6, 10):
            r = self.client.post(reverse('registrar-levantar'), {'hora': '04:50'}, format='json')
            self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
            r = self.client.post(reverse('registrar-levantar'), {}, format='json')
            self.assertEqual(r.status_code, status.HTTP_201_CREATED)
            self.assertEqual(timezone.localtime(parse_datetime(r.data['momento'])).strftime('%H:%M'), '06:10')
        with a_la_hora(21, 30):
            r2 = self.client.post(reverse('registrar-dormir'), {'hora': '23:30'}, format='json')
            self.assertEqual(timezone.localtime(parse_datetime(r2.data['momento'])).strftime('%H:%M'), '21:30')

    def test_con_dos_registros_del_mismo_dia_manda_el_ultimo(self):
        ayer = HOY() - timedelta(days=1)
        RegistroHabito.objects.create(usuario=self.usuario, tipo='dormir', fecha=ayer, momento=a_las(ayer, 22, 0))
        RegistroHabito.objects.create(usuario=self.usuario, tipo='levantar', fecha=HOY(), momento=a_las(HOY(), 13, 46))
        RegistroHabito.objects.create(usuario=self.usuario, tipo='levantar', fecha=HOY(), momento=a_las(HOY(), 4, 50))
        hoy = self.client.get(reverse('hoy')).data['levantar']
        self.assertEqual(timezone.localtime(hoy['levantado']).strftime('%H:%M'), '04:50')
        self.assertEqual(hoy['dormiste_horas'], 6.83)


class VentanasYSiestasTest(SuenoTest):
    """«Me levanté» vale ±2 h de la hora prevista (6:00), «ya me acosté» desde 2 h antes de acostarse (22:00)
    y las siestas se acaban cuando empieza la jornada de dormir."""

    def levantar(self, hora=None):
        return self.client.post(reverse('registrar-levantar'), {'hora': hora} if hora else {}, format='json')

    def test_me_levante_solo_dos_horas_antes_o_despues(self):
        with a_la_hora(3, 30):
            self.assertEqual(self.client.get(reverse('hoy')).data['levantar']['ventana'], 'antes')
            self.assertEqual(self.levantar().status_code, status.HTTP_400_BAD_REQUEST)
        with a_la_hora(4, 0):
            self.assertEqual(self.client.get(reverse('hoy')).data['levantar']['ventana'], 'abierta')
        with a_la_hora(8, 0):
            self.assertEqual(self.levantar().status_code, status.HTTP_201_CREATED)

    def test_si_no_responde_queda_sin_respuesta_y_se_responde_una_vez_con_la_hora(self):
        with a_la_hora(9, 0):
            d = self.client.get(reverse('hoy')).data['levantar']
            self.assertEqual((d['ventana'], d['levantado']), ('cerrada', None))
            self.assertEqual(self.levantar().status_code, status.HTTP_400_BAD_REQUEST)
            # Una hora que todavía no llega o mal escrita no sirve.
            self.assertEqual(self.levantar('10:00').status_code, status.HTTP_400_BAD_REQUEST)
            self.assertEqual(self.levantar('tarde').status_code, status.HTTP_400_BAD_REQUEST)
            r = self.levantar('07:20')
            self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
            self.assertEqual(timezone.localtime(parse_datetime(r.data['momento'])).strftime('%H:%M'), '07:20')
            # Ya respondió: no hay una segunda hora.
            self.assertEqual(self.levantar('07:40').data['id'], r.data['id'])
            self.assertEqual(RegistroHabito.objects.filter(tipo='levantar').count(), 1)

    def test_la_hora_no_se_puede_decir_si_estaba_a_tiempo(self):
        with a_la_hora(6, 30):
            self.assertEqual(self.levantar('06:00').status_code, status.HTTP_400_BAD_REQUEST)

    def test_ya_me_acoste_abre_dos_horas_antes(self):
        with a_la_hora(19, 30):
            self.assertFalse(self.client.get(reverse('hoy')).data['dormir']['abierta'])
            self.assertEqual(self.client.post(reverse('registrar-dormir')).status_code, status.HTTP_400_BAD_REQUEST)
        with a_la_hora(20, 0):
            self.assertTrue(self.client.get(reverse('hoy')).data['dormir']['abierta'])
            self.assertEqual(self.client.post(reverse('registrar-dormir')).status_code, status.HTTP_201_CREATED)

    def test_ya_me_acoste_vale_hasta_dos_horas_antes_de_levantarse_y_despues_no_respondio(self):
        Habitos.objects.filter(usuario=self.usuario).update(hora_levantarse=time(5, 0))
        ayer = HOY() - timedelta(days=1)
        with a_la_hora(3, 30):          # la noche de ayer: hasta las 3:00 (5:00 menos 2 h)
            d = self.client.get(reverse('hoy')).data['dormir']
            self.assertEqual((d['ventana'], d['abierta']), ('cerrada', False))
            self.assertEqual(self.client.post(reverse('registrar-dormir')).status_code, status.HTTP_400_BAD_REQUEST)
        with a_la_hora(2, 30):
            self.assertEqual(self.client.post(reverse('registrar-dormir')).status_code, status.HTTP_201_CREATED)
        self.assertTrue(RegistroHabito.objects.filter(tipo='dormir', fecha=ayer).exists())

    def test_anoche_sin_respuesta_se_dice_por_la_manana(self):
        with a_la_hora(5, 0):
            self.assertTrue(self.client.get(reverse('hoy')).data['dormir']['anoche_sin_respuesta'])
        with a_la_hora(3, 0):
            self.assertFalse(self.client.get(reverse('hoy')).data['dormir']['anoche_sin_respuesta'])

    def test_voy_a_dormir_y_deje_de_dormir_solo_fuera_de_las_horas_de_sueno(self):
        with a_la_hora(14, 0):
            self.assertTrue(self.client.get(reverse('hoy')).data['siesta']['puede_iniciar'])
            self.assertEqual(self.client.post(reverse('siesta-terminar')).status_code, status.HTTP_400_BAD_REQUEST)
            self.assertEqual(self.client.post(reverse('siesta-iniciar')).status_code, status.HTTP_201_CREATED)
            self.assertEqual(self.client.post(reverse('siesta-iniciar')).status_code, status.HTTP_400_BAD_REQUEST)
            d = self.client.get(reverse('hoy')).data['siesta']
            self.assertIsNotNone(d['en_curso'])
            self.assertFalse(d['puede_iniciar'])
        with a_la_hora(14, 40):
            self.assertEqual(self.client.post(reverse('siesta-terminar')).status_code, status.HTTP_201_CREATED)
            d = self.client.get(reverse('hoy')).data['siesta']
            self.assertEqual([s['minutos'] for s in d['hechas']], [40])
            self.assertTrue(d['puede_iniciar'])
        # Desde 2 h antes de acostarse (20:00) son horas de sueño.
        with a_la_hora(20, 5):
            self.assertFalse(self.client.get(reverse('hoy')).data['siesta']['puede_iniciar'])
            self.assertEqual(self.client.post(reverse('siesta-iniciar')).status_code, status.HTTP_400_BAD_REQUEST)
        # De madrugada y antes de levantarse también; ya levantado (o pasado el rato para decirlo), no.
        with a_la_hora(5, 0):
            self.assertFalse(self.client.get(reverse('hoy')).data['siesta']['puede_iniciar'])
        with a_la_hora(6, 10):
            self.assertEqual(self.levantar().status_code, status.HTTP_201_CREATED)
            self.assertTrue(self.client.get(reverse('hoy')).data['siesta']['puede_iniciar'])

    def test_sin_responder_el_levantarse_la_siesta_se_abre_pasado_el_rato(self):
        with a_la_hora(7, 0):
            self.assertFalse(self.client.get(reverse('hoy')).data['siesta']['puede_iniciar'])
        with a_la_hora(8, 30):
            self.assertTrue(self.client.get(reverse('hoy')).data['siesta']['puede_iniciar'])
