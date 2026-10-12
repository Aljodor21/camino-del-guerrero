"""Última versión de la app de Android.

La pantalla de descarga necesita saber la versión, el peso y la fecha del último release. Se lee
aquí, en el servidor, y no desde el navegador: así no depende de que el sitio deje al navegador
hablar con GitHub (un `Content-Security-Policy: connect-src 'self'` puesto por Cloudflare lo
impedía). Se guarda unos minutos para no pasar el límite de consultas de GitHub.
"""
import fcntl
import logging
import os
import threading
from pathlib import Path

import requests
from django.conf import settings
from django.core.cache import cache
from django.http import FileResponse, HttpResponse, HttpResponseRedirect
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

log = logging.getLogger(__name__)

ARCHIVO = 'camino-del-guerrero.apk'
CLAVE_CACHE = 'app_movil:ultima'
MINUTOS_CACHE = 10


def _url_descarga():
    return f'https://github.com/{settings.APK_REPO}/releases/latest/download/{ARCHIVO}'


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
        'url': _url_descarga(),
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
            if datos.get('disponible'):
                # La copia se baja en segundo plano para que el clic de descargar ya la encuentre lista.
                threading.Thread(target=_asegurar_copia, args=(datos,), daemon=True).start()
        return Response(datos)


# ── La descarga se sirve desde nuestro dominio ──────────────────────────────────────────────────
# El navegador no baja "en el acto" un archivo que está en otro dominio (GitHub): salta de página.
# Por eso el servidor guarda una copia de la última versión y la entrega él mismo (nginx, con
# X-Accel-Redirect: reanuda y muestra el avance sin ocupar a Django).

def _carpeta():
    carpeta = Path(settings.APK_DIR)
    carpeta.mkdir(parents=True, exist_ok=True)
    return carpeta


def _asegurar_copia(datos):
    """Deja en disco el APK de esa versión (bajándolo si hace falta) y devuelve su ruta, o None."""
    destino = _carpeta() / f"camino-del-guerrero-{datos['version']}.apk"
    if destino.exists() and destino.stat().st_size == datos['bytes']:
        return destino
    with open(_carpeta() / '.bloqueo', 'w') as candado:
        fcntl.flock(candado, fcntl.LOCK_EX)  # una sola descarga a la vez, aunque lleguen varias peticiones
        if destino.exists() and destino.stat().st_size == datos['bytes']:
            return destino
        temporal = destino.with_suffix('.apk.parcial')
        try:
            with requests.get(datos['url'], stream=True, timeout=(6, 60)) as r:
                r.raise_for_status()
                with open(temporal, 'wb') as f:
                    for trozo in r.iter_content(chunk_size=1 << 20):
                        f.write(trozo)
            if temporal.stat().st_size != datos['bytes']:
                raise ValueError('el archivo bajado no tiene el tamaño del release')
            os.replace(temporal, destino)
        except (requests.RequestException, OSError, ValueError):
            log.warning('No se pudo guardar la copia del APK', exc_info=True)
            temporal.unlink(missing_ok=True)
            return None
        for vieja in _carpeta().glob('camino-del-guerrero-*.apk'):
            if vieja != destino:
                vieja.unlink(missing_ok=True)
    return destino


class DescargarApk(APIView):
    """GET: baja la última versión desde nuestro propio dominio. Es pública."""
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        datos = cache.get(CLAVE_CACHE)
        if datos is None:
            try:
                datos = _consultar_github()
                cache.set(CLAVE_CACHE, datos, MINUTOS_CACHE * 60)
            except (requests.RequestException, KeyError, ValueError):
                datos = None
        copia = _asegurar_copia(datos) if datos and datos.get('disponible') else None
        if copia is None:
            # Sin copia (GitHub caído o aún no hay release): se manda al enlace de siempre.
            return HttpResponseRedirect(_url_descarga())
        cabeceras = {'Content-Disposition': 'attachment; filename="camino-del-guerrero.apk"',
                     'Cache-Control': 'no-cache'}
        if settings.APK_ACCEL_NGINX:
            r = HttpResponse(content_type='application/vnd.android.package-archive')
            r['X-Accel-Redirect'] = f'/apk-cache/{copia.name}'
        else:  # desarrollo y pruebas, sin nginx adelante
            r = FileResponse(open(copia, 'rb'), content_type='application/vnd.android.package-archive')
        for k, v in cabeceras.items():
            r[k] = v
        return r
