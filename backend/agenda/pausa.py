"""Modo pausa («voy a estar desconectado») y el aviso de «¿qué pasó?» cuando la persona deja de usar la app.

- Mientras hay una pausa no se crea ni se programa ningún aviso, y los pendientes se quitan (`resolucion='pausa'`).
- Un día cuenta como «en pausa» si la pausa cubre al menos 8 horas de él: ese día no entra al cumplimiento ni
  rompe la racha (tampoco la suma). Una pausa de unas horas solo calla los avisos.
- Si pasa un día sin ninguna actividad y no hay pausa, llega un aviso al día preguntando qué pasó, con la acción
  de pausar el resto del día.
"""
from datetime import datetime, time, timedelta

from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from core.exceptions import ReglaNegocioError

from .models import Notificacion, Pausa, RegistroHabito

HORAS_PARA_CONTAR_EL_DIA = timedelta(hours=8)
MAX_DIAS = 30
MAX_HORAS = 12
SIN_ACTIVIDAD = timedelta(hours=24)
HORA_REGRESO = time(8, 0)


def _inicio_del_dia(fecha):
    return timezone.make_aware(datetime.combine(fecha, time(0, 0)))


def activa(usuario, ahora=None):
    ahora = ahora or timezone.now()
    for p in usuario.pausas.filter(desde__lte=ahora, terminada_en__isnull=True):
        if p.hasta is None or p.hasta > ahora:
            return p
    return None


def pausas_entre(usuario, desde, hasta):
    """Las pausas que tocan el rango [desde, hasta) (fechas y horas)."""
    return [p for p in usuario.pausas.filter(desde__lt=hasta) if p.fin is None or p.fin > desde]


def en_pausa(pausas, momento):
    return any(p.desde <= momento and (p.fin is None or momento < p.fin) for p in pausas)


def dias_en_pausa(usuario, desde, hasta, ahora=None):
    """Las fechas entre `desde` y `hasta` que alguna pausa cubre al menos 8 horas."""
    ahora = ahora or timezone.now()
    pausas = pausas_entre(usuario, _inicio_del_dia(desde), _inicio_del_dia(hasta + timedelta(days=1)))
    dias = set()
    if not pausas:
        return dias
    fecha = desde
    while fecha <= hasta:
        inicio, fin = _inicio_del_dia(fecha), _inicio_del_dia(fecha + timedelta(days=1))
        cubierto = timedelta()
        for p in pausas:
            hasta_p = p.fin or max(ahora, p.desde)
            cubierto += max(timedelta(), min(fin, hasta_p) - max(inicio, p.desde))
        if cubierto >= HORAS_PARA_CONTAR_EL_DIA:
            dias.add(fecha)
        fecha += timedelta(days=1)
    return dias


@transaction.atomic
def volvio_hoy(usuario, ahora=None):
    """Hoy terminó una pausa (dijo «ya volví» o se cumplió su tiempo) y no hay otra en curso."""
    ahora = ahora or timezone.now()
    if activa(usuario, ahora):
        return False
    inicio = _inicio_del_dia(timezone.localdate(ahora))
    return any(p.fin and inicio <= p.fin <= ahora for p in pausas_entre(usuario, inicio, ahora))


def iniciar(usuario, duracion, cantidad=None, motivo=''):
    """`duracion`: 'horas' (cantidad 1-12), 'hoy', 'dias' (cantidad 1-30, contando hoy) o 'indefinida'. Empieza
    ahora: los días que ya pasaron no se excusan después."""
    ahora = timezone.now()
    if activa(usuario, ahora):
        raise ReglaNegocioError('Ya estás en pausa.')
    hoy = timezone.localdate()
    if duracion == 'horas':
        if not isinstance(cantidad, int) or not 1 <= cantidad <= MAX_HORAS:
            raise ReglaNegocioError(f'Di entre 1 y {MAX_HORAS} horas.')
        hasta = ahora + timedelta(hours=cantidad)
    elif duracion == 'hoy':
        hasta = _inicio_del_dia(hoy + timedelta(days=1))
    elif duracion == 'dias':
        if not isinstance(cantidad, int) or not 1 <= cantidad <= MAX_DIAS:
            raise ReglaNegocioError(f'Di entre 1 y {MAX_DIAS} días.')
        hasta = _inicio_del_dia(hoy + timedelta(days=cantidad))
    elif duracion == 'indefinida':
        hasta = None
    else:
        raise ReglaNegocioError('Elige cuánto vas a estar desconectado.')
    desde = ahora
    # Nunca encima de una pausa anterior.
    ultima = usuario.pausas.order_by('-desde').first()
    if ultima and ultima.fin and ultima.fin > desde:
        desde = ultima.fin
    p = Pausa.objects.create(usuario=usuario, desde=desde, hasta=hasta, motivo=(motivo or '').strip()[:120])
    # Lo que estaba pendiente sobra: ya no se va a poder responder a tiempo.
    Notificacion.objects.filter(usuario=usuario, resuelta_en__isnull=True).update(resuelta_en=ahora, resolucion='pausa')
    return p


def terminar(usuario):
    """«Ya volví»."""
    p = activa(usuario)
    if p is None:
        raise ReglaNegocioError('No estás en pausa.')
    p.terminada_en = timezone.now()
    p.save(update_fields=['terminada_en'])
    return p


# ── «¿Qué pasó?» ────────────────────────────────────────────────────────────────
def ultima_actividad(usuario):
    """Lo último que hizo en la app: un registro, una comida contada, un aviso confirmado o el fin de una pausa."""
    from nutricion.models import RegistroComida
    momentos = [
        usuario.date_joined,
        RegistroHabito.objects.filter(usuario=usuario).aggregate(m=Max('momento'))['m'],
        RegistroComida.objects.filter(usuario=usuario).aggregate(m=Max('momento'))['m'],
        Notificacion.objects.filter(usuario=usuario, resolucion='confirmada').aggregate(m=Max('resuelta_en'))['m'],
    ]
    for p in usuario.pausas.all()[:5]:
        momentos.append(p.fin)
    return max(m for m in momentos if m)


def aviso_de_regreso(usuario, fecha, ahora):
    """El aviso de hoy si lleva un día o más sin hacer nada (y no está en pausa)."""
    if activa(usuario, ahora):
        return None
    ultima = ultima_actividad(usuario)
    if ahora - ultima < SIN_ACTIVIDAD:
        return None
    cuando = max(ultima + SIN_ACTIVIDAD, timezone.make_aware(datetime.combine(fecha, HORA_REGRESO)))
    if timezone.localdate(cuando) != fecha:
        return None
    dias = (ahora - ultima).days
    if dias >= 7:
        titulo, cuerpo = ('Aquí sigue tu camino', 'Cuando quieras volver, empieza por una sola cosa: un vaso de '
                                                  'agua ya cuenta. Si sigues a mil, pon la app en pausa.')
    elif dias >= 2:
        titulo, cuerpo = (f'Ey, llevas {dias} días sin aparecer', 'Si estás a mil, pon la app en pausa: tus días '
                                                                   'en pausa no rompen la racha.')
    else:
        titulo, cuerpo = ('Ey, ¿qué pasó?', 'Llevas un día sin anotar nada. Si estás a mil, pon la app en pausa: '
                                            'tus días en pausa no rompen la racha.')
    return {'tipo': 'regreso', 'clave': f'regreso:{fecha}', 'programada_para': cuando, 'titulo': titulo,
            'cuerpo': cuerpo, 'datos': {'desde': ultima.isoformat()}}


def regreso_resuelto(notificacion, ahora):
    return (notificacion.fecha < timezone.localdate(ahora) or activa(notificacion.usuario, ahora) is not None
            or ultima_actividad(notificacion.usuario) > notificacion.programada_para)
