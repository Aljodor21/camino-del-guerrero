from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from users.models import Usuario

from . import fcm, notificaciones, push
from .models import Notificacion, TokenCelular

WEBVIEW = ('Mozilla/5.0 (Linux; Android 13; SM-A546E Build/TP1A.220624.014; wv) AppleWebKit/537.36 '
           '(KHTML, like Gecko) Version/4.0 Chrome/130.0.0.0 Mobile Safari/537.36')
TOKEN = 't' * 60


def respuesta(codigo=200, estado=''):
    r = MagicMock(status_code=codigo, ok=codigo < 400)
    r.json.return_value = {'error': {'status': estado}} if estado else {}
    return r


class FirebaseTest(APITestCase):
    def setUp(self):
        self.usuario = Usuario.objects.create_user(username='f@x.co', email='f@x.co', nombre='F',
                                                   password='clave-segura-123')
        self.otro = Usuario.objects.create_user(username='o@x.co', email='o@x.co', nombre='O',
                                                password='clave-segura-123')
        self.client.force_authenticate(self.usuario)
        self.aviso = Notificacion.objects.create(
            usuario=self.usuario, tipo='agua', clave=f'agua:{timezone.localdate()}:1', fecha=timezone.localdate(),
            programada_para=timezone.now() - timedelta(minutes=1), titulo='Toma un vaso de agua',
            cuerpo='Un vaso de 500 ml.', datos={'vaso': 1})

    def registrar(self, token=TOKEN):
        return self.client.post(reverse('push-celular'), {'token': token}, format='json',
                                HTTP_USER_AGENT=WEBVIEW, HTTP_X_APP_VERSION='1.0.14')

    def test_el_celular_se_registra_con_su_modelo_y_version(self):
        self.assertEqual(self.registrar().status_code, status.HTTP_204_NO_CONTENT)
        t = TokenCelular.objects.get()
        self.assertEqual((t.usuario, t.dispositivo, t.version_app), (self.usuario, 'SM-A546E', '1.0.14'))
        self.registrar()   # repetirlo no lo duplica
        self.assertEqual(TokenCelular.objects.count(), 1)

    def test_un_token_corto_o_ausente_se_rechaza(self):
        for datos in ({}, {'token': 'x'}, {'token': 5}):
            r = self.client.post(reverse('push-celular'), datos, format='json')
            self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_si_el_celular_pasa_a_otra_cuenta_deja_de_ser_de_la_anterior(self):
        self.registrar()
        self.client.force_authenticate(self.otro)
        self.registrar()
        self.assertEqual(TokenCelular.objects.get().usuario, self.otro)

    def test_solo_se_quita_el_propio(self):
        self.registrar()
        self.client.force_authenticate(self.otro)
        self.client.delete(reverse('push-celular'), {'token': TOKEN}, format='json')
        self.assertEqual(TokenCelular.objects.count(), 1)
        self.client.force_authenticate(self.usuario)
        self.client.delete(reverse('push-celular'), {'token': TOKEN}, format='json')
        self.assertEqual(TokenCelular.objects.count(), 0)

    def test_dice_si_el_servidor_manda_por_firebase(self):
        self.assertFalse(self.client.get(reverse('push-celular')).data['disponible'])
        with override_settings(FIREBASE_CREDENCIALES_B64='x'):
            self.assertTrue(self.client.get(reverse('push-celular')).data['disponible'])

    @override_settings(FIREBASE_CREDENCIALES_B64='x')
    def test_el_aviso_sale_por_firebase_con_su_canal_y_ruta(self):
        TokenCelular.objects.create(usuario=self.usuario, token=TOKEN)
        sesion = MagicMock()
        sesion.post.return_value = respuesta()
        with patch.object(fcm, '_sesion', return_value=(sesion, 'mi-proyecto')):
            self.assertEqual(fcm.enviar(self.aviso), 1)
        url = sesion.post.call_args.args[0]
        mensaje = sesion.post.call_args.kwargs['json']['message']
        self.assertEqual(url, 'https://fcm.googleapis.com/v1/projects/mi-proyecto/messages:send')
        self.assertEqual(mensaje['token'], TOKEN)
        # Solo datos: así la app arma la notificación con su botón, esté abierta o cerrada.
        self.assertNotIn('notification', mensaje)
        self.assertEqual(mensaje['android']['priority'], 'HIGH')
        datos = mensaje['data']
        self.assertEqual((datos['titulo'], datos['ruta'], datos['clave'], datos['tipo']),
                         ('Toma un vaso de agua', '/avisos', self.aviso.clave, 'agua'))
        self.assertEqual(datos['accion'], 'Ya lo tomé')
        # La firma del botón confirma ese aviso sin sesión.
        self.assertEqual(notificaciones.desde_firma(datos['firma']), self.aviso)

    @override_settings(FIREBASE_CREDENCIALES_B64='x')
    def test_el_envio_general_usa_firebase(self):
        TokenCelular.objects.create(usuario=self.usuario, token=TOKEN)
        sesion = MagicMock()
        sesion.post.return_value = respuesta()
        with patch.object(fcm, '_sesion', return_value=(sesion, 'p')):
            push.enviar(self.aviso)
        self.assertEqual(sesion.post.call_count, 1)

    @override_settings(FIREBASE_CREDENCIALES_B64='x')
    def test_un_celular_que_ya_no_existe_se_borra(self):
        TokenCelular.objects.create(usuario=self.usuario, token=TOKEN)
        sesion = MagicMock()
        sesion.post.return_value = respuesta(404, 'NOT_FOUND')
        with patch.object(fcm, '_sesion', return_value=(sesion, 'p')):
            self.assertEqual(fcm.enviar(self.aviso), 0)
        self.assertFalse(TokenCelular.objects.exists())

    @override_settings(FIREBASE_CREDENCIALES_B64='x')
    def test_un_error_de_firebase_no_borra_el_celular_ni_tumba_el_envio(self):
        TokenCelular.objects.create(usuario=self.usuario, token=TOKEN)
        sesion = MagicMock()
        sesion.post.side_effect = [respuesta(500, 'INTERNAL')]
        with patch.object(fcm, '_sesion', return_value=(sesion, 'p')):
            self.assertEqual(fcm.enviar(self.aviso), 0)
        self.assertTrue(TokenCelular.objects.exists())

    def test_sin_firebase_configurado_no_se_manda_nada(self):
        TokenCelular.objects.create(usuario=self.usuario, token=TOKEN)
        with patch.object(fcm, '_sesion') as sesion:
            self.assertEqual(fcm.enviar(self.aviso), 0)
        sesion.assert_not_called()

    @override_settings(FIREBASE_CREDENCIALES_B64='x')
    def test_la_prueba_llega_solo_si_el_celular_esta_registrado(self):
        r = self.client.post(reverse('push-celular-probar'))
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        TokenCelular.objects.create(usuario=self.usuario, token=TOKEN)
        sesion = MagicMock()
        sesion.post.return_value = respuesta()
        with patch.object(fcm, '_sesion', return_value=(sesion, 'p')):
            r = self.client.post(reverse('push-celular-probar'))
        self.assertEqual(r.data, {'enviadas': 1})
        datos = sesion.post.call_args.kwargs['json']['message']['data']
        self.assertEqual((datos['titulo'], datos.get('accion', '')), ('Prueba de notificaciones', ''))

    @override_settings(FIREBASE_CREDENCIALES_B64='x')
    def test_la_prueba_con_credenciales_malas_responde_cero_sin_romper(self):
        TokenCelular.objects.create(usuario=self.usuario, token=TOKEN)
        with patch.object(fcm, '_sesion', side_effect=ValueError('credenciales inválidas')):
            r = self.client.post(reverse('push-celular-probar'))
        self.assertEqual((r.status_code, r.data), (status.HTTP_200_OK, {'enviadas': 0}))


class WebPushConLaAppTest(FirebaseTest):
    """Quien ya tiene la app instalada no recibe lo mismo en el navegador."""

    @override_settings(VAPID_PUBLIC_KEY='pub', VAPID_PRIVATE_KEY='priv', VAPID_EMAIL='a@b.co')
    def test_con_la_app_registrada_el_navegador_no_recibe_el_aviso(self):
        from .models import SuscripcionPush
        SuscripcionPush.objects.create(usuario=self.usuario, endpoint='https://push.example/x', p256dh='a', auth='b')
        with patch('agenda.push.webpush') as web:
            push.enviar_web(self.aviso)
            self.assertEqual(web.call_count, 1)        # sin la app, sí le llega al navegador
            TokenCelular.objects.create(usuario=self.usuario, token=TOKEN)
            push.enviar_web(self.aviso)
            self.assertEqual(web.call_count, 1)        # con la app, ya no

    @override_settings(VAPID_PUBLIC_KEY='pub', VAPID_PRIVATE_KEY='priv', VAPID_EMAIL='a@b.co')
    def test_el_navegador_sabe_si_ya_tienes_la_app(self):
        self.assertFalse(self.client.get(reverse('avisos-push')).data['en_la_app'])
        TokenCelular.objects.create(usuario=self.usuario, token=TOKEN)
        self.assertTrue(self.client.get(reverse('avisos-push')).data['en_la_app'])
