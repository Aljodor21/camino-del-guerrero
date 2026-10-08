"""Reglas de negocio de los procesos del usuario.

Un usuario tiene como máximo un proceso en curso y uno programado. Al crear un
proceso nuevo, el que está en curso se cierra el día anterior al inicio del
nuevo. La medición inicial se registra el mismo día de inicio y no cambia.
"""
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from core.exceptions import ReglaNegocioError
from progress.models import Medicion

from .models import ConfiguracionEntrenamiento, Proceso

MAX_DIAS_PROGRAMACION = 60
MAX_DIAS_DURACION = 730


def proceso_actual(usuario):
    return usuario.procesos.en_curso().first()


def proceso_programado(usuario):
    return usuario.procesos.programados().first()


def proceso_de_referencia(usuario):
    """El proceso que deben usar los planes: el que está en curso o, si aún no
    empieza ninguno, el programado."""
    return proceso_actual(usuario) or proceso_programado(usuario)


def _validar_fin_plan(fecha_inicio, fecha_fin_plan):
    if fecha_fin_plan is None:
        return
    if fecha_fin_plan <= fecha_inicio:
        raise ReglaNegocioError('La fecha de fin del plan debe ser posterior al inicio.')
    if fecha_fin_plan > fecha_inicio + timedelta(days=MAX_DIAS_DURACION):
        raise ReglaNegocioError('Un proceso puede planearse máximo a dos años.')


def _crear_medicion(usuario, datos):
    datos = {**datos}
    datos.pop('fecha', None)
    datos.setdefault('talla_cm', usuario.estatura)
    return Medicion.objects.create(usuario=usuario, fecha=timezone.localdate(), **datos)


@transaction.atomic
def crear_proceso(usuario, datos, medicion=None, entrenamiento=None):
    hoy = timezone.localdate()
    fecha_inicio = datos['fecha_inicio']

    # Bloquea los procesos del usuario para evitar dos creaciones simultáneas.
    list(Proceso.objects.select_for_update().filter(usuario=usuario))

    if fecha_inicio < hoy:
        raise ReglaNegocioError('La fecha de inicio no puede estar en el pasado.')
    if fecha_inicio > hoy + timedelta(days=MAX_DIAS_PROGRAMACION):
        raise ReglaNegocioError(f'Solo puedes programar un proceso hasta {MAX_DIAS_PROGRAMACION} días adelante.')
    if proceso_programado(usuario):
        raise ReglaNegocioError('Ya tienes un proceso programado. Cancélalo antes de crear otro.')

    actual = proceso_actual(usuario)
    if actual and fecha_inicio <= actual.fecha_inicio:
        raise ReglaNegocioError('El nuevo proceso debe iniciar después del día de inicio de tu proceso actual.')

    if fecha_inicio == hoy and not medicion:
        raise ReglaNegocioError('Si el proceso inicia hoy, registra tu medición inicial.')
    if fecha_inicio > hoy and medicion:
        raise ReglaNegocioError('La medición inicial se registra el día en que inicia el proceso.')
    if datos.get('incluye_entrenamiento') and not entrenamiento:
        raise ReglaNegocioError('Configura tu entrenamiento para incluirlo en el proceso.')
    _validar_fin_plan(fecha_inicio, datos.get('fecha_fin_plan'))

    if actual:
        Proceso.objects.filter(pk=actual.pk).update(fecha_fin=fecha_inicio - timedelta(days=1))
        from nutricion.suplementos import cerrar_con_proceso
        cerrar_con_proceso(actual, fecha_inicio - timedelta(days=1))

    proceso = Proceso.objects.create(usuario=usuario, **datos)
    if medicion:
        proceso.medicion_inicial = _crear_medicion(usuario, medicion)
        proceso.save(update_fields=['medicion_inicial'])
    if entrenamiento:
        ConfiguracionEntrenamiento.objects.create(proceso=proceso, **entrenamiento)
    return proceso


@transaction.atomic
def cancelar_programado(proceso):
    """Elimina un proceso que aún no ha iniciado y reabre el que estaba en curso."""
    if proceso.estado != 'programado':
        raise ReglaNegocioError('Solo se puede cancelar un proceso que aún no ha iniciado.')
    anterior = (proceso.usuario.procesos
                .filter(fecha_fin=proceso.fecha_inicio - timedelta(days=1))
                .exclude(pk=proceso.pk).first())
    proceso.delete()
    if anterior:
        Proceso.objects.filter(pk=anterior.pk).update(fecha_fin=None)
        from nutricion.suplementos import reabrir_con_proceso
        reabrir_con_proceso(anterior, proceso.fecha_inicio - timedelta(days=1))


@transaction.atomic
def registrar_medicion_inicial(proceso, datos):
    proceso = Proceso.objects.select_for_update().get(pk=proceso.pk)
    if proceso.estado != 'en_curso':
        raise ReglaNegocioError('La medición inicial se registra cuando el proceso está en curso.')
    if proceso.medicion_inicial_id:
        raise ReglaNegocioError('Este proceso ya tiene medición inicial y no se puede cambiar.')
    proceso.medicion_inicial = _crear_medicion(proceso.usuario, datos)
    proceso.save(update_fields=['medicion_inicial'])
    return proceso


@transaction.atomic
def actualizar_proceso(proceso, datos, entrenamiento=None):
    """Cambia solo lo editable: peso meta, fin del plan, notas y módulos."""
    if proceso.estado == 'finalizado':
        raise ReglaNegocioError('Un proceso finalizado ya no se puede modificar.')
    fin_plan = datos.get('fecha_fin_plan')
    if fin_plan and fin_plan != proceso.fecha_fin_plan:
        if fin_plan < timezone.localdate():
            raise ReglaNegocioError('La nueva fecha de fin del plan no puede estar en el pasado.')
        _validar_fin_plan(proceso.fecha_inicio, fin_plan)

    for campo, valor in datos.items():
        setattr(proceso, campo, valor)

    tiene_config = hasattr(proceso, 'entrenamiento')
    if proceso.incluye_entrenamiento and not tiene_config and not entrenamiento:
        raise ReglaNegocioError('Configura tu entrenamiento para incluirlo en el proceso.')
    if not (proceso.incluye_alimentacion or proceso.incluye_entrenamiento):
        raise ReglaNegocioError('El proceso debe incluir alimentación, entrenamiento o ambos.')

    proceso.save()
    if 'fecha_fin_plan' in datos:
        from nutricion.suplementos import sincronizar_proceso
        sincronizar_proceso(proceso)
    if entrenamiento:
        ConfiguracionEntrenamiento.objects.update_or_create(proceso=proceso, defaults=entrenamiento)
        proceso.refresh_from_db()
    return proceso
