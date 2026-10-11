"""Reglas de los suplementos del proceso.

Todo cambio pasa por aquí para que los recordatorios sugeridos y el menú queden al día.
"""
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from agenda import sugerencias
from core.exceptions import ReglaNegocioError
from progress.fotos import LADO_ORIGINAL, a_jpeg, leer_imagen

from . import menus, minutas
from .grupos import NOMBRE_GRUPO, NOMBRE_TIEMPO
from .models import Suplemento

MAX_DIAS_DURACION = 730


def _validar(proceso, datos, actual=None):
    duracion = datos.get('duracion_dias')
    if duracion is not None and not 1 <= duracion <= MAX_DIAS_DURACION:
        raise ReglaNegocioError('La duración debe estar entre 1 día y dos años.')
    if proceso.estado == 'finalizado':
        raise ReglaNegocioError('El proceso ya terminó.')
    _validar_en_minuta(proceso, datos.get('tomas', getattr(actual, 'tomas', [])))


def _validar_en_minuta(proceso, tomas):
    """Lo que reemplaza cada toma tiene que estar en esa comida de la minuta."""
    minuta = minutas.vigente(proceso)
    if minuta is None:
        return
    for toma in tomas:
        tiempo = toma['tiempo']
        en_la_comida = minuta.porciones_en(tiempo)
        for grupo, porciones in toma['reemplaza'].items():
            if en_la_comida.get(grupo, Decimal(0)) < Decimal(str(porciones)):
                raise ReglaNegocioError(
                    f'Tu minuta no tiene {porciones:g} de {NOMBRE_GRUPO[grupo].lower()} '
                    f'en {NOMBRE_TIEMPO[tiempo].lower()}.')


@transaction.atomic
def crear_suplemento(proceso, datos):
    _validar(proceso, datos)
    inicio = max(timezone.localdate(), proceso.fecha_inicio)
    suplemento = Suplemento.objects.create(
        usuario=proceso.usuario, proceso=proceso, fecha_inicio=inicio, envase_desde=inicio, **datos)
    sugerencias.sincronizar(suplemento)
    menus.reajustar(proceso.usuario)
    return suplemento


def _vigente(suplemento):
    if suplemento.fecha_fin:
        raise ReglaNegocioError('Este suplemento ya no está activo.')


@transaction.atomic
def actualizar_suplemento(suplemento, datos):
    _vigente(suplemento)
    _validar(suplemento.proceso, datos, suplemento)
    for campo, valor in datos.items():
        setattr(suplemento, campo, valor)
    suplemento.save()
    if suplemento.duracion_confirmada:
        sugerencias.resolver(suplemento, 'confirmar')
    sugerencias.sincronizar(suplemento)
    menus.reajustar(suplemento.usuario)
    return suplemento


@transaction.atomic
def abrir_envase(suplemento):
    """Se compró y abrió un envase nuevo hoy."""
    _vigente(suplemento)
    sugerencias.resolver(suplemento, 'reponer')
    suplemento.envase_desde = timezone.localdate()
    suplemento.save(update_fields=['envase_desde'])
    sugerencias.sincronizar(suplemento)
    return suplemento


@transaction.atomic
def continuar(suplemento, dias_mas):
    """Al terminar lo planeado se decide seguir con el mismo por `dias_mas` días."""
    _vigente(suplemento)
    if not suplemento.duracion_dias:
        raise ReglaNegocioError('Este suplemento va mientras dure el proceso.')
    return actualizar_suplemento(suplemento, {
        'duracion_dias': suplemento.duracion_dias + dias_mas, 'duracion_confirmada': True})


@transaction.atomic
def terminar(suplemento):
    _vigente(suplemento)
    hoy = timezone.localdate()
    sugerencias.resolver(suplemento, 'revisar')
    suplemento.fecha_fin = max(hoy, suplemento.fecha_inicio)
    suplemento.save(update_fields=['fecha_fin'])
    sugerencias.sincronizar(suplemento)
    menus.reajustar(suplemento.usuario)
    return suplemento


@transaction.atomic
def eliminar(suplemento):
    usuario = suplemento.usuario
    suplemento.delete()
    menus.reajustar(usuario)


@transaction.atomic
def reemplazar(suplemento, datos):
    """Termina el actual y empieza otro del mismo tipo (ej. cambio de proteína), que
    por defecto se toma en las mismas comidas y reemplaza lo mismo."""
    terminar(suplemento)
    datos = {'tomas': suplemento.tomas, 'liquido': suplemento.liquido, 'liquido_ml': suplemento.liquido_ml, **datos}
    return crear_suplemento(suplemento.proceso, {'tipo': suplemento.tipo, **datos})


def sincronizar_proceso(proceso):
    """El fin del plan del proceso cambia el fin de los suplementos sin duración propia."""
    for suplemento in proceso.suplementos.filter(fecha_fin__isnull=True):
        sugerencias.sincronizar(suplemento)
    menus.reajustar(proceso.usuario)


def cerrar_con_proceso(proceso, fecha_fin):
    """Al cerrar un proceso, sus suplementos activos terminan con él."""
    activos = list(proceso.suplementos.filter(fecha_fin__isnull=True))
    for suplemento in activos:
        suplemento.fecha_fin = max(fecha_fin, suplemento.fecha_inicio)
        suplemento.save(update_fields=['fecha_fin'])
        sugerencias.sincronizar(suplemento)
    menus.reajustar(proceso.usuario)


def reabrir_con_proceso(proceso, fecha_fin):
    """Si se cancela el proceso que lo iba a reemplazar, vuelven los que se cerraron con él."""
    for suplemento in proceso.suplementos.filter(fecha_fin=fecha_fin):
        suplemento.fecha_fin = None
        suplemento.save(update_fields=['fecha_fin'])
        sugerencias.sincronizar(suplemento)
    menus.reajustar(proceso.usuario)


# ── Información nutricional (foto o PDF de la etiqueta) ───────────────────────
MAX_INFO_BYTES = 10 * 1024 * 1024


def guardar_info_archivo(suplemento, archivo):
    """La foto (se reduce y se le quitan los metadatos) o el PDF de la etiqueta. Reemplaza al anterior."""
    if archivo.size > MAX_INFO_BYTES:
        raise ReglaNegocioError('El archivo pesa más de 10 MB.')
    if archivo.read(5) == b'%PDF-':
        archivo.seek(0)
        archivo.name = 'etiqueta.pdf'
        nuevo = archivo
    else:
        archivo.seek(0)
        nuevo = a_jpeg(leer_imagen(archivo), LADO_ORIGINAL, 85)
    anterior = suplemento.info_archivo.name
    suplemento.info_archivo.save(nuevo.name, nuevo, save=True)
    if anterior:
        suplemento.info_archivo.storage.delete(anterior)
    return suplemento


def quitar_info_archivo(suplemento):
    anterior = suplemento.info_archivo.name
    if anterior:
        suplemento.info_archivo = ''
        suplemento.save(update_fields=['info_archivo'])
        suplemento.info_archivo.storage.delete(anterior)
    return suplemento


def guardar_foto(suplemento, archivo):
    """La foto del producto (se reduce y se le quitan los metadatos). Reemplaza a la anterior."""
    if archivo.size > MAX_INFO_BYTES:
        raise ReglaNegocioError('La foto pesa más de 10 MB.')
    nuevo = a_jpeg(leer_imagen(archivo), LADO_ORIGINAL, 85)
    anterior = suplemento.foto.name
    suplemento.foto.save(nuevo.name, nuevo, save=True)
    if anterior:
        suplemento.foto.storage.delete(anterior)
    return suplemento


def quitar_foto(suplemento):
    anterior = suplemento.foto.name
    if anterior:
        suplemento.foto = ''
        suplemento.save(update_fields=['foto'])
        suplemento.foto.storage.delete(anterior)
    return suplemento
