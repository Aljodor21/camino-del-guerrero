"""Última versión de la app de Android.

La pantalla de descarga necesita saber la versión, el peso y la fecha del último release. Se lee
aquí, en el servidor, y no desde el navegador: así no depende de que el sitio deje al navegador
hablar con GitHub (un `Content-Security-Policy: connect-src 'self'` puesto por Cloudflare lo
impedía). Se guarda unos minutos para no pasar el límite de consultas de GitHub.
"""
import logging

import requests
from django.conf import settings
from django.core.cache import cache
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

log = logging.getLogger(__name__)

ARCHIVO = 'camino-del-guerrero.apk'
CLAVE_CACHE = 'app_movil:ultima'
MINUTOS_CACHE = 10


def _consultar_github():
    r = requests.get(
        f'https://api.github.com/repos/{settings.APK_REPO}/releases/latest',
        headers={'Accept': 'application/vnd.github+json', 'User-Agent': 'camino-del-guerrero'},
        timeout=6,
    )
    if r.status_code == 404:
        return {'disponible': False}
    r.raise_for_status()
    datos = r.json()
    apk = next((a for a in datos.get('assets', []) if a.get('name') == ARCHIVO), None)
    if apk is None:
        return {'disponible': False}
    return {
        'disponible': True,
        'version': str(datos['tag_name']).lstrip('v'),
        'publicada': datos['published_at'],
        'bytes': apk['size'],
        'url': f'https://github.com/{settings.APK_REPO}/releases/latest/download/{ARCHIVO}',
    }


class UltimaVersionApk(APIView):
    """GET: la última versión publicada. Es pública: son datos de un repositorio público."""
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        datos = cache.get(CLAVE_CACHE)
        if datos is None:
            try:
                datos = _consultar_github()
            except (requests.RequestException, KeyError, ValueError):
                log.warning('No se pudo consultar el último release de la app', exc_info=True)
                # Sin respuesta de GitHub: el enlace de descarga sigue sirviendo, solo faltan los datos.
                return Response({'disponible': None}, status=200)
            cache.set(CLAVE_CACHE, datos, MINUTOS_CACHE * 60)
        return Response(datos)
