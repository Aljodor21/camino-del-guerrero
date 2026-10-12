"""Reglas de negocio de los procesos del usuario.

Un usuario tiene un solo proceso a la vez (en curso o programado), con alimentación,
entrenamiento o ambos; el módulo que falta se suma después sin crear otro proceso. Para
empezar uno nuevo se borra el actual. La medición inicial se toma al crear el proceso (obligatoria si inicia hoy) y no cambia.
"""
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from core.exceptions import DatoInmutableError, ReglaNegocioError
from progress.models import Medicion

from .models import ConfiguracionEntrenamiento, Proceso

MODULOS = ('alimentacion', 'entrenamiento')
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
    # Un solo proceso a la vez: la alimentación y el entrenamiento van en el mismo proceso.
    if proceso_programado(usuario):
        raise ReglaNegocioError('Ya tienes un proceso programado. Para empezar otro, bórralo desde tu perfil.')
    if proceso_actual(usuario):
        raise ReglaNegocioError('Ya tienes un proceso en curso. Para empezar otro, bórralo desde tu perfil.')

    if fecha_inicio == hoy and not medicion:
        raise ReglaNegocioError('Si el proceso inicia hoy, registra tu medición inicial.')
    if datos.get('incluye_entrenamiento') and not entrenamiento:
        raise ReglaNegocioError('Configura tu entrenamiento para incluirlo en el proceso.')
    _validar_fin_plan(fecha_inicio, datos.get('fecha_fin_plan'))

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
    """Cambia solo lo editable: peso meta, notas y módulos. La fecha meta se puede poner si
    no se puso al empezar, pero una vez puesta no se mueve."""
    if proceso.estado == 'finalizado':
        raise ReglaNegocioError('Un proceso finalizado ya no se puede modificar.')
    fin_plan = datos.get('fecha_fin_plan')
    if 'fecha_fin_plan' in datos and proceso.fecha_fin_plan and fin_plan != proceso.fecha_fin_plan:
        raise DatoInmutableError('La fecha meta que pusiste al empezar no se puede cambiar.')
    for modulo in MODULOS:
        if datos.get(f'incluye_{modulo}') is False and getattr(proceso, f'incluye_{modulo}'):
            raise ReglaNegocioError('Para quitar un módulo usa "Quitar" en tu proceso: borra lo que armaste con él.')
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


@transaction.atomic
def reiniciar(usuario):
    """Borra todo lo que la persona armó (procesos, medidas, plan, menús, suplementos, registros,
    avisos y rutina) y deja solo sus datos personales, para empezar de nuevo con otro onboarding."""
    from agenda.models import Habitos
    from nutricion.models import ListaMercado, PreferenciasComida
    from routines.models import Rutina

    # Los procesos primero: protegen su medición inicial y arrastran minutas, menús y suplementos.
    usuario.procesos.all().delete()
    for relacion in (usuario.mediciones, usuario.registros_entrenamiento, usuario.registros_comida,
                     usuario.registros_habito, usuario.notificaciones, usuario.recordatorios,
                     usuario.items_recurrentes, usuario.implementos, usuario.ilustraciones):
        relacion.all().delete()
    for modelo in (Rutina, ListaMercado, PreferenciasComida, Habitos):
        modelo.objects.filter(usuario=usuario).delete()


@transaction.atomic
def quitar_modulo(proceso, modulo):
    """Quita la alimentación o el entrenamiento del proceso y borra lo que se armó con él.
    El otro módulo sigue igual; un proceso no puede quedarse sin ninguno."""
    from agenda.models import Notificacion
    from nutricion.models import ListaMercado, PreferenciasComida
    from routines.models import Rutina

    if modulo not in MODULOS:
        raise ReglaNegocioError('Ese módulo no existe.')
    if not getattr(proceso, f'incluye_{modulo}'):
        raise ReglaNegocioError('Ese módulo ya no está en tu proceso.')
    otro = 'entrenamiento' if modulo == 'alimentacion' else 'alimentacion'
    if not getattr(proceso, f'incluye_{otro}'):
        raise ReglaNegocioError('El proceso necesita al menos un módulo. Para empezar de cero, bórralo.')
    usuario = proceso.usuario
    if modulo == 'entrenamiento':
        ConfiguracionEntrenamiento.objects.filter(proceso=proceso).delete()
        usuario.registros_entrenamiento.all().delete()
        usuario.implementos.all().delete()
        Rutina.objects.filter(usuario=usuario).delete()
        Notificacion.objects.filter(usuario=usuario, tipo='entreno').delete()
    else:
        proceso.minutas.all().delete()  # arrastra sus menús; la minuta no se borra de a una
        proceso.suplementos.all().delete()
        usuario.registros_comida.all().delete()
        usuario.items_recurrentes.all().delete()
        usuario.ilustraciones.all().delete()
        usuario.registros_habito.filter(tipo='toma').delete()
        Notificacion.objects.filter(usuario=usuario, tipo__in=['comida', 'toma']).delete()
        for modelo in (ListaMercado, PreferenciasComida):
            modelo.objects.filter(usuario=usuario).delete()
    setattr(proceso, f'incluye_{modulo}', False)
    proceso.save(update_fields=[f'incluye_{modulo}'])
    return proceso


@transaction.atomic
def renovar(proceso, fecha_fin_plan, con_plan_nuevo=False):
    """Sigue con el proceso en otro periodo: otra fecha meta, o ninguna (sin definir).

    La fecha meta es fija. Solo se mueve al llegar el control (cuando ya venció) o cuando se
    guarda un plan nuevo; la anterior queda en `renovaciones`."""
    proceso = Proceso.objects.select_for_update().get(pk=proceso.pk)
    hoy = timezone.localdate()
    vencido = proceso.fecha_fin_plan is not None and proceso.fecha_fin_plan <= hoy
    if proceso.fecha_fin_plan is not None and not (vencido or con_plan_nuevo):
        raise DatoInmutableError('La fecha meta no se mueve hasta que llegue tu control o guardes un plan nuevo.')
    if fecha_fin_plan is not None:
        if fecha_fin_plan <= hoy:
            raise ReglaNegocioError('La nueva fecha tiene que ser futura.')
        _validar_fin_plan(proceso.fecha_inicio, fecha_fin_plan)
    if fecha_fin_plan == proceso.fecha_fin_plan:
        return proceso
    if proceso.fecha_fin_plan:
        proceso.renovaciones = [*proceso.renovaciones,
                                {'hasta': proceso.fecha_fin_plan.isoformat(), 'cambiada_el': hoy.isoformat()}]
    proceso.fecha_fin_plan = fecha_fin_plan
    proceso.save(update_fields=['fecha_fin_plan', 'renovaciones'])
    from nutricion.suplementos import sincronizar_proceso
    sincronizar_proceso(proceso)
    return proceso
