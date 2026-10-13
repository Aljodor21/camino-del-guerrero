"""Avisos a la app instalada por Firebase Cloud Messaging (API HTTP v1).

El servidor entrega el aviso a Google con la clave de la cuenta de servicio de Firebase y
Google lo lleva al celular, aunque la app esté cerrada. Firebase solo transporta el aviso:
los datos siguen en nuestro servidor.
"""
import base64
import json
import logging
from functools import lru_cache

from django.conf import settings
from google.auth.transport.requests import AuthorizedSession
from google.oauth2 import service_account

from . import notificaciones

logger = logging.getLogger(__name__)
ALCANCE = 'https://www.googleapis.com/auth/firebase.messaging'
URL = 'https://fcm.googleapis.com/v1/projects/{proyecto}/messages:send'
TTL = '7200s'


def configurado():
    return bool(settings.FIREBASE_CREDENCIALES_B64)


@lru_cache(maxsize=1)
def _sesion():
    """(sesión autenticada, id del proyecto). Se arma una vez y renueva su pase sola."""
    info = json.loads(base64.b64decode(settings.FIREBASE_CREDENCIALES_B64))
    credenciales = service_account.Credentials.from_service_account_info(info, scopes=[ALCANCE])
    return AuthorizedSession(credenciales), info['project_id']


def _mensaje(token, datos):
    """Un mensaje solo de datos: la app arma la notificación (con su botón de confirmar), con la
    app abierta o cerrada. Con «notification» el sistema la mostraría sin botones."""
    return {'message': {
        'token': token,
        'data': {k: str(v) for k, v in datos.items()},
        'android': {'priority': 'HIGH', 'ttl': TTL},
    }}


def _mandar(token_celular, mensaje):
    """True si Google lo recibió. Un token que ya no existe (app desinstalada) se borra."""
    sesion, proyecto = _sesion()
    r = sesion.post(URL.format(proyecto=proyecto), json=mensaje, timeout=10)
    if r.ok:
        return True
    estado = ''
    try:
        estado = r.json().get('error', {}).get('status', '')
    except ValueError:
        pass
    if r.status_code == 404 or estado == 'UNREGISTERED':
        token_celular.delete()
    else:
        logger.warning('Firebase no aceptó el aviso (%s %s)', r.status_code, estado)
    return False


def enviar(n):
    """Manda el aviso a cada celular del usuario. Devuelve cuántos lo recibieron."""
    if not configurado():
        return 0
    enviados = 0
    for t in n.usuario.tokens_celular.all():
        try:
            datos = {'id': n.id, 'tipo': n.tipo, 'clave': n.clave, 'titulo': n.titulo,
                     'cuerpo': notificaciones.cuerpo_de(n), 'ruta': notificaciones.url_de(n),
                     'accion': notificaciones.accion_de(n), 'firma': notificaciones.firmar(n)}
            enviados += _mandar(t, _mensaje(t.token, datos))
        except Exception:
            logger.exception('Falló el envío por Firebase del aviso %s', n.id)
    return enviados


def enviar_prueba(usuario):
    """Una notificación de prueba a los celulares del usuario. Devuelve cuántos la recibieron."""
    if not configurado():
        return 0
    enviados = 0
    for t in usuario.tokens_celular.all():
        mensaje = _mensaje(t.token, {
            'tipo': 'prueba', 'clave': 'prueba', 'titulo': 'Prueba de notificaciones',
            'cuerpo': 'Si ves esto, los avisos te van a llegar a este celular.', 'ruta': '/avisos'})
        try:
            enviados += _mandar(t, mensaje)
        except Exception:
            logger.exception('Falló la notificación de prueba por Firebase')
    return enviados
