"""Cuánto se duerme: de la hora en que la persona anota que se acostó a la hora en que anota que
se levantó. Es un cálculo sobre lo registrado, no se guarda: la hora del aviso confirmado puede
adelantarse un poco a la real, así que es un promedio aproximado."""
from datetime import timedelta

from django.utils import timezone

from . import horarios
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
    from .notificaciones import habitos_de      # evita un import circular
    habitos = habitos_de(usuario)
    personalizados = horarios.personalizados_entre(usuario, desde - timedelta(days=1), hasta)
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
            metas_noche = horarios.horas_de(habitos, acostado.fecha, personalizados)
            metas_dia = horarios.horas_de(habitos, fecha, personalizados)
            resultado.append({
                'fecha': fecha, 'acostado': acostado.momento, 'levantado': lev.momento, 'horas': round(horas, 2),
                # Minutos antes (−) o después (+) de la hora prevista de ese día; None si no había hora prevista.
                'dif_acostarse_min': horarios.minutos_de_diferencia(
                    timezone.localtime(acostado.momento), acostado.fecha, metas_noche['dormir'], madrugada=True),
                'dif_levantarse_min': horarios.minutos_de_diferencia(
                    timezone.localtime(lev.momento), fecha, metas_dia['levantarse']),
            })
    return resultado


def resumen(usuario, desde, hasta):
    lista = noches(usuario, desde, hasta)
    promedio = round(sum(n['horas'] for n in lista) / len(lista), 2) if lista else None

    def media(clave):
        valores = [n[clave] for n in lista if n[clave] is not None]
        return round(sum(valores) / len(valores)) if valores else None

    return {'desde': desde, 'hasta': hasta, 'promedio_horas': promedio, 'noches': lista,
            'promedio_acostarse_min': media('dif_acostarse_min'),
            'promedio_levantarse_min': media('dif_levantarse_min')}


def anoche(usuario):
    """La última noche (la de la mañana de hoy) con sus horas y diferencias, o None si falta una de las dos."""
    hoy = timezone.localdate()
    lista = noches(usuario, hoy, hoy)
    return lista[0] if lista else None
