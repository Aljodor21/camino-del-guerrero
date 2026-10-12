"""Imagen orientativa de cómo podría verse el cambio estimado hasta el control.

Parte de la foto de frente de la persona (la que subió con sus medidas) y le pide a OpenAI el
cambio de la proyección, con cuánto sería músculo y cuánto grasa. La estimación ya viene acotada
a un ritmo que el cuerpo puede dar (ver `proyeccion`), así que la imagen no se inventa nada. Solo se envía la foto con el permiso
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
LADO_ENVIO = 1536
LADO_GUARDADO = 1600


def disponible():
    return bool(settings.OPENAI_API_KEY)


def generadas_hoy(usuario):
    desde = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
    return usuario.ilustraciones.filter(creada__gte=desde).count()


def restantes_hoy(usuario):
    return max(0, settings.ILUSTRACIONES_POR_DIA - generadas_hoy(usuario))


# Cómo se nota el entrenamiento en el cuerpo, según su enfoque.
MATIZ_ENFOQUE = {
    'fuerza': 'músculos algo más llenos y marcados, sobre todo en hombros, pecho y brazos',
    'boxeo': 'un cuerpo atlético y algo más definido, con hombros y espalda trabajados',
    'funcional': 'un cuerpo atlético, funcional y algo más definido',
    'cardio_casa': 'un cuerpo más ligero y definido, sin ganar volumen muscular',
    'movilidad': 'un tono suave, sin cambios marcados de volumen',
}


def _contexto(proy):
    """Lo que sabemos de la persona, en una o dos frases para el pedido de la imagen."""
    entreno = proy['entrenamiento']
    if entreno:
        actividad = (f'Hace ejercicio: {entreno["nombre"].lower()}, {entreno["dias"]} días por semana de '
                     f'{entreno["duracion"]} minutos, lo que se nota en {MATIZ_ENFOQUE[entreno["enfoque"]]}.')
    else:
        actividad = ('No hace ejercicio: el cambio viene solo de la alimentación, así que cambia la masa '
                     'corporal en general y no se nota una ganancia muscular marcada.')
    if proy['proteina']:
        actividad += (f' Toma un suplemento de proteína en polvo (unos {proy["proteina"]["proteina_g"]} g de '
                      'proteína al día), que ya cuenta en su alimentación.')
    return actividad


def _descripcion_del_cambio(escenario):
    """Cómo se vería ese cambio, según cuánto sería músculo y cuánto grasa y agua."""
    cambio, musculo, grasa = escenario['cambio_kg'], escenario['musculo_kg'], escenario['grasa_kg']
    detalle = (f'(unos {abs(musculo):.1f} kg de músculo y {abs(grasa):.1f} kg de grasa y agua)'
               .replace('.', ','))
    if cambio < 0:
        return f'un cuerpo más delgado y definido, que conserva su músculo {detalle}'
    parte_muscular = musculo / cambio
    if parte_muscular >= 0.6:
        return f'sobre todo músculo: más volumen muscular y definición, con muy poca grasa nueva {detalle}'
    if parte_muscular >= 0.3:
        return f'una mezcla de músculo y algo de grasa: más volumen en general y algo de definición {detalle}'
    return ('sobre todo grasa y agua: algo más de volumen corporal en general (cintura, rostro y brazos un poco '
            f'más llenos), sin ganancia muscular marcada {detalle}')


def _prompt(proy, escenario):
    peso_base, cambio = proy['peso_actual_kg'], escenario['cambio_kg']
    return (
        f'Edita esta foto de la misma persona para mostrar cómo podría verse después de {proy["dias"]} días '
        f'con un cambio de peso de {cambio:+.1f} kg (de {peso_base:.1f} a {peso_base + cambio:.1f} kg): '
        f'{_descripcion_del_cambio(escenario)}. {_contexto(proy)} El cambio debe ser realista y proporcional a '
        'esos kilos, sin exagerarlo. Conserva idénticos el rostro, la identidad, el tono de piel, la pose, '
        'la ropa, el fondo, la iluminación y el encuadre. '
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
    cambio = escenario['cambio_kg']
    if abs(cambio) < CAMBIO_MINIMO_KG:
        raise ReglaNegocioError(
            f'Con tu plan el cambio estimado es de {cambio:+.1f} kg: casi no se notaría en una imagen.'.replace('.', ','))

    foto = _foto_de_frente(usuario)
    with foto.imagen.open('rb') as f:
        original = Image.open(f)
        original.load()
    envio = a_jpeg(original.convert('RGB'), LADO_ENVIO, 90).read()
    try:
        resultado = _pedir_a_openai(envio, _prompt(proy, escenario))
        imagen = a_jpeg(Image.open(BytesIO(resultado)).convert('RGB'), LADO_GUARDADO, 88)
    except Exception:
        log.exception('OpenAI no pudo generar la imagen.')
        raise ReglaNegocioError('No pudimos generar la imagen ahora. Intenta de nuevo en un rato.')

    ahora = timezone.now()
    ilustracion = Ilustracion(usuario=usuario, creada=ahora, peso_base=proy['peso_actual_kg'],
                              cambio_kg=cambio, limitado=escenario['limitado'], dias=proy['dias'],
                              foto_origen=foto, consentimiento_en=ahora)
    ilustracion.imagen.save('ilustracion.jpg', ContentFile(imagen.read()), save=False)
    ilustracion.save()
    return ilustracion
