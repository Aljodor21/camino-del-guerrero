from datetime import timedelta

from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from core.exceptions import DatoInmutableError
from users.models import Rol, Usuario

from . import agente
from .models import Evento

PIXEL = ('Mozilla/5.0 (Linux; Android 14; Pixel 8 Build/AP1A.240905.015) AppleWebKit/537.36 '
         '(KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36')
WEBVIEW = ('Mozilla/5.0 (Linux; Android 13; SM-A546E Build/TP1A.220624.014; wv) AppleWebKit/537.36 '
           '(KHTML, like Gecko) Version/4.0 Chrome/130.0.0.0 Mobile Safari/537.36')
ESCRITORIO = ('Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) '
              'Chrome/130.0.0.0 Safari/537.36')


class InterpretarTest(APITestCase):
    def test_celular_android_en_navegador(self):
        info = agente.interpretar(PIXEL)
        self.assertEqual((info['cliente'], info['sistema'], info['dispositivo'], info['navegador']),
                         ('web', 'Android 14', 'Pixel 8', 'Chrome 130'))

    def test_la_app_instalada_es_un_webview(self):
        info = agente.interpretar(WEBVIEW)
        self.assertEqual((info['cliente'], info['dispositivo'], info['navegador']), ('app', 'SM-A546E', 'App'))

    def test_computador(self):
        info = agente.interpretar(ESCRITORIO)
        self.assertEqual((info['sistema'], info['dispositivo']), ('Linux', 'Computador'))

    def test_la_app_se_declara_sola(self):
        self.assertEqual(agente.interpretar(ESCRITORIO, 'app')['cliente'], 'app')

    def test_la_consulta_tapa_lo_sensible(self):
        self.assertEqual(agente.consulta_limpia('desde=2026-10-01&token=abc&firma=x'),
                         'desde=2026-10-01&token=***&firma=***')


class AuditoriaTest(APITestCase):
    def setUp(self):
        self.rol_admin = Rol.objects.create(nombre='admin')
        self.persona = Usuario.objects.create_user(username='p@x.co', email='p@x.co', nombre='P',
                                                   password='clave-segura-123')
        self.admin = Usuario.objects.create_user(username='a@x.co', email='a@x.co', nombre='A',
                                                 password='clave-segura-123', rol=self.rol_admin)

    def entrar(self, usuario):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(usuario).access_token}')

    def test_cada_consulta_deja_su_huella_con_quien_y_desde_donde(self):
        self.entrar(self.persona)
        r = self.client.get(reverse('hoy'), HTTP_USER_AGENT=WEBVIEW, HTTP_X_APP_VERSION='1.0.12',
                            HTTP_CF_CONNECTING_IP='190.1.2.3')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        e = Evento.objects.get()
        self.assertEqual((e.usuario, e.correo, e.metodo, e.estado), (self.persona, 'p@x.co', 'GET', 200))
        self.assertEqual((e.ruta, e.camino), ('api/agenda/hoy/', '/api/agenda/hoy/'))
        self.assertEqual((e.cliente, e.dispositivo, e.sistema, e.version_app, e.ip),
                         ('app', 'SM-A546E', 'Android 13', '1.0.12', '190.1.2.3'))

    def test_la_ruta_agrupa_aunque_cambie_el_id_y_no_se_guarda_el_contenido(self):
        self.entrar(self.persona)
        self.client.post('/api/agenda/avisos/99/confirmar/', {'nota': 'secreto'}, format='json')
        e = Evento.objects.get()
        self.assertEqual(e.ruta, 'api/agenda/avisos/<int:pk>/confirmar/')
        self.assertEqual(e.estado, 404)
        self.assertNotIn('secreto', ' '.join(str(v) for v in vars(e).values()))

    def test_sin_sesion_queda_como_anonimo_y_los_sondeos_se_marcan(self):
        self.client.get(reverse('avisos'), HTTP_X_SEGUNDO_PLANO='1')
        e = Evento.objects.get()
        self.assertIsNone(e.usuario)
        self.assertEqual(e.estado, 401)
        self.assertTrue(e.automatico)

    def test_no_se_audita_a_si_misma(self):
        self.entrar(self.admin)
        self.client.get(reverse('auditoria-resumen'))
        self.assertFalse(Evento.objects.exists())

    def test_la_app_avisa_la_pantalla_sin_su_contenido(self):
        self.entrar(self.persona)
        r = self.client.post(reverse('auditoria-pantalla'), {'ruta': '/avisos?seccion=cumplimiento'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_204_NO_CONTENT)
        e = Evento.objects.filter(tipo='pantalla').get()
        self.assertEqual((e.ruta, e.correo), ('/avisos', 'p@x.co'))
        self.assertEqual(self.client.post(reverse('auditoria-pantalla'), {'ruta': 'avisos'}, format='json')
                         .status_code, status.HTTP_400_BAD_REQUEST)

    def test_solo_el_administrador_ve_la_auditoria(self):
        self.entrar(self.persona)
        for nombre in ('auditoria-eventos', 'auditoria-resumen'):
            self.assertEqual(self.client.get(reverse(nombre)).status_code, status.HTTP_403_FORBIDDEN)
        self.entrar(self.admin)
        for nombre in ('auditoria-eventos', 'auditoria-resumen'):
            self.assertEqual(self.client.get(reverse(nombre)).status_code, status.HTTP_200_OK)

    def test_resumen_y_filtros(self):
        self.entrar(self.persona)
        self.client.get(reverse('hoy'), HTTP_USER_AGENT=WEBVIEW, HTTP_X_APP_VERSION='1.0.12')
        self.client.get(reverse('hoy'), HTTP_USER_AGENT=ESCRITORIO)
        self.client.get(reverse('avisos'), HTTP_X_SEGUNDO_PLANO='1')
        self.entrar(self.admin)
        resumen = self.client.get(reverse('auditoria-resumen')).data
        self.assertEqual((resumen['consultas'], resumen['personas']), (2, 1))   # sin sondeos
        self.assertEqual({d['dispositivo'] for d in resumen['por_dispositivo']}, {'SM-A546E', 'Computador'})
        self.assertEqual(resumen['versiones_app'][0]['version_app'], '1.0.12')
        r = self.client.get(reverse('auditoria-eventos'), {'cliente': 'app'}).data
        self.assertEqual(len(r['resultados']), 1)
        todos = self.client.get(reverse('auditoria-eventos'), {'automaticos': '1'}).data
        self.assertEqual(len(todos['resultados']), 3)

    def test_se_pagina_con_antes(self):
        for i in range(105):
            Evento.objects.create(ruta=f'api/x/{i}/', camino=f'/api/x/{i}/')
        self.entrar(self.admin)
        primera = self.client.get(reverse('auditoria-eventos')).data
        self.assertEqual(len(primera['resultados']), 100)
        segunda = self.client.get(reverse('auditoria-eventos'), {'antes': primera['siguiente']}).data
        self.assertEqual(len(segunda['resultados']), 5)
        self.assertIsNone(segunda['siguiente'])

    def test_no_se_edita_y_la_limpieza_borra_lo_viejo(self):
        e = Evento.objects.create(ruta='api/x/')
        with self.assertRaises(DatoInmutableError):
            e.estado = 500
            e.save()
        Evento.objects.create(ruta='api/viejo/', momento=timezone.now() - timedelta(days=120))
        call_command('limpiar_auditoria', verbosity=0)
        self.assertEqual(list(Evento.objects.values_list('ruta', flat=True)), ['api/x/'])


class InicioDeSesionTest(APITestCase):
    def test_se_sabe_quien_entro_y_quien_fallo(self):
        Usuario.objects.create_user(username='p@x.co', email='p@x.co', nombre='P', password='clave-segura-123')
        self.client.post(reverse('login'), {'email': 'p@x.co', 'password': 'clave-segura-123'}, format='json',
                         HTTP_USER_AGENT=WEBVIEW)
        self.client.post(reverse('login'), {'email': 'otro@x.co', 'password': 'mala'}, format='json')
        entro, fallo = Evento.objects.order_by('id')
        self.assertEqual((entro.estado, entro.correo, entro.usuario.email), (200, 'p@x.co', 'p@x.co'))
        self.assertEqual((fallo.estado, fallo.correo, fallo.usuario), (401, 'otro@x.co', None))
        self.assertNotIn('mala', ' '.join(str(v) for v in vars(fallo).values()))
