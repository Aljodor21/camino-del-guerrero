import logging
import time

from django.urls import Resolver404, resolve

from . import agente
from .models import Evento

log = logging.getLogger(__name__)

# Lo que no vale la pena guardar.
IGNORAR = ('/api/auditoria/',)


def ip_de(request):
    """La IP real de quien consulta: detrás de Cloudflare y nginx llega en las cabeceras."""
    meta = request.META
    candidata = (meta.get('HTTP_CF_CONNECTING_IP') or meta.get('HTTP_X_REAL_IP')
                 or (meta.get('HTTP_X_FORWARDED_FOR') or '').split(',')[0].strip()
                 or meta.get('REMOTE_ADDR'))
    return candidata or None


def datos_del_cliente(request):
    """Lo que dice el dispositivo: sistema, modelo, navegador, y la app con su versión."""
    ua = request.META.get('HTTP_USER_AGENT', '')
    info = agente.interpretar(ua, request.META.get('HTTP_X_CLIENTE', ''))
    return {**info, 'agente': ua[:300], 'version_app': request.META.get('HTTP_X_APP_VERSION', '')[:20],
            'ip': ip_de(request)}


def registrar(request, **campos):
    """Guarda una huella sin que un fallo de auditoría tumbe la consulta."""
    usuario = getattr(request, 'user', None)
    if usuario is None or not usuario.is_authenticated:
        usuario = getattr(request, 'auditoria_usuario', None)   # al iniciar sesión aún no hay pase
    correo = getattr(usuario, 'email', '') or getattr(request, 'auditoria_correo', '')
    try:
        Evento.objects.create(usuario=usuario, correo=correo,
                              **datos_del_cliente(request), **campos)
    except Exception:
        log.exception('No se pudo guardar la huella de auditoría')


class AuditoriaMiddleware:
    """Deja una huella por cada consulta a la API: quién, qué, el resultado y el dispositivo.

    El usuario lo resuelve DRF al autenticar con el pase; por eso se lee después de la respuesta."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path
        if not path.startswith('/api/') or path.startswith(IGNORAR) or request.method == 'OPTIONS':
            return self.get_response(request)
        inicio = time.monotonic()
        respuesta = self.get_response(request)
        try:
            ruta = resolve(path).route
        except Resolver404:
            ruta = '(no existe)'
        registrar(
            request, tipo='api', metodo=request.method, ruta=ruta[:200], camino=path[:300],
            consulta=agente.consulta_limpia(request.META.get('QUERY_STRING', '')),
            estado=respuesta.status_code, duracion_ms=round((time.monotonic() - inicio) * 1000),
            automatico=request.META.get('HTTP_X_SEGUNDO_PLANO') == '1')
        return respuesta
