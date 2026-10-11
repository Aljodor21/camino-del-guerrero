"""Imagen orientativa de cómo podría verse el cambio estimado hasta el control.

Parte de la foto de frente de la persona (la que subió con sus medidas) y le pide a OpenAI un
cambio suave, proporcional a los kilos de la proyección. Solo se envía la foto con el permiso
expreso de la persona, y la imagen queda privada. Es una ilustración, no una promesa.
"""
import logging
from datetime import timedelta
from io import BytesIO

from django.conf import settings
from django.core.files.base import ContentFile
from django.utils import timezone
from PIL import Image

from core.exceptions import ReglaNegocioError
from progress.fotos import a_jpeg
from progress.models import FotoProgreso

from . import proyeccion
from .models import Ilustracion

log = logging.getLogger(__name__)

# Por debajo de esto el cambio no se notaría en una imagen.
CAMBIO_MINIMO_KG = 0.3
# La imagen nunca muestra más que esto, aunque la cuenta dé más: así no se exagera nada.
CAMBIO_MAXIMO_KG = 3.0
LADO_ENVIO = 1536
LADO_GUARDADO = 1600


def disponible():
    return bool(settings.OPENAI_API_KEY)


def generadas_hoy(usuario):
    desde = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
    return usuario.ilustraciones.filter(creada__gte=desde).count()


def restantes_hoy(usuario):
    return max(0, settings.ILUSTRACIONES_POR_DIA - generadas_hoy(usuario))


def _prompt(peso_base, cambio, dias):
    if cambio > 0:
        cambio_texto = ('un poco más de masa corporal, con músculos algo más llenos y definidos, '
                        'sin agrandar nada de forma exagerada')
    else:
        cambio_texto = 'el cuerpo algo más delgado y definido, sin exagerar la pérdida'
    return (
        f'Edita esta foto de la misma persona para mostrar cómo podría verse después de {dias} días '
        f'con un cambio de peso de {cambio:+.1f} kg (de {peso_base:.1f} a {peso_base + cambio:.1f} kg): '
        f'{cambio_texto}. Es un cambio pequeño y realista. Conserva idénticos el rostro, la identidad, '
        'el tono de piel, la pose, la ropa, el fondo, la iluminación y el encuadre. '
        'Resultado fotorrealista y natural; sin filtros, sin texto y sin marcas.'
    )


def _foto_de_frente(usuario):
    foto = (FotoProgreso.objects.filter(medicion__usuario=usuario, pose='frente')
            .order_by('-medicion__fecha', '-id').first())
    if foto is None:
        raise ReglaNegocioError('Sube una foto de frente con tus medidas para poder generar la imagen.')
    return foto


def _pedir_a_openai(jpeg, prompt):
    from openai import OpenAI
    cliente = OpenAI(api_key=settings.OPENAI_API_KEY, timeout=110, max_retries=0)
    respuesta = cliente.images.edit(
        model=settings.OPENAI_IMAGE_MODEL,
        image=('frente.jpg', jpeg, 'image/jpeg'),
        prompt=prompt,
        size='1024x1536',
        quality=settings.OPENAI_IMAGE_QUALITY,
    )
    import base64
    return base64.b64decode(respuesta.data[0].b64_json)


def generar(usuario, consentimiento):
    if not disponible():
        raise ReglaNegocioError('Esta función no está activa.')
    if consentimiento is not True:
        raise ReglaNegocioError('Para generar la imagen tienes que aceptar que tu foto se envíe a OpenAI.')
    if restantes_hoy(usuario) == 0:
        raise ReglaNegocioError(f'Ya generaste {settings.ILUSTRACIONES_POR_DIA} imágenes hoy. Vuelve mañana.')

    proy = proyeccion.proyectar(usuario, timezone.localdate())
    escenario = proy['escenarios'][0]  # cumpliendo todo el plan
    real = escenario['cambio_kg']
    cambio = max(-CAMBIO_MAXIMO_KG, min(CAMBIO_MAXIMO_KG, real))
    if abs(cambio) < CAMBIO_MINIMO_KG:
        raise ReglaNegocioError(
            f'Con tu plan el cambio estimado es de {real:+.1f} kg: casi no se notaría en una imagen.'.replace('.', ','))

    foto = _foto_de_frente(usuario)
    with foto.imagen.open('rb') as f:
        original = Image.open(f)
        original.load()
    envio = a_jpeg(original.convert('RGB'), LADO_ENVIO, 90).read()
    try:
        resultado = _pedir_a_openai(envio, _prompt(proy['peso_actual_kg'], cambio, proy['dias']))
        imagen = a_jpeg(Image.open(BytesIO(resultado)).convert('RGB'), LADO_GUARDADO, 88)
    except Exception:
        log.exception('OpenAI no pudo generar la imagen.')
        raise ReglaNegocioError('No pudimos generar la imagen ahora. Intenta de nuevo en un rato.')

    ahora = timezone.now()
    ilustracion = Ilustracion(usuario=usuario, creada=ahora, peso_base=proy['peso_actual_kg'],
                              cambio_kg=cambio, limitado=abs(real) > CAMBIO_MAXIMO_KG, dias=proy['dias'],
                              consentimiento_en=ahora)
    ilustracion.imagen.save('ilustracion.jpg', ContentFile(imagen.read()), save=False)
    ilustracion.save()
    return ilustracion
