"""A qué hora se levanta, se acuesta y come cada persona, que no es igual todos los días.

Para las horas de levantarse y acostarse manda, en este orden: lo que la persona puso solo para
ese día (`HorarioDia`), lo que puso para ese día de la semana (`Habitos.horas_semana`) y su hora
general (`Habitos.hora_levantarse` / `hora_dormir`). Las comidas tienen una hora de referencia
(la de `nutricion.grupos.HORA_TIEMPO`) que cada persona puede cambiar (`Habitos.horas_comida`).
"""
import re
from datetime import datetime, time, timedelta

from django.utils import timezone

from nutricion.grupos import HORA_TIEMPO

from .models import HorarioDia


def a_hora(texto):
    """'06:30' o '06:30:00' → time; None si no hay o no es una hora."""
    if not texto:
        return None
    partes = re.fullmatch(r'(\d{1,2}):(\d{2})(?::\d{2})?', str(texto).strip())
    if not partes:
        return None
    hora, minuto = int(partes[1]), int(partes[2])
    return time(hora, minuto) if hora < 24 and minuto < 60 else None


def horas_de(habitos, fecha, personalizados=None):
    """{'levantarse', 'dormir', 'personalizado'} de ese día. `personalizados` es un {fecha: HorarioDia}
    ya leído (para recorrer muchos días sin una consulta por día)."""
    if personalizados is None:
        propio = (HorarioDia.objects.filter(usuario_id=habitos.usuario_id, fecha=fecha).first()
                  if habitos.usuario_id else None)
    else:
        propio = personalizados.get(fecha)
    semana = (habitos.horas_semana or {}).get(str(fecha.isoweekday()), {})
    levantarse = (propio.hora_levantarse if propio and propio.hora_levantarse else None) \
        or a_hora(semana.get('levantarse')) or habitos.hora_levantarse
    dormir = (propio.hora_dormir if propio and propio.hora_dormir else None) \
        or a_hora(semana.get('dormir')) or habitos.hora_dormir
    return {
        'levantarse': levantarse, 'dormir': dormir,
        'personalizado': bool(propio and (propio.hora_levantarse or propio.hora_dormir)),
    }


def personalizados_entre(usuario, desde, hasta):
    return {h.fecha: h for h in HorarioDia.objects.filter(usuario=usuario, fecha__range=(desde, hasta))}


def hora_comida(habitos, tiempo):
    """La hora a la que la persona come ese tiempo: la suya, o la de referencia."""
    propia = a_hora((habitos.horas_comida or {}).get(tiempo))
    return propia or time(*HORA_TIEMPO[tiempo])


def momento(fecha, hora):
    return timezone.make_aware(datetime.combine(fecha, hora))


def minutos_de_diferencia(real, fecha, meta, madrugada=False):
    """Cuántos minutos después (+) o antes (−) de la hora prevista pasó `real`. Si la hora prevista
    es de madrugada (para acostarse: pasada la medianoche) cae al día siguiente."""
    if meta is None:
        return None
    esperado = momento(fecha + timedelta(days=1) if madrugada and meta.hour < 12 else fecha, meta)
    return round((real - esperado).total_seconds() / 60)
