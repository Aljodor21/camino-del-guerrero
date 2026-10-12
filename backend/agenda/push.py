"""Envío de los avisos al celular (web push con llaves VAPID)."""
import json
import logging

from django.conf import settings
from pywebpush import WebPushException, webpush

from . import notificaciones

logger = logging.getLogger(__name__)
TTL = 2 * 3600


def configurado():
    return bool(settings.VAPID_PUBLIC_KEY and settings.VAPID_PRIVATE_KEY and settings.VAPID_EMAIL)


def contenido(n):
    return {
        'id': n.id,
        'tipo': n.tipo,
        'momento': n.programada_para.isoformat(),
        'titulo': n.titulo,
        'cuerpo': notificaciones.cuerpo_de(n),
        'accion': notificaciones.accion_de(n),
        'firma': notificaciones.firmar(n),
        'url': notificaciones.url_de(n),
    }


def enviar(n):
    """Lo manda a cada celular o navegador del usuario. Las suscripciones vencidas se borran."""
    if not configurado():
        return
    datos = json.dumps(contenido(n))
    for s in n.usuario.suscripciones_push.all():
        try:
            webpush(
                subscription_info={'endpoint': s.endpoint, 'keys': {'p256dh': s.p256dh, 'auth': s.auth}},
                data=datos,
                vapid_private_key=settings.VAPID_PRIVATE_KEY,
                vapid_claims={'sub': f'mailto:{settings.VAPID_EMAIL}'},
                ttl=TTL,
            )
        except WebPushException as e:
            codigo = getattr(e.response, 'status_code', None)
            if codigo in (404, 410):
                s.delete()
            else:
                logger.warning('No se pudo mandar el aviso %s: %s', n.id, e)
