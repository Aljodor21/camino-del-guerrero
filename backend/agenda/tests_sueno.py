from datetime import datetime, time, timedelta

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
        a = self.client.post(reverse('registrar-levantar'))
        b = self.client.post(reverse('registrar-levantar'))
        self.assertEqual(a.status_code, status.HTTP_201_CREATED)
        self.assertEqual(a.data['id'], b.data['id'])
        self.assertEqual(RegistroHabito.objects.filter(tipo='levantar').count(), 1)

    def test_el_boton_me_acoste_anota_la_noche_y_lo_de_hoy_lo_cuenta(self):
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


class DecirLaHoraRealTest(SuenoTest):
    """Si se anota tarde, la persona dice a qué hora fue de verdad; lo último que dice es lo que cuenta."""

    AHORA = a_las(HOY(), 14, 30)

    def ahora(self):
        from unittest.mock import patch
        return patch('django.utils.timezone.now', return_value=self.AHORA)

    def test_se_levanto_a_las_cinco_y_lo_dice_a_las_dos_de_la_tarde(self):
        ayer = HOY() - timedelta(days=1)
        RegistroHabito.objects.create(usuario=self.usuario, tipo='dormir', fecha=ayer, momento=a_las(ayer, 22, 0))
        with self.ahora():
            primero = self.client.post(reverse('registrar-levantar')).data           # lo anotó tarde, «ahora»
            r = self.client.post(reverse('registrar-levantar'), {'hora': '04:50'}, format='json')
            self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
            hoy = self.client.get(reverse('hoy')).data['levantar']
        self.assertNotEqual(primero['id'], r.data['id'])
        self.assertEqual(timezone.localtime(parse_datetime(r.data['momento'])).strftime('%H:%M'), '04:50')
        # La última palabra manda: duerme 6 h 50 min y se levantó a las 4:50, no a las 2:30 de la tarde.
        self.assertEqual(hoy['dormiste_horas'], 6.83)
        self.assertEqual(timezone.localtime(hoy['acostado_anoche']).strftime('%H:%M'), '22:00')
        self.assertEqual(timezone.localtime(hoy['levantado']).strftime('%H:%M'), '04:50')
        # Los dos registros quedan: nada se borra ni se edita.
        self.assertEqual(RegistroHabito.objects.filter(usuario=self.usuario, tipo='levantar').count(), 2)

    def test_puede_corregir_hacia_adelante_o_hacia_atras(self):
        with self.ahora():
            self.client.post(reverse('registrar-levantar'), {'hora': '04:50'}, format='json')
            self.client.post(reverse('registrar-levantar'), {'hora': '06:15'}, format='json')
            hoy = self.client.get(reverse('hoy')).data['levantar']
        self.assertEqual(timezone.localtime(hoy['levantado']).strftime('%H:%M'), '06:15')

    def test_una_hora_futura_o_mal_escrita_se_rechaza(self):
        with self.ahora():
            for malo in ({'hora': '16:00'}, {'hora': 'tarde'}, {'hora': '25:00'}):
                r = self.client.post(reverse('registrar-levantar'), malo, format='json')
                self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST, malo)
        self.assertFalse(RegistroHabito.objects.filter(usuario=self.usuario, tipo='levantar').exists())

    def test_el_aviso_pendiente_se_cumple_con_la_hora_dicha(self):
        notificaciones.generar(self.usuario, a_las(HOY(), 6, 5))
        n = Notificacion.objects.get(usuario=self.usuario, tipo='levantar')
        with self.ahora():
            r = self.client.post(reverse('registrar-levantar'), {'hora': '05:00'}, format='json')
        n.refresh_from_db()
        self.assertEqual((n.resolucion, n.registro.id), ('confirmada', r.data['id']))

    def test_acostarse_a_las_once_y_media_dicho_al_dia_siguiente(self):
        ayer = HOY() - timedelta(days=1)
        with self.ahora():
            r = self.client.post(reverse('registrar-dormir'), {'hora': '23:30'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        self.assertEqual(r.data['fecha'], ayer.isoformat())
        self.assertEqual(timezone.localtime(parse_datetime(r.data['momento'])).strftime('%d %H:%M'),
                         f'{ayer:%d} 23:30')

    def test_acostarse_pasada_la_medianoche_cuenta_para_la_noche_anterior(self):
        ayer = HOY() - timedelta(days=1)
        with self.ahora():
            r = self.client.post(reverse('registrar-dormir'), {'hora': '00:40'}, format='json')
        self.assertEqual(r.data['fecha'], ayer.isoformat())
        self.assertEqual(timezone.localtime(parse_datetime(r.data['momento'])).strftime('%H:%M'), '00:40')

    def test_una_hora_de_acostarse_de_hace_mas_de_un_dia_se_rechaza(self):
        from unittest.mock import patch
        con_dos_dias = a_las(HOY(), 3, 0)          # a las 3:00 ya pasaron 20 h desde las 7:00 de ayer
        with patch('django.utils.timezone.now', return_value=con_dos_dias):
            r = self.client.post(reverse('registrar-dormir'), {'hora': '06:00'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_la_ultima_hora_de_acostarse_es_la_que_cuenta_para_el_cumplimiento(self):
        ayer = HOY() - timedelta(days=1)
        RegistroHabito.objects.create(usuario=self.usuario, tipo='dormir', fecha=ayer, momento=a_las(ayer, 21, 30))
        with self.ahora():
            self.client.post(reverse('registrar-dormir'), {'hora': '23:10'}, format='json')
        dia = self.client.get(reverse('cumplimiento-global'), {'desde': ayer.isoformat(), 'hasta': ayer.isoformat()}).data['dias'][0]
        dormir = next(b for b in dia['bloques'] if b['id'] == 'dormir')
        self.assertIn('23:10', dormir['detalle'])
