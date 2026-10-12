import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import requests
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

CONTENIDO = b'PK\x03\x04' + b'x' * 996  # 1000 bytes, un "APK" de mentira


def _respuesta(estado=200, json=None):
    r = MagicMock(status_code=estado)
    r.json.return_value = json or {}
    r.raise_for_status.side_effect = None if estado < 400 else requests.HTTPError(str(estado))
    return r


def _descarga(contenido=CONTENIDO):
    """Lo que devuelve requests.get(..., stream=True) usado como `with`."""
    r = MagicMock()
    r.__enter__.return_value = r
    r.raise_for_status.side_effect = None
    r.iter_content.return_value = [contenido[:500], contenido[500:]]
    return r


RELEASE = {'tag_name': 'v1.0.4', 'published_at': '2026-10-12T17:30:00Z',
           'assets': [{'name': 'camino-del-guerrero.apk', 'size': len(CONTENIDO)}]}


@override_settings(APK_ACCEL_NGINX=False)
class AppMovilTest(TestCase):
    def setUp(self):
        cache.clear()
        self.carpeta = tempfile.TemporaryDirectory()
        self.addCleanup(self.carpeta.cleanup)
        self.ajustes = override_settings(APK_DIR=self.carpeta.name)
        self.ajustes.enable()
        self.addCleanup(self.ajustes.disable)
        # La versión intenta dejar lista la copia en un hilo: en las pruebas no se lanza.
        parche = patch('core.app_movil.threading.Thread')
        parche.start()
        self.addCleanup(parche.stop)

    # ── Versión ──────────────────────────────────────────────────────────────
    @patch('core.app_movil.requests.get')
    def test_version_devuelve_datos_sin_iniciar_sesion_y_usa_cache(self, get):
        get.return_value = _respuesta(json=RELEASE)
        r = self.client.get(reverse('app-version'))
        self.assertEqual(r.status_code, 200)
        self.assertEqual((r.json()['version'], r.json()['bytes']), ('1.0.4', len(CONTENIDO)))
        self.client.get(reverse('app-version'))
        self.assertEqual(get.call_count, 1)

    @patch('core.app_movil.requests.get')
    def test_version_sin_release(self, get):
        get.return_value = _respuesta(404)
        self.assertEqual(self.client.get(reverse('app-version')).json(), {'disponible': False})

    @patch('core.app_movil.requests.get', side_effect=requests.ConnectionError('sin red'))
    def test_version_si_github_no_responde_no_se_cae(self, _get):
        r = self.client.get(reverse('app-version'))
        self.assertEqual(r.status_code, 200)
        self.assertIsNone(r.json()['disponible'])

    # ── Descarga ─────────────────────────────────────────────────────────────
    @patch('core.app_movil.requests.get')
    def test_la_descarga_sale_de_nuestro_dominio_y_guarda_una_copia(self, get):
        get.side_effect = [_respuesta(json=RELEASE), _descarga()]
        r = self.client.get(reverse('app-descargar'))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(b''.join(r.streaming_content), CONTENIDO)
        self.assertEqual(r['Content-Type'], 'application/vnd.android.package-archive')
        self.assertIn('attachment', r['Content-Disposition'])
        self.assertEqual(len(list(Path(self.carpeta.name).glob('*.apk'))), 1)
        # La segunda vez ya hay copia: no vuelve a bajarse.
        llamadas = get.call_count
        self.client.get(reverse('app-descargar'))
        self.assertEqual(get.call_count, llamadas)

    @override_settings(APK_ACCEL_NGINX=True)
    @patch('core.app_movil.requests.get')
    def test_detras_de_nginx_se_le_pasa_el_archivo_con_x_accel(self, get):
        get.side_effect = [_respuesta(json=RELEASE), _descarga()]
        r = self.client.get(reverse('app-descargar'))
        self.assertEqual(r['X-Accel-Redirect'], '/apk-cache/camino-del-guerrero-1.0.4.apk')
        self.assertEqual(r.content, b'')

    @patch('core.app_movil.requests.get')
    def test_si_el_archivo_no_tiene_el_tamano_del_release_se_descarta_y_se_manda_a_github(self, get):
        get.side_effect = [_respuesta(json=RELEASE), _descarga(b'corto')]
        r = self.client.get(reverse('app-descargar'))
        self.assertEqual(r.status_code, 302)
        self.assertIn('github.com', r['Location'])
        self.assertEqual(list(Path(self.carpeta.name).glob('*.apk*')), [])

    @patch('core.app_movil.requests.get', side_effect=requests.ConnectionError('sin red'))
    def test_si_github_no_responde_se_manda_al_enlace_de_siempre(self, _get):
        r = self.client.get(reverse('app-descargar'))
        self.assertEqual(r.status_code, 302)
        self.assertTrue(r['Location'].endswith('/releases/latest/download/camino-del-guerrero.apk'))

    @patch('core.app_movil.requests.get')
    def test_una_version_nueva_reemplaza_la_copia_vieja(self, get):
        vieja = Path(self.carpeta.name) / 'camino-del-guerrero-1.0.3.apk'
        vieja.write_bytes(b'viejo')
        get.side_effect = [_respuesta(json=RELEASE), _descarga()]
        self.client.get(reverse('app-descargar'))
        self.assertFalse(vieja.exists())
        self.assertTrue((Path(self.carpeta.name) / 'camino-del-guerrero-1.0.4.apk').exists())
