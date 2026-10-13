"""Recomendar horas a partir de cómo usa la app la persona (no confundir con `sugerencias`, que arma los
recordatorios de los suplementos).

Mira a qué hora de verdad anota sus vasos, cuenta sus comidas, se levanta y se acuesta, en las últimas
semanas, y si lo que hace se aparta de las horas que tiene puestas propone cambiarlas. Solo propone
(la persona decide) y solo con datos suficientes: pocas muestras no dicen nada.
"""
from collections import defaultdict
from datetime import timedelta
from statistics import median

from django.utils import timezone

from nutricion import minutas
from nutricion.grupos import NOMBRE_TIEMPO
from nutricion.models import RegistroComida

from . import horarios, notificaciones
from .models import RegistroHabito

VENTANA_DIAS = 21
MINIMO_DIAS = 5
# Una diferencia menor que esto no vale la pena molestar.
UMBRAL_MIN = 30


def _min(momento):
    local = timezone.localtime(momento)
    return local.hour * 60 + local.minute


def _hhmm(minutos):
    minutos = int(round(minutos / 5) * 5) % 1440
    return f'{minutos // 60:02d}:{minutos % 60:02d}'


def _bonito(hhmm):
    return horarios.a_hora(hhmm).strftime('%I:%M %p').lstrip('0').replace('AM', 'a. m.').replace('PM', 'p. m.')


def _a_min(hora):
    return hora.hour * 60 + hora.minute


def de_horas(usuario):
    habitos = notificaciones.habitos_de(usuario)
    hoy = timezone.localdate()
    desde = hoy - timedelta(days=VENTANA_DIAS)
    lista = []

    # Comidas: la hora a la que cuenta lo que comió, menos el rato que tarda en llegar el aviso.
    minuta = minutas.vigente_de(usuario)
    tiempos = list(minuta.tiempos()) if minuta else []
    if tiempos:
        efectivas = horarios.horas_de_comidas(habitos, hoy, tiempos)
        por_tiempo = defaultdict(list)
        for r in RegistroComida.objects.filter(usuario=usuario, fecha__gte=desde):
            if timezone.localtime(r.momento).date() == r.fecha and r.tiempo in efectivas:
                por_tiempo[r.tiempo].append(_min(r.momento))
        for tiempo, valores in por_tiempo.items():
            if len(valores) < MINIMO_DIAS:
                continue
            sugerida = median(valores) - notificaciones.DESPUES_DE_COMER.total_seconds() / 60
            if abs(sugerida - _a_min(efectivas[tiempo])) >= UMBRAL_MIN:
                hora = _hhmm(sugerida)
                lista.append({
                    'id': f'comida-{tiempo}', 'tipo': 'comida',
                    'titulo': f'Tu {NOMBRE_TIEMPO[tiempo].lower()}',
                    'texto': (f'Sueles contar esta comida cerca de las {_bonito(_hhmm(median(valores)))}, así que '
                              f'comes hacia las {_bonito(hora)}; hoy la tienes a las '
                              f'{_bonito(efectivas[tiempo].isoformat("minutes"))}.'),
                    'actual': efectivas[tiempo].isoformat('minutes'), 'sugerida': hora,
                    'cambios': {'horas_comida': {**(habitos.horas_comida or {}), tiempo: hora}},
                })

    # Agua: de tu primer vaso al último, en los días con al menos dos.
    por_dia = defaultdict(list)
    for r in RegistroHabito.objects.filter(usuario=usuario, tipo='agua', fecha__gte=desde):
        por_dia[r.fecha].append(_min(r.momento))
    dias = [v for v in por_dia.values() if len(v) >= 2]
    if len(dias) >= MINIMO_DIAS:
        primero = median(min(v) for v in dias)
        ultimo = median(max(v) for v in dias)
        actuales = notificaciones._horas_agua(habitos, hoy, horarios.horas_de(habitos, hoy))
        if actuales:
            a_ini, a_fin = _min(actuales[0]), _min(actuales[-1])
            if max(abs(primero - a_ini), abs(ultimo - a_fin)) >= UMBRAL_MIN and primero < ultimo:
                inicio, fin = _hhmm(primero), _hhmm(ultimo)
                lista.append({
                    'id': 'agua', 'tipo': 'agua', 'titulo': 'Tu agua',
                    'texto': (f'Sueles tomar tu primer vaso hacia las {_bonito(inicio)} y el último hacia las '
                              f'{_bonito(fin)}. Los avisos van de {_bonito(_hhmm(a_ini))} a {_bonito(_hhmm(a_fin))}.'),
                    'actual': f'{_hhmm(a_ini)}–{_hhmm(a_fin)}', 'sugerida': f'{inicio}–{fin}',
                    'cambios': {'horas_agua': {'inicio': inicio, 'fin': fin}},
                })

    # Levantarse y acostarse.
    horas = horarios.horas_de(habitos, hoy)
    levantadas = {}
    for r in RegistroHabito.objects.filter(usuario=usuario, tipo='levantar', fecha__gte=desde).order_by('momento'):
        levantadas.setdefault(r.fecha, _min(r.momento))
    if len(levantadas) >= MINIMO_DIAS and horas['levantarse']:
        m = median(levantadas.values())
        if abs(m - _a_min(horas['levantarse'])) >= UMBRAL_MIN:
            hora = _hhmm(m)
            lista.append({
                'id': 'levantarse', 'tipo': 'levantarse', 'titulo': 'Cuándo te levantas',
                'texto': (f'Sueles levantarte hacia las {_bonito(hora)}; tienes puesto las '
                          f'{_bonito(horas["levantarse"].isoformat("minutes"))}.'),
                'actual': horas['levantarse'].isoformat('minutes'), 'sugerida': hora,
                'cambios': {'hora_levantarse': hora},
            })
    acostadas = defaultdict(list)
    for r in RegistroHabito.objects.filter(usuario=usuario, tipo='dormir', fecha__gte=desde).order_by('momento'):
        minutos = _min(r.momento)
        acostadas[r.fecha].append(minutos if minutos >= 12 * 60 else minutos + 1440)   # pasada la medianoche
    if len(acostadas) >= MINIMO_DIAS and horas['dormir']:
        meta = _a_min(horas['dormir']) + (1440 if horas['dormir'].hour < 12 else 0)
        m = median(v[-1] for v in acostadas.values())
        if abs(m - meta) >= UMBRAL_MIN:
            hora = _hhmm(m)
            lista.append({
                'id': 'acostarse', 'tipo': 'acostarse', 'titulo': 'Cuándo te acuestas',
                'texto': (f'Sueles acostarte hacia las {_bonito(hora)}; tienes puesto las '
                          f'{_bonito(horas["dormir"].isoformat("minutes"))}.'),
                'actual': horas['dormir'].isoformat('minutes'), 'sugerida': hora,
                'cambios': {'hora_dormir': hora},
            })
    for sugerencia in lista:
        sugerencia['texto'] = sugerencia['texto'].replace('..', '.')    # las horas terminan en «a. m.»
    return lista
