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


LEVANTARSE_POR_DEFECTO = time(6, 0)
DORMIR_POR_DEFECTO = time(22, 0)
# El desayuno es una hora después de levantarse; la última comida, dos horas antes de acostarse.
DESPUES_DE_LEVANTARSE = timedelta(hours=1)
ULTIMA_ANTES_DE_DORMIR = timedelta(hours=2)
# Cuánto se espera a que la persona diga «me levanté» antes de seguir con la hora prevista.
GRACIA_LEVANTARSE = timedelta(hours=3)


def _a_cinco_minutos(momento_):
    minutos = round((momento_.hour * 60 + momento_.minute) / 5) * 5
    return momento_.replace(hour=minutos // 60 % 24, minute=minutos % 60, second=0, microsecond=0)


def horas_de_comidas(habitos, fecha, tiempos, levantado=None, personalizados=None, propias=True):
    """{tiempo: time} de las comidas del plan de ese día (solo las que el plan tiene).

    Si la persona no puso una hora, se reparten como el agua: la primera una hora después de
    levantarse (la hora a la que de verdad se levantó ese día, si ya la anotó) y la última dos
    horas antes de acostarse, con el mismo espacio entre una y otra. Las horas que sí puso mandan.
    `propias=False` da solo el reparto, sin las horas de la persona."""
    horas = horas_de(habitos, fecha, personalizados)
    levantarse = levantado or horas['levantarse'] or LEVANTARSE_POR_DEFECTO
    dormir = horas['dormir'] or DORMIR_POR_DEFECTO
    inicio = momento(fecha, levantarse) + DESPUES_DE_LEVANTARSE
    fin = momento(fecha, dormir) - ULTIMA_ANTES_DE_DORMIR
    if dormir <= levantarse:                      # se acuesta pasada la medianoche
        fin += timedelta(days=1)
    n = len(tiempos)
    if fin <= inicio:
        fin = inicio + timedelta(hours=3) * max(n - 1, 1)
    paso = (fin - inicio) / max(n - 1, 1)
    repartidas = {t: _a_cinco_minutos(inicio + paso * i).time() for i, t in enumerate(tiempos)}
    if not propias:
        return repartidas
    for t in tiempos:
        propia = a_hora((habitos.horas_comida or {}).get(t))
        if propia:
            repartidas[t] = propia
    return repartidas


def hora_comida(habitos, tiempo):
    """La hora de una comida que no está en el plan (por ejemplo, la de una toma): la suya o la de referencia."""
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
