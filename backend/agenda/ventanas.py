"""Cuándo se puede decir «me levanté» y «ya me acosté», y cuándo ya no caben más siestas.

«Me levanté» solo vale desde 2 horas antes hasta 2 horas después de la hora prevista de levantarse; si
no se dice en ese rato, el día queda como «no respondió» y se puede responder una sola vez con la hora
(es la única vez que se escribe una hora). «Ya me acosté» abre 2 horas antes de la hora de acostarse:
desde ahí empieza la jornada de dormir y no se pueden empezar más siestas.
"""
from datetime import datetime, time, timedelta

from django.utils import timezone

from . import horarios

MARGEN = timedelta(hours=2)
# Antes de esta hora, la noche todavía es la del día anterior (se acostó pasada la medianoche).
HORA_CORTE_DORMIR = time(4, 0)


def _momento(fecha, hora):
    return timezone.make_aware(datetime.combine(fecha, hora))


def noche_de(ahora):
    """La fecha de la noche en que está `ahora`: de madrugada, la del día anterior."""
    return ahora.date() - timedelta(days=1) if ahora.time() < HORA_CORTE_DORMIR else ahora.date()


def levantar(habitos, ahora):
    """{'estado': 'libre'|'antes'|'abierta'|'cerrada', 'desde', 'hasta'} para el «me levanté» de hoy."""
    hora = horarios.horas_de(habitos, ahora.date())['levantarse']
    if hora is None:
        return {'estado': 'libre', 'desde': None, 'hasta': None}
    prevista = _momento(ahora.date(), hora)
    desde, hasta = prevista - MARGEN, prevista + MARGEN
    estado = 'antes' if ahora < desde else 'cerrada' if ahora > hasta else 'abierta'
    return {'estado': estado, 'desde': desde, 'hasta': hasta}


def dormir(habitos, ahora):
    """{'noche', 'abierta', 'desde'}: si ya se puede decir «ya me acosté» esta noche y desde cuándo."""
    noche = noche_de(ahora)
    hora = horarios.horas_de(habitos, noche)['dormir']
    if hora is None:
        return {'noche': noche, 'abierta': True, 'desde': None}
    # Si se acuesta pasada la medianoche, la hora cae al día siguiente de esa noche.
    dia = noche + timedelta(days=1) if hora < HORA_CORTE_DORMIR else noche
    desde = _momento(dia, hora) - MARGEN
    return {'noche': noche, 'abierta': ahora >= desde, 'desde': desde}
