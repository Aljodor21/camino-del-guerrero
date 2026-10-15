from contextlib import contextmanager
from datetime import datetime, time, timedelta
from unittest import mock

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from users.models import Usuario

from . import cumplimiento, logros, notificaciones, pausa
from .models import Habitos, Notificacion, Pausa, RegistroHabito

HOY = timezone.localdate


def a_las(dia, hora, minuto=0):
    return timezone.make_aware(datetime.combine(dia, time(hora, minuto)))


@contextmanager
def a_la_hora(dia, hora, minuto=0):
    with mock.patch('django.utils.timezone.now', return_value=a_las(dia, hora, minuto)):
        yield


class PausaTest(APITestCase):
    def setUp(self):
        self.usuario = Usuario.objects.create_user(username='p@x.co', email='p@x.co', nombre='P',
                                                   password='clave-segura-123')
        Usuario.objects.filter(pk=self.usuario.pk).update(date_joined=timezone.now() - timedelta(days=20))
        self.usuario.refresh_from_db()
        self.client.force_authenticate(self.usuario)
        Habitos.objects.create(usuario=self.usuario, agua_ml=2000, vaso_ml=500,
                               hora_levantarse=time(6, 0), hora_dormir=time(22, 0))

    def pausar(self, **datos):
        return self.client.post(reverse('pausa'), datos, format='json')

    def agua(self, dia, vasos=4):
        for _ in range(vasos):
            RegistroHabito.objects.create(usuario=self.usuario, tipo='agua', fecha=dia, ml=500,
                                          momento=a_las(dia, 10))

    def test_en_pausa_no_llega_ningun_aviso_y_los_pendientes_se_quitan(self):
        dia = HOY()
        notificaciones.generar(self.usuario, a_las(dia, 9))
        self.assertTrue(Notificacion.objects.filter(resuelta_en__isnull=True).exists())
        with a_la_hora(dia, 9, 5):
            r = self.pausar(duracion='dias', cantidad=3, motivo='Nació mi bebé')
            self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
            self.assertFalse(Notificacion.objects.filter(resuelta_en__isnull=True).exists())
            self.assertEqual(Notificacion.objects.filter(resolucion='pausa').count(),
                             Notificacion.objects.count())
            # Ya en pausa: otra no.
            self.assertEqual(self.pausar(duracion='hoy').status_code, status.HTTP_400_BAD_REQUEST)
            self.assertEqual(self.client.get(reverse('pausa')).data['activa']['motivo'], 'Nació mi bebé')
        antes = Notificacion.objects.count()
        notificaciones.generar(self.usuario, a_las(dia, 20))
        notificaciones.generar(self.usuario, a_las(dia + timedelta(days=1), 20))
        self.assertEqual(Notificacion.objects.count(), antes)
        # Y el celular no programa nada en esos días.
        with a_la_hora(dia, 9, 10):
            proximos = notificaciones.proximos(self.usuario, 5)
        self.assertTrue(all(timezone.localdate(a['programada_para']) >= dia + timedelta(days=3) for a in proximos))

    def test_ya_volvi_vuelve_a_avisar_sin_amontonar_lo_de_la_pausa(self):
        dia = HOY()
        with a_la_hora(dia, 8):
            self.pausar(duracion='indefinida')
        with a_la_hora(dia, 15):
            self.assertEqual(self.client.delete(reverse('pausa')).status_code, status.HTTP_200_OK)
            self.assertIsNone(self.client.get(reverse('pausa')).data['activa'])
            self.assertEqual(self.client.delete(reverse('pausa')).status_code, status.HTTP_400_BAD_REQUEST)
        notificaciones.generar(self.usuario, a_las(dia, 21, 50))
        # Solo lo de después de volver (el agua de la tarde, dormir), nada de lo que tocaba en la pausa.
        horas = {timezone.localtime(n.programada_para).hour for n in Notificacion.objects.all()}
        self.assertTrue(horas)
        self.assertTrue(all(h >= 15 for h in horas), horas)

    def test_los_dias_en_pausa_no_cuentan_ni_rompen_la_racha(self):
        hoy = HOY()
        for atras in (6, 5, 4, 1):
            d = hoy - timedelta(days=atras)
            self.agua(d)
            RegistroHabito.objects.create(usuario=self.usuario, tipo='dormir', fecha=d, momento=a_las(d, 22))
        # Los días 3 y 2 atrás estuvo en pausa.
        Pausa.objects.create(usuario=self.usuario, desde=a_las(hoy - timedelta(days=3), 0),
                             hasta=a_las(hoy - timedelta(days=1), 0), motivo='Nació mi bebé')
        datos = cumplimiento.calcular(self.usuario, hoy - timedelta(days=6), hoy - timedelta(days=1))
        en_pausa = [d['fecha'] for d in datos['dias'] if d['en_pausa']]
        self.assertEqual(en_pausa, [hoy - timedelta(days=3), hoy - timedelta(days=2)])
        self.assertEqual((datos['dias_en_pausa'], datos['dias_periodo']), (2, 4))
        self.assertEqual(datos['racha_actual'], 4)
        self.assertEqual(logros.logros(self.usuario)['racha']['actual'], 4)

    def test_una_pausa_de_unas_horas_solo_calla_los_avisos(self):
        hoy = HOY()
        p = Pausa.objects.create(usuario=self.usuario, desde=a_las(hoy, 9), hasta=a_las(hoy, 13))
        self.assertEqual(pausa.dias_en_pausa(self.usuario, hoy, hoy, a_las(hoy, 20)), set())
        notificaciones.generar(self.usuario, a_las(hoy, 14))
        horas = [timezone.localtime(n.programada_para).hour for n in Notificacion.objects.all()]
        self.assertFalse([h for h in horas if 9 <= h < 13], horas)
        p.delete()

    def test_validaciones(self):
        for datos in ({'duracion': 'siempre'}, {'duracion': 'horas', 'cantidad': 30},
                      {'duracion': 'dias', 'cantidad': 0}, {'duracion': 'dias'}):
            self.assertEqual(self.pausar(**datos).status_code, status.HTTP_400_BAD_REQUEST, datos)
        r = self.pausar(duracion='horas', cantidad=4)
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)

    def test_desde_ayer_cuenta_el_dia_de_ayer(self):
        hoy = HOY()
        with a_la_hora(hoy, 10):
            self.pausar(duracion='hoy', desde_ayer=True)
            self.assertIn(hoy - timedelta(days=1),
                          pausa.dias_en_pausa(self.usuario, hoy - timedelta(days=1), hoy))


class QuePasoTest(APITestCase):
    def setUp(self):
        self.usuario = Usuario.objects.create_user(username='q@x.co', email='q@x.co', nombre='Q',
                                                   password='clave-segura-123')
        Usuario.objects.filter(pk=self.usuario.pk).update(date_joined=timezone.now() - timedelta(days=20))
        self.usuario.refresh_from_db()
        self.client.force_authenticate(self.usuario)
        Habitos.objects.create(usuario=self.usuario)

    def test_un_dia_sin_nada_pregunta_que_paso_y_pausar_hoy_lo_resuelve(self):
        hoy = HOY()
        RegistroHabito.objects.create(usuario=self.usuario, tipo='agua', fecha=hoy - timedelta(days=2),
                                      momento=a_las(hoy - timedelta(days=2), 9))
        notificaciones.generar(self.usuario, a_las(hoy, 10))
        n = Notificacion.objects.get(tipo='regreso')
        self.assertEqual(n.titulo, 'Ey, llevas 2 días sin aparecer')
        self.assertEqual((notificaciones.accion_de(n), notificaciones.url_de(n)), ('Pausar hoy', '/avisos?seccion=dia'))
        with a_la_hora(hoy, 10, 5):
            self.assertEqual(self.client.post(reverse('aviso-confirmar', args=[n.id])).status_code,
                             status.HTTP_204_NO_CONTENT)
            self.assertIsNotNone(pausa.activa(self.usuario))
        # Un solo aviso de estos al día.
        notificaciones.generar(self.usuario, a_las(hoy, 23))
        self.assertEqual(Notificacion.objects.filter(tipo='regreso').count(), 1)

    def test_con_actividad_reciente_no_pregunta_y_si_vuelve_se_quita_solo(self):
        hoy = HOY()
        RegistroHabito.objects.create(usuario=self.usuario, tipo='agua', fecha=hoy, momento=a_las(hoy, 7))
        notificaciones.generar(self.usuario, a_las(hoy, 10))
        self.assertFalse(Notificacion.objects.filter(tipo='regreso').exists())
        RegistroHabito.objects.all().delete()
        RegistroHabito.objects.create(usuario=self.usuario, tipo='agua', fecha=hoy - timedelta(days=1),
                                      momento=a_las(hoy - timedelta(days=1), 8))
        notificaciones.generar(self.usuario, a_las(hoy, 10))
        n = Notificacion.objects.get(tipo='regreso')
        self.assertEqual(n.titulo, 'Ey, ¿qué pasó?')
        RegistroHabito.objects.create(usuario=self.usuario, tipo='agua', fecha=hoy, momento=a_las(hoy, 11))
        notificaciones.resolver_automaticas(self.usuario, a_las(hoy, 11, 5))
        n.refresh_from_db()
        self.assertEqual(n.resolucion, 'automatica')
