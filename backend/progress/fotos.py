"""Reglas y procesamiento de las fotos de progreso.

Cada foto se vuelve a codificar como JPEG: se corrige la orientación, se limita el
tamaño y se descartan los metadatos (EXIF, ubicación GPS) de la cámara.
"""
from datetime import timedelta
from io import BytesIO

from django.core.files.base import ContentFile
from django.db import IntegrityError, transaction
from django.utils import timezone
from PIL import Image, ImageOps, UnidentifiedImageError

from core.exceptions import DatoInmutableError, ReglaNegocioError

from .models import FotoProgreso

# Las fotos de la medición inicial se pueden completar durante los primeros días
# del proceso; después, el punto de partida queda cerrado.
DIAS_FOTOS_INICIALES = 7
MAX_BYTES = 15 * 1024 * 1024
LADO_ORIGINAL = 1600
LADO_MINIATURA = 480
FORMATOS = {'JPEG', 'PNG', 'WEBP', 'MPO'}


def _proceso_iniciado(medicion):
    return getattr(medicion, 'proceso_iniciado', None)


def limite_fotos(medicion):
    """Último día en que se pueden agregar fotos a la medición, o None si no hay límite."""
    proceso = _proceso_iniciado(medicion)
    if proceso is None:
        return None
    return proceso.fecha_inicio + timedelta(days=DIAS_FOTOS_INICIALES - 1)


def admite_fotos(medicion):
    limite = limite_fotos(medicion)
    return limite is None or timezone.localdate() <= limite


def _jpeg(imagen, lado, calidad):
    copia = imagen.copy()
    copia.thumbnail((lado, lado), Image.Resampling.LANCZOS)
    salida = BytesIO()
    copia.save(salida, 'JPEG', quality=calidad, optimize=True, progressive=True)
    return ContentFile(salida.getvalue(), name='foto.jpg')


def _leer_imagen(archivo):
    if archivo.size > MAX_BYTES:
        raise ReglaNegocioError('La foto pesa más de 15 MB.')
    try:
        imagen = Image.open(archivo)
        imagen.load()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise ReglaNegocioError('No pudimos leer la foto. Usa una imagen JPG, PNG o WEBP.')
    if imagen.format not in FORMATOS:
        raise ReglaNegocioError('No pudimos leer la foto. Usa una imagen JPG, PNG o WEBP.')
    return ImageOps.exif_transpose(imagen).convert('RGB')


def agregar_foto(medicion, pose, archivo):
    if not admite_fotos(medicion):
        raise ReglaNegocioError(
            f'Las fotos de inicio se agregan durante los primeros {DIAS_FOTOS_INICIALES} días del proceso.')
    if medicion.fotos.filter(pose=pose).exists():
        raise ReglaNegocioError('Esta medición ya tiene foto en esa pose.')

    imagen = _leer_imagen(archivo)
    try:
        with transaction.atomic():
            return FotoProgreso.objects.create(
                medicion=medicion,
                pose=pose,
                imagen=_jpeg(imagen, LADO_ORIGINAL, 85),
                miniatura=_jpeg(imagen, LADO_MINIATURA, 80),
            )
    except IntegrityError:
        raise ReglaNegocioError('Esta medición ya tiene foto en esa pose.')


def eliminar_foto(foto):
    if _proceso_iniciado(foto.medicion):
        raise DatoInmutableError('Es una foto de tu punto de partida y no se puede eliminar.')
    foto.delete()
