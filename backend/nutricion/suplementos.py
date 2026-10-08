"""Reglas de los suplementos del proceso.

Todo cambio pasa por aquí para que los recordatorios sugeridos queden al día.
"""
from django.db import transaction
from django.utils import timezone

from agenda import sugerencias
from core.exceptions import ReglaNegocioError

from .models import Suplemento

MAX_DIAS_DURACION = 730


def _validar(proceso, datos):
    duracion = datos.get('duracion_dias')
    if duracion is not None and not 1 <= duracion <= MAX_DIAS_DURACION:
        raise ReglaNegocioError('La duración debe estar entre 1 día y dos años.')
    if proceso.estado == 'finalizado':
        raise ReglaNegocioError('El proceso ya terminó.')


@transaction.atomic
def crear_suplemento(proceso, datos):
    _validar(proceso, datos)
    inicio = max(timezone.localdate(), proceso.fecha_inicio)
    suplemento = Suplemento.objects.create(
        usuario=proceso.usuario, proceso=proceso, fecha_inicio=inicio, envase_desde=inicio, **datos)
    sugerencias.sincronizar(suplemento)
    return suplemento


def _vigente(suplemento):
    if suplemento.fecha_fin:
        raise ReglaNegocioError('Este suplemento ya no está activo.')


@transaction.atomic
def actualizar_suplemento(suplemento, datos):
    _vigente(suplemento)
    _validar(suplemento.proceso, datos)
    for campo, valor in datos.items():
        setattr(suplemento, campo, valor)
    suplemento.save()
    if suplemento.duracion_confirmada:
        sugerencias.resolver(suplemento, 'confirmar')
    sugerencias.sincronizar(suplemento)
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
    return suplemento


@transaction.atomic
def reemplazar(suplemento, datos):
    """Termina el actual y empieza otro del mismo tipo (ej. cambio de proteína)."""
    terminar(suplemento)
    return crear_suplemento(suplemento.proceso, {'tipo': suplemento.tipo, **datos})


def sincronizar_proceso(proceso):
    """El fin del plan del proceso cambia el fin de los suplementos sin duración propia."""
    for suplemento in proceso.suplementos.filter(fecha_fin__isnull=True):
        sugerencias.sincronizar(suplemento)


def cerrar_con_proceso(proceso, fecha_fin):
    """Al cerrar un proceso, sus suplementos activos terminan con él."""
    activos = list(proceso.suplementos.filter(fecha_fin__isnull=True))
    for suplemento in activos:
        suplemento.fecha_fin = max(fecha_fin, suplemento.fecha_inicio)
        suplemento.save(update_fields=['fecha_fin'])
        sugerencias.sincronizar(suplemento)


def reabrir_con_proceso(proceso, fecha_fin):
    """Si se cancela el proceso que lo iba a reemplazar, vuelven los que se cerraron con él."""
    for suplemento in proceso.suplementos.filter(fecha_fin=fecha_fin):
        suplemento.fecha_fin = None
        suplemento.save(update_fields=['fecha_fin'])
        sugerencias.sincronizar(suplemento)
