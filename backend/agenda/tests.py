import json
from datetime import datetime, time, timedelta
from unittest.mock import MagicMock, patch

from django.core.management import call_command
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from pywebpush import WebPushException
from rest_framework import status
from rest_framework.test import APITestCase

from core.exceptions import DatoInmutableError
from progress.models import RegistroEntrenamiento
from routines.models import DiaRutina, Rutina
from users.models import Proceso, Usuario

from . import notificaciones
from .models import Habitos, Notificacion, Recordatorio, RegistroHabito, SuscripcionPush

HOY = timezone.localdate


class RecordatorioTest(APITestCase):
    def setUp(self):
        self.usuario = Usuario.objects.create_user(username='a@x.co', email='a@x.co', nombre='A',
                                                   password='clave-segura-123')
        self.client.force_authenticate(self.usuario)
        self.proceso = Proceso.objects.create(usuario=self.usuario, objetivo='ganar_musculo', fase='volumen')

    def crear(self, **cambios):
        datos = {'tipo': 'control', 'titulo': 'Control con la nutricionista',
                 'fecha': (HOY() + timedelta(days=60)).isoformat(), 'hora': '07:30', 'avisar_dias_antes': 3}
        datos.update(cambios)
        return self.client.post(reverse('recordatorios'), datos, format='json')

    def test_crear_queda_ligado_al_proceso(self):
        r = self.crear()
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        self.assertEqual(r.data['proceso'], self.proceso.id)
        self.assertEqual(r.data['tipo_nombre'], 'Control con profesional')
        self.assertIsNone(r.data['completado_en'])

    def test_validaciones(self):
        ayer = (HOY() - timedelta(days=1)).isoformat()
        self.assertEqual(self.crear(fecha=ayer).status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.crear(titulo='   ').status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.crear(avisar_dias_antes=31).status_code, status.HTTP_400_BAD_REQUEST)

    def test_se_marca_como_hecho_cuando_llega_su_fecha_no_antes(self):
        url = reverse('recordatorio-detail', args=[self.crear().data['id']])
        r = self.client.patch(url, {'completado': True}, format='json')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Todavía no llega la fecha', str(r.data))
        hoy = self.crear(fecha=HOY().isoformat()).data['id']
        r = self.client.patch(reverse('recordatorio-detail', args=[hoy]), {'completado': True}, format='json')
        self.assertEqual(r.status_code, status.HTTP_200_OK)

    def test_completar_reprogramar_y_borrar(self):
        r = self.crear(fecha=HOY().isoformat())
        url = reverse('recordatorio-detail', args=[r.data['id']])
        r = self.client.patch(url, {'completado': True}, format='json')
        self.assertIsNotNone(r.data['completado_en'])
        r = self.client.patch(url, {'completado': False}, format='json')
        self.assertIsNone(r.data['completado_en'])

        nueva = (HOY() + timedelta(days=75)).isoformat()
        self.assertEqual(self.client.patch(url, {'fecha': nueva}, format='json').data['fecha'], nueva)
        self.assertEqual(self.client.put(url, {}, format='json').status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertEqual(self.client.delete(url).status_code, status.HTTP_204_NO_CONTENT)

    def test_uno_vencido_se_puede_completar_sin_tocar_su_fecha(self):
        r = Recordatorio.objects.create(usuario=self.usuario, titulo='Pesarme', fecha=HOY() - timedelta(days=2))
        url = reverse('recordatorio-detail', args=[r.id])
        self.assertEqual(self.client.patch(url, {'completado': True, 'fecha': r.fecha.isoformat()},
                                           format='json').status_code, status.HTTP_200_OK)

    def test_solo_los_propios(self):
        url = reverse('recordatorio-detail', args=[self.crear().data['id']])
        otro = Usuario.objects.create_user(username='b@x.co', email='b@x.co', nombre='B', password='clave-segura-123')
        self.client.force_authenticate(otro)
        self.assertEqual(self.client.get(reverse('recordatorios')).data, [])
        self.assertEqual(self.client.patch(url, {'completado': True}, format='json').status_code,
                         status.HTTP_404_NOT_FOUND)


class AvisosTest(APITestCase):
    """Los avisos llegan a su hora, quedan hasta que se confirman y al confirmar se guarda el dato."""

    def setUp(self):
        self.usuario = Usuario.objects.create_user(username='v@x.co', email='v@x.co', nombre='V',
                                                   password='clave-segura-123')
        self.client.force_authenticate(self.usuario)
        self.proceso = Proceso.objects.create(usuario=self.usuario, objetivo='ganar_musculo', fase='volumen')
        self.hoy = HOY()
        Usuario.objects.filter(pk=self.usuario.pk).update(date_joined=self.a_las(0) - timedelta(days=1))
        self.usuario.refresh_from_db()

    def a_las(self, hora, minuto=0):
        return timezone.make_aware(datetime.combine(self.hoy, time(hora, minuto)))

    def test_no_llegan_avisos_de_antes_del_registro(self):
        Usuario.objects.filter(pk=self.usuario.pk).update(date_joined=self.a_las(15))
        self.usuario.refresh_from_db()
        nuevas = notificaciones.generar(self.usuario, self.a_las(16))
        self.assertTrue(all(n.programada_para >= self.a_las(15) for n in nuevas))
        self.assertFalse(Notificacion.objects.filter(usuario=self.usuario, clave__startswith='agua:', clave__endswith=':1').exists())

    def habitos(self, **datos):
        r = self.client.patch(reverse('habitos'), datos, format='json')
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        return r.data

    def pendientes(self, tipo=None):
        avisos = Notificacion.objects.filter(usuario=self.usuario, resuelta_en__isnull=True)
        return list(avisos.filter(tipo=tipo) if tipo else avisos)

    def confirmar(self, n):
        r = self.client.post(reverse('aviso-confirmar', args=[n.id]))
        self.assertEqual(r.status_code, status.HTTP_204_NO_CONTENT, getattr(r, 'data', None))

    def test_el_agua_se_reparte_en_el_dia_y_queda_hasta_confirmarla(self):
        datos = self.habitos(agua_ml=2000, hora_levantarse='06:00', hora_dormir='22:00')
        self.assertEqual(datos['vasos_meta'], 8)
        # 8 vasos entre las 7:00 y las 21:00: uno cada 2 horas.
        notificaciones.generar(self.usuario, self.a_las(12))
        notificaciones.generar(self.usuario, self.a_las(12, 30))
        agua = self.pendientes('agua')
        self.assertEqual([timezone.localtime(n.programada_para).hour for n in agua], [7, 9, 11])

        self.confirmar(agua[0])
        self.assertEqual(len(self.pendientes('agua')), 2)
        registro = RegistroHabito.objects.get(usuario=self.usuario, tipo='agua')
        self.assertEqual(registro.notificacion, agua[0])

        # Un vaso anotado a mano cumple el aviso pendiente más viejo.
        r = self.client.post(reverse('registrar-agua'))
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertEqual([n.id for n in self.pendientes('agua')], [agua[2].id])
        self.assertEqual(self.client.get(reverse('hoy')).data['agua']['vasos'], 2)

        # Confirmar dos veces no guarda dos vasos, y lo guardado no se toca.
        self.confirmar(agua[0])
        self.assertEqual(RegistroHabito.objects.filter(tipo='agua').count(), 2)
        with self.assertRaises(DatoInmutableError):
            registro.save()

    def test_cada_toma_avisa_en_su_comida_y_guarda_los_scoops(self):
        r = self.client.post(reverse('suplementos'), {
            'tipo': 'hipercalorico', 'duracion_confirmada': True, 'scoops_porcion': 6,
            'tomas': [{'tiempo': 'onces', 'scoops': 3, 'reemplaza': {}},
                      {'tiempo': 'algo', 'scoops': 3, 'reemplaza': {}}]}, format='json')
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)

        notificaciones.generar(self.usuario, self.a_las(11))
        tomas = self.pendientes('toma')
        self.assertEqual(len(tomas), 1)
        self.assertEqual(tomas[0].titulo, 'Tómate 3 scoops de la proteína hipercalórica')

        self.confirmar(tomas[0])
        toma = RegistroHabito.objects.get(tipo='toma')
        self.assertEqual((toma.tiempo, toma.cantidad), ('onces', 3))
        hoy = self.client.get(reverse('hoy')).data
        self.assertEqual([(t['tiempo'], t['hecha']) for t in hoy['tomas']], [('onces', True), ('algo', False)])

    def test_una_toma_con_hora_avisa_a_esa_hora_y_dice_como(self):
        r = self.client.post(reverse('suplementos'), {
            'tipo': 'hipercalorico', 'duracion_confirmada': True, 'scoops_porcion': 6,
            'tomas': [{'tiempo': 'onces', 'scoops': 3, 'reemplaza': {}, 'hora': '08:45', 'nota': 'Con el desayuno'},
                      {'tiempo': 'algo', 'scoops': 3, 'reemplaza': {}}]}, format='json')
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        # Las onces son a las 10:00 por defecto: a las 9 ya avisó por la hora que dijo (08:45).
        notificaciones.generar(self.usuario, self.a_las(9))
        tomas = self.pendientes('toma')
        self.assertEqual(len(tomas), 1)
        self.assertEqual(tomas[0].programada_para, self.a_las(8, 45))
        self.assertIn('Con el desayuno', tomas[0].cuerpo)

    def test_otra_toma_avisa_a_su_hora_y_se_confirma_con_su_propia_clave(self):
        r = self.client.post(reverse('suplementos'), {
            'tipo': 'hipercalorico', 'duracion_confirmada': True, 'scoops_porcion': 6,
            'tomas': [{'tiempo': 'onces', 'scoops': 3, 'reemplaza': {}},
                      {'tiempo': 'otro', 'scoops': 3, 'hora': '21:30', 'nota': 'Antes de dormir'}]}, format='json')
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        notificaciones.generar(self.usuario, self.a_las(22))
        tomas = self.pendientes('toma')
        otra = next(n for n in tomas if n.datos['tiempo'] == 'otro-2130')
        self.assertEqual(otra.programada_para, self.a_las(21, 30))
        self.assertIn('A las 9:30 p. m.', otra.cuerpo)
        self.assertIn('Antes de dormir', otra.cuerpo)
        self.confirmar(otra)
        hoy = self.client.get(reverse('hoy')).data
        hechas = {t['tiempo']: t['hecha'] for t in hoy['tomas']}
        self.assertEqual(hechas, {'onces': False, 'otro-2130': True})

    def test_dormir_es_opcional_y_avisa_media_hora_antes(self):
        notificaciones.generar(self.usuario, self.a_las(23))
        self.assertEqual(self.pendientes('dormir'), [])

        self.habitos(hora_dormir='22:00')
        notificaciones.generar(self.usuario, self.a_las(21, 29))
        self.assertEqual(self.pendientes('dormir'), [])
        notificaciones.generar(self.usuario, self.a_las(21, 30))
        dormir = self.pendientes('dormir')[0]
        self.assertEqual(dormir.cuerpo, 'Tu hora de acostarte es a las 10:00 p. m.')
        self.confirmar(dormir)
        self.assertTrue(RegistroHabito.objects.filter(tipo='dormir').exists())

    def test_el_entreno_se_resuelve_solo_al_entrenar(self):
        rutina = Rutina.objects.create(usuario=self.usuario, nombre='Rutina')
        DiaRutina.objects.create(rutina=rutina, dia_semana=self.hoy.isoweekday())
        notificaciones.generar(self.usuario, self.a_las(8))
        self.assertEqual(len(self.pendientes('entreno')), 1)

        RegistroEntrenamiento.objects.create(usuario=self.usuario, duracion_segundos=1800)
        notificaciones.generar(self.usuario, self.a_las(9))
        self.assertEqual(self.pendientes('entreno'), [])
        self.assertEqual(Notificacion.objects.get(tipo='entreno').resolucion, 'automatica')

    def test_confirmar_desde_el_celular_con_la_firma(self):
        self.habitos(agua_ml=500)
        notificaciones.generar(self.usuario, self.a_las(23))
        n = self.pendientes('agua')[0]
        self.client.force_authenticate(None)

        r = self.client.post(reverse('aviso-confirmar-firmado'), {'firma': 'falsa'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        r = self.client.post(reverse('aviso-confirmar-firmado'), {'firma': notificaciones.firmar(n)},
                             format='json')
        self.assertEqual(r.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(len(self.pendientes('agua')), 1)

    @override_settings(VAPID_PUBLIC_KEY='pub', VAPID_PRIVATE_KEY='priv', VAPID_EMAIL='a@x.co')
    @patch('agenda.push.webpush')
    def test_se_manda_al_celular_una_vez(self, webpush):
        SuscripcionPush.objects.create(usuario=self.usuario, endpoint='https://push.x/1', p256dh='k', auth='a')
        SuscripcionPush.objects.create(usuario=self.usuario, endpoint='https://push.x/2', p256dh='k', auth='a')
        Habitos.objects.create(usuario=self.usuario, agua_ml=250)
        # El vaso único queda una hora después de levantarse (6:00 por defecto).
        hora = timezone.make_aware(datetime.combine(self.hoy, time(7, 30)))

        vencida = MagicMock(status_code=410)
        webpush.side_effect = [None, WebPushException('vencida', response=vencida)]
        with patch('django.utils.timezone.now', return_value=hora):
            call_command('enviar_avisos')
            call_command('enviar_avisos')
        self.assertEqual(webpush.call_count, 2)
        self.assertEqual(SuscripcionPush.objects.count(), 1)
        enviado = json.loads(webpush.call_args.kwargs['data'])
        self.assertEqual((enviado['titulo'], enviado['accion']), ('Toma un vaso de agua', 'Ya lo tomé'))
