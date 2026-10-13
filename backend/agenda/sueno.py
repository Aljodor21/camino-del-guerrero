"""Cuánto se duerme: de la hora en que la persona anota que se acostó a la hora en que anota que
se levantó. Es un cálculo sobre lo registrado, no se guarda: la hora del aviso confirmado puede
adelantarse un poco a la real, así que es un promedio aproximado."""
from datetime import timedelta

from django.utils import timezone

from .models import RegistroHabito

# Una noche más corta o más larga que esto casi seguro es que se olvidó anotar una de las dos horas.
MIN_HORAS = 1
MAX_HORAS = 16


def noches(usuario, desde, hasta):
    """Las noches con las dos horas anotadas: {fecha en que se levantó, acostado, levantado, horas}."""
    levantadas = {}
    for r in RegistroHabito.objects.filter(usuario=usuario, tipo='levantar', fecha__range=(desde, hasta)).order_by('momento'):
        levantadas.setdefault(r.fecha, r)          # la primera del día
    if not levantadas:
        return []
    primera = min(r.momento for r in levantadas.values()) - timedelta(hours=MAX_HORAS)
    acostadas = list(RegistroHabito.objects.filter(usuario=usuario, tipo='dormir', momento__gte=primera)
                     .order_by('momento'))
    resultado = []
    for fecha, lev in sorted(levantadas.items()):
        previas = [a for a in acostadas if lev.momento - timedelta(hours=MAX_HORAS) <= a.momento < lev.momento]
        if not previas:
            continue
        acostado = previas[-1]
        horas = (lev.momento - acostado.momento).total_seconds() / 3600
        if MIN_HORAS <= horas <= MAX_HORAS:
            resultado.append({'fecha': fecha, 'acostado': acostado.momento, 'levantado': lev.momento,
                              'horas': round(horas, 2)})
    return resultado


def resumen(usuario, desde, hasta):
    lista = noches(usuario, desde, hasta)
    promedio = round(sum(n['horas'] for n in lista) / len(lista), 2) if lista else None
    return {'desde': desde, 'hasta': hasta, 'promedio_horas': promedio, 'noches': lista}


def anoche(usuario):
    """Cuánto durmió la última noche (la de la mañana de hoy), o None si falta una de las horas."""
    hoy = timezone.localdate()
    lista = noches(usuario, hoy, hoy)
    return lista[0]['horas'] if lista else None
