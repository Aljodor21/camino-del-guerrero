"""Logros: la racha (con un comodín por semana), los hitos y el capítulo de cada semana.

Todo sale de lo registrado (vasos, tomas, comidas contadas, entrenos, mediciones), que no se
edita; por eso no se guarda ningún contador: se calcula siempre y no se puede inflar. Solo se
recuerda qué hitos la persona ya vio celebrar (`HitoVisto`).

Ningún logro premia comer menos, pasarse de agua ni saltarse comidas: cuentan lo que pidió el
plan de la nutricionista, nada más.
"""
from collections import defaultdict
from datetime import timedelta

from django.utils import timezone

from core.exceptions import ReglaNegocioError
from nutricion.models import RegistroComida
from progress.models import Medicion, RegistroEntrenamiento

from . import cumplimiento
from .models import HitoVisto, RegistroHabito

# Hasta cuántos días atrás se mira para la racha y los hitos.
HISTORIAL_DIAS = 365
# Un hito logrado hace más que esto ya no se celebra con fanfarria al abrir la app.
DIAS_DE_FIESTA = 2

RACHAS = (3, 7, 14, 30, 60, 90)
AGUA_LITROS = (10, 50, 100)
ENTRENOS = (1, 10, 25, 50)
COMIDAS = (1, 25, 100)
TOMAS = (10, 50)
DIAS_COMPLETOS = (1, 7, 30)
NIVELES = ('bronce', 'plata', 'oro')


def _dias(usuario, hasta=None):
    """Los días medidos desde que se registró la persona (máx. un año), del más viejo al más nuevo."""
    ahora = timezone.localtime()
    hasta = min(hasta or ahora.date(), ahora.date())
    desde = max(timezone.localtime(usuario.date_joined).date(), hasta - timedelta(days=HISTORIAL_DIAS))
    if desde > hasta:
        return [], None
    datos = cumplimiento._Datos(usuario, desde, hasta)
    return [cumplimiento._dia(datos, desde + timedelta(days=i), ahora) for i in range((hasta - desde).days + 1)], datos


def calcular_racha(dias, umbral=cumplimiento.UMBRAL_RACHA):
    """Días seguidos desde el umbral. Un día que se queda corto no corta la racha si en esa semana
    (lunes a domingo) aún no se ha usado el comodín: se «salva» sin sumar. Hoy no corta mientras no
    se acabe. Devuelve la racha, la mejor, los días salvados y las fechas en que se llegó a cada meta."""
    actual = mejor = 0
    semanas_usadas, salvados = set(), []
    alcanzada = {}
    for d in dias:
        p = d['porcentaje']
        if p is not None and p >= umbral:
            actual += 1
            mejor = max(mejor, actual)
            for meta in RACHAS:
                if actual >= meta:
                    alcanzada.setdefault(meta, d['fecha'])
        elif d['es_hoy']:
            continue
        else:
            semana = d['fecha'].isocalendar()[:2]
            if actual > 0 and p is not None and semana not in semanas_usadas:
                semanas_usadas.add(semana)
                salvados.append(d['fecha'])
            else:
                actual = 0
    hoy = timezone.localdate()
    return {
        'actual': actual, 'mejor': mejor, 'umbral': umbral,
        'comodin_disponible': hoy.isocalendar()[:2] not in semanas_usadas,
        'dias_salvados': salvados,
    }, alcanzada


def _fecha_en_que_se_llego(fechas, meta):
    """La fecha del registro número `meta` (1 = el primero), o None si aún no llega."""
    fechas = sorted(fechas)
    return fechas[meta - 1] if len(fechas) >= meta else None


def _hito(id_, grupo, nivel, nombre, descripcion, actual, meta, logrado_en):
    return {'id': id_, 'grupo': grupo, 'nivel': NIVELES[nivel], 'nombre': nombre,
            'descripcion': descripcion, 'actual': min(actual, meta), 'meta': meta,
            'logrado_en': logrado_en, 'logrado': logrado_en is not None}


def _hitos(usuario, dias, datos, alcanzada, racha):
    hitos = []
    # Racha
    for i, meta in enumerate(RACHAS):
        hitos.append(_hito(f'racha-{meta}', 'racha', min(i // 2, 2), f'{meta} días seguidos',
                           f'Cumple {meta} días seguidos desde el {racha["umbral"]} %.', racha['mejor'], meta,
                           alcanzada.get(meta)))

    # Días completos (100 %)
    completos = [d['fecha'] for d in dias if d['porcentaje'] == 100]
    for i, meta in enumerate(DIAS_COMPLETOS):
        nombre = 'Tu primer día completo' if meta == 1 else f'{meta} días completos'
        hitos.append(_hito(f'completos-{meta}', 'dias', i, nombre, 'Cumple al 100 % todo lo que tocaba.',
                           len(completos), meta, _fecha_en_que_se_llego(completos, meta)))

    # Una semana entera desde el umbral
    semanas = defaultdict(list)
    for d in dias:
        semanas[d['fecha'].isocalendar()[:2]].append(d)
    perfectas = sorted(max(x['fecha'] for x in v) for v in semanas.values()
                       if len(v) == 7 and all((x['porcentaje'] or 0) >= racha['umbral'] for x in v))
    hitos.append(_hito('semana-completa', 'dias', 2, 'Una semana completa',
                       f'Los 7 días de una semana (lunes a domingo) desde el {racha["umbral"]} %.',
                       len(perfectas), 1, perfectas[0] if perfectas else None))

    # Agua acumulada (solo lo que se tomó de verdad)
    por_dia_ml = sorted(datos.agua.items()) if datos else []
    acumulado, llegada = 0, {}
    for fecha, ml in por_dia_ml:
        acumulado += ml
        for litros in AGUA_LITROS:
            if acumulado >= litros * 1000:
                llegada.setdefault(litros, fecha)
    for i, litros in enumerate(AGUA_LITROS):
        hitos.append(_hito(f'agua-{litros}', 'agua', i, f'{litros} litros de agua',
                           f'Suma {litros} litros tomados.', int(acumulado // 1000), litros, llegada.get(litros)))

    # Entrenos
    entrenos = list(RegistroEntrenamiento.objects.filter(usuario=usuario).values_list('fecha', flat=True))
    for i, meta in enumerate(ENTRENOS):
        nombre = 'Tu primer entreno' if meta == 1 else f'{meta} entrenos'
        hitos.append(_hito(f'entreno-{meta}', 'entreno', min(i, 2), nombre, 'Entrena y regístralo.',
                           len(entrenos), meta, _fecha_en_que_se_llego(entrenos, meta)))

    # Comidas contadas
    comidas = list(RegistroComida.objects.filter(usuario=usuario).values_list('fecha', flat=True))
    for i, meta in enumerate(COMIDAS):
        nombre = 'Tu primera comida contada' if meta == 1 else f'{meta} comidas contadas'
        hitos.append(_hito(f'comidas-{meta}', 'comida', i, nombre, 'Cuenta lo que comes para ver cómo vas con tu plan.',
                           len(comidas), meta, _fecha_en_que_se_llego(comidas, meta)))

    # Tomas de proteína
    tomas = list(RegistroHabito.objects.filter(usuario=usuario, tipo='toma').values_list('fecha', flat=True))
    for i, meta in enumerate(TOMAS):
        hitos.append(_hito(f'tomas-{meta}', 'proteina', i, f'{meta} tomas de proteína',
                           'Confirma tus tomas.', len(tomas), meta, _fecha_en_que_se_llego(tomas, meta)))

    # Mediciones
    mediciones = list(Medicion.objects.filter(usuario=usuario).values_list('fecha', flat=True))
    for i, meta in enumerate((1, 4)):
        nombre = 'Tu primera medición' if meta == 1 else '4 mediciones'
        hitos.append(_hito(f'mediciones-{meta}', 'medicion', i, nombre, 'Mídete y registra tu progreso.',
                           len(mediciones), meta, _fecha_en_que_se_llego(mediciones, meta)))
    return hitos


def logros(usuario):
    """La racha, los hitos (con cuáles son nuevos) y cómo va hoy. Los hitos de hace tiempo que la
    persona nunca vio se dan por vistos sin fiesta, para que al estrenar esto no salgan todos a la vez."""
    dias, datos = _dias(usuario)
    racha, alcanzada = calcular_racha(dias)
    hitos = _hitos(usuario, dias, datos, alcanzada, racha)

    vistos = set(HitoVisto.objects.filter(usuario=usuario).values_list('clave', flat=True))
    reciente = timezone.localdate() - timedelta(days=DIAS_DE_FIESTA)
    viejos = [h['id'] for h in hitos if h['logrado'] and h['id'] not in vistos and h['logrado_en'] < reciente]
    HitoVisto.objects.bulk_create([HitoVisto(usuario=usuario, clave=c) for c in viejos], ignore_conflicts=True)
    vistos.update(viejos)
    for h in hitos:
        h['nuevo'] = h['logrado'] and h['id'] not in vistos

    hoy = next((d for d in dias if d['es_hoy']), None)
    return {
        'racha': racha, 'hitos': hitos,
        'hoy': {'porcentaje': hoy['porcentaje'], 'en_proceso': hoy['en_proceso']} if hoy else None,
        'logrados': sum(h['logrado'] for h in hitos), 'total': len(hitos),
    }


def marcar_vistos(usuario, claves):
    """La persona ya vio celebrar estos hitos. Solo cuentan los que de verdad logró."""
    logrados = {h['id'] for h in logros(usuario)['hitos'] if h['logrado']}
    validas = [c for c in claves if c in logrados]
    HitoVisto.objects.bulk_create([HitoVisto(usuario=usuario, clave=c) for c in validas], ignore_conflicts=True)
    return len(validas)


# ── El capítulo de la semana ────────────────────────────────────────────────

def lunes_de(fecha):
    return fecha - timedelta(days=fecha.weekday())


def _titulo(porcentaje, completa=True):
    if not completa:
        if porcentaje is None:
            return 'Tu semana empieza', 'Todavía no hay nada que medir en esta semana.'
        if porcentaje >= 80:
            return 'Así va tu semana', 'Buen comienzo: sigue así.'
        return 'Así va tu semana', 'Aún hay semana por delante para sumar.'
    if porcentaje is None:
        return 'Una semana en blanco', 'Todavía no hay nada que medir en esta semana.'
    if porcentaje >= 90:
        return 'Semana de guerrero', 'Casi todo lo que tocaba, lo hiciste.'
    if porcentaje >= 70:
        return 'Semana firme', 'Buen ritmo: la base ya está puesta.'
    if porcentaje >= 40:
        return 'Semana de avance', 'Hay camino recorrido y hay dónde mejorar.'
    return 'Semana para retomar', 'No pasa nada: la siguiente empieza el lunes.'


def capitulo(usuario, lunes):
    """La semana de lunes a domingo: cómo le fue, frente a la anterior, y qué mirar."""
    if lunes.weekday() != 0:
        raise ReglaNegocioError('La semana empieza un lunes.')
    domingo = lunes + timedelta(days=6)
    hoy = timezone.localdate()
    completa = domingo < hoy
    if lunes > hoy:
        raise ReglaNegocioError('Esa semana aún no llega.')
    actual = cumplimiento.calcular(usuario, lunes, domingo)
    anterior = cumplimiento.calcular(usuario, lunes - timedelta(days=7), lunes - timedelta(days=1))
    dias = [d for d in actual['dias'] if d['porcentaje'] is not None]
    mejor = max(dias, key=lambda d: d['porcentaje'], default=None)
    flojo = min(actual['bloques'], key=lambda b: b['porcentaje'], default=None)
    titulo, frase = _titulo(actual['porcentaje'], completa)
    # Solo una semana terminada se compara con la anterior: una a medias saldría siempre más baja.
    delta = (actual['porcentaje'] - anterior['porcentaje']
             if completa and actual['porcentaje'] is not None and anterior['porcentaje'] is not None else None)
    hitos = [h for h in logros(usuario)['hitos'] if h['logrado'] and lunes <= h['logrado_en'] <= domingo]
    return {
        'lunes': lunes, 'domingo': domingo, 'completa': completa, 'es_actual': lunes <= hoy <= domingo,
        # El promedio de los días que van y lo que lleva de la semana entera (7 días).
        'porcentaje': actual['porcentaje'], 'porcentaje_semana': actual['porcentaje_periodo'],
        'dias_que_van': len(actual['dias']),
        'anterior': anterior['porcentaje'], 'diferencia': delta,
        'titulo': titulo, 'frase': frase,
        'estaciones': [{'fecha': d['fecha'], 'porcentaje': d['porcentaje'], 'es_hoy': d['es_hoy']}
                       for d in actual['dias']],
        'mejor_dia': {'fecha': mejor['fecha'], 'porcentaje': mejor['porcentaje']} if mejor else None,
        'para_mirar': ({'nombre': flojo['nombre'], 'porcentaje': flojo['porcentaje']}
                       if flojo and flojo['porcentaje'] < 100 else None),
        'bloques': actual['bloques'], 'hitos': hitos,
    }
