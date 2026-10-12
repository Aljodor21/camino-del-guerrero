from unittest.mock import MagicMock, patch

import requests
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse


def _respuesta(estado=200, json=None):
    r = MagicMock(status_code=estado)
    r.json.return_value = json or {}
    r.raise_for_status.side_effect = None if estado < 400 else requests.HTTPError(str(estado))
    return r


RELEASE = {'tag_name': 'v1.0.4', 'published_at': '2026-10-12T17:30:00Z',
           'assets': [{'name': 'camino-del-guerrero.apk', 'size': 24904369}]}


class UltimaVersionApkTest(TestCase):
    def setUp(self):
        cache.clear()

    @patch('core.app_movil.requests.get')
    def test_devuelve_version_peso_fecha_y_enlace_sin_iniciar_sesion(self, get):
        get.return_value = _respuesta(json=RELEASE)
        r = self.client.get(reverse('app-version'))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['version'], '1.0.4')
        self.assertEqual(r.json()['bytes'], 24904369)
        self.assertTrue(r.json()['url'].endswith('/releases/latest/download/camino-del-guerrero.apk'))
        # Segunda llamada: sale de la caché, no vuelve a GitHub.
        self.client.get(reverse('app-version'))
        self.assertEqual(get.call_count, 1)

    @patch('core.app_movil.requests.get')
    def test_sin_release_dice_que_no_hay(self, get):
        get.return_value = _respuesta(404)
        self.assertEqual(self.client.get(reverse('app-version')).json(), {'disponible': False})

    @patch('core.app_movil.requests.get', side_effect=requests.ConnectionError('sin red'))
    def test_si_github_no_responde_no_se_cae(self, _get):
        r = self.client.get(reverse('app-version'))
        self.assertEqual(r.status_code, 200)
        self.assertIsNone(r.json()['disponible'])
