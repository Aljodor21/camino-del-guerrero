"""Recuperar la clave: se envía por correo el usuario y un enlace para crear una clave nueva.

El enlace es de un solo uso, caduca (RECUPERACION_MINUTOS) y solo funciona en el navegador
donde se pidió: ese navegador guarda un código que se compara con el que quedó al pedirlo.
Pedir otro enlace anula el anterior. Quien lo pide nunca sabe si el correo existe.
"""
import hashlib
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as ErrorDeClave
from django.db import transaction
from django.utils import timezone

from core.exceptions import ReglaNegocioError

from . import correos
from .models import SolicitudRecuperacion, Usuario

ENLACE_INVALIDO = 'El enlace ya no sirve: venció o ya se usó. Pide uno nuevo desde "¿Olvidaste tu clave?".'


def _hash(valor):
    return hashlib.sha256(valor.encode()).hexdigest()


def _dispositivo_valido(dispositivo):
    if not isinstance(dispositivo, str) or not 16 <= len(dispositivo) <= 100:
        raise ReglaNegocioError('No pudimos identificar tu navegador. Recarga la página e intenta de nuevo.')
    return dispositivo


@transaction.atomic
def enviar(email, dispositivo):
    """Manda el usuario y el enlace si el correo es de una cuenta activa."""
    dispositivo = _dispositivo_valido(dispositivo)
    ahora = timezone.now()
    SolicitudRecuperacion.objects.filter(creada__lt=ahora - timedelta(days=1)).delete()
    usuario = Usuario.objects.filter(email__iexact=email.strip(), is_active=True).first()
    if usuario is None:
        return
    # El enlace anterior deja de servir.
    SolicitudRecuperacion.objects.filter(usuario=usuario, usada_en__isnull=True).update(usada_en=ahora)
    token = secrets.token_urlsafe(32)
    SolicitudRecuperacion.objects.create(usuario=usuario, token_hash=_hash(token),
                                         dispositivo_hash=_hash(dispositivo))
    enlace = f'{settings.FRONTEND_URL.rstrip("/")}/auth/restablecer?token={token}'
    correos.enviar_recuperacion(usuario, enlace, settings.RECUPERACION_MINUTOS)


@transaction.atomic
def restablecer(token, dispositivo, clave):
    dispositivo = _dispositivo_valido(dispositivo)
    ahora = timezone.now()
    solicitud = (SolicitudRecuperacion.objects.select_for_update().select_related('usuario')
                 .filter(token_hash=_hash(token), usada_en__isnull=True,
                         creada__gte=ahora - timedelta(minutes=settings.RECUPERACION_MINUTOS),
                         usuario__is_active=True).first())
    if solicitud is None:
        raise ReglaNegocioError(ENLACE_INVALIDO)
    if not secrets.compare_digest(solicitud.dispositivo_hash, _hash(dispositivo)):
        raise ReglaNegocioError('Abre el enlace en el mismo navegador donde pediste recuperar la clave.')
    usuario = solicitud.usuario
    try:
        validate_password(clave, usuario)
    except ErrorDeClave as e:
        raise ReglaNegocioError(' '.join(e.messages))
    usuario.set_password(clave)
    usuario.save(update_fields=['password'])
    SolicitudRecuperacion.objects.filter(usuario=usuario, usada_en__isnull=True).update(usada_en=ahora)
