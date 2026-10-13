"""Envío de los avisos al celular: web push (navegador, llaves VAPID) y Firebase (app instalada)."""
import json
import logging

from django.conf import settings
from pywebpush import WebPushException, webpush

from . import fcm, notificaciones

logger = logging.getLogger(__name__)
TTL = 2 * 3600


def configurado():
    return bool(settings.VAPID_PUBLIC_KEY and settings.VAPID_PRIVATE_KEY and settings.VAPID_EMAIL)


def contenido(n):
    return {
        'id': n.id,
        'tipo': n.tipo,
        # Los avisos de un mismo pendiente comparten grupo: el nuevo reemplaza al anterior en la barra.
        'grupo': n.datos.get('grupo') or f'{n.tipo}-{n.id}',
        'momento': n.programada_para.isoformat(),
        'titulo': n.titulo,
        'cuerpo': notificaciones.cuerpo_de(n),
        'accion': notificaciones.accion_de(n),
        'firma': notificaciones.firmar(n),
        'url': notificaciones.url_de(n),
    }


def enviar(n):
    """Lo manda a cada navegador (web push) y a cada celular con la app (Firebase) del usuario."""
    enviar_web(n)
    fcm.enviar(n)


def tiene_la_app(usuario):
    """Si ya recibe los avisos en la app instalada, el navegador no debe repetirlos."""
    return usuario.tokens_celular.exists()


def enviar_web(n):
    """Web push. Las suscripciones vencidas se borran. No se manda a quien ya tiene la app."""
    if not configurado() or tiene_la_app(n.usuario):
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
