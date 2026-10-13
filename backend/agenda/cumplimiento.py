"""Cumplimiento global: qué tanto de lo que tocaba cada día se hizo.

Se arma solo con lo registrado (vasos, tomas, comidas contadas, entrenos y la hora de
acostarse), que no se edita. Cada día suma los bloques que le aplican:

- Antes de que empiece el proceso solo aplican el agua y el dormir.
- Con el proceso en marcha, además, las comidas (si hay plan de comida), las tomas de
  suplemento y el entreno (si tocaba ese día).

Un día pesa lo que lo que aplica: los pesos se reparten solo entre los bloques que
aplican. Los días de hoy se miden contra la meta completa del día, así que el porcentaje
sube mientras se va cumpliendo; los días pasados quedan cerrados.
"""
from collections import defaultdict
from datetime import time, timedelta
from decimal import Decimal

from django.utils import timezone

from core.exceptions import ReglaNegocioError
from nutricion import minutas
from nutricion.grupos import HORA_TIEMPO, NOMBRE_TIEMPO
from nutricion.menus import Contexto
from nutricion.models import RegistroComida, Suplemento
from progress.models import RegistroEntrenamiento
from routines.models import DiaRutina

from .models import RegistroHabito
from .notificaciones import VASO_ML, habitos_de

# Cuánto pesa cada bloque en el día cuando aplica.
PESOS = {'comidas': 40, 'entreno': 20, 'tomas': 15, 'agua': 15, 'dormir': 10}
NOMBRES = {'comidas': 'Comidas', 'entreno': 'Entreno', 'tomas': 'Proteína', 'agua': 'Agua', 'dormir': 'Dormir'}
ORDEN = list(PESOS)
# Un día cuenta para la racha desde este porcentaje.
UMBRAL_RACHA = 80
MAX_DIAS = 93  # un trimestre


def _porcentaje(hecho, meta):
    if not meta:
        return None
    return min(100, round(float(hecho) / float(meta) * 100))


def _bloque(id_, hecho, meta, porcentaje, detalle, faltas=()):
    return {'id': id_, 'nombre': NOMBRES[id_], 'peso': PESOS[id_], 'hecho': hecho, 'meta': meta,
            'porcentaje': porcentaje, 'detalle': detalle, 'faltas': list(faltas)}


class _Datos:
    """Todo lo registrado en el rango, leído una vez para no consultar por cada día."""

    def __init__(self, usuario, desde, hasta):
        self.usuario = usuario
        self.habitos = habitos_de(usuario)
        self.procesos = list(usuario.procesos.all())
        registros = RegistroHabito.objects.filter(usuario=usuario, fecha__range=(desde, hasta))
        self.agua = defaultdict(int)
        self.tomas = defaultdict(set)
        self.dormir = {}
        for r in registros:
            if r.tipo == 'agua':
                self.agua[r.fecha] += r.ml or VASO_ML
            elif r.tipo == 'toma':
                self.tomas[r.fecha].add((r.suplemento_id, r.tiempo))
            elif r.tipo == 'dormir':
                self.dormir.setdefault(r.fecha, r.momento)
        self.comidas = defaultdict(dict)
        for r in RegistroComida.objects.filter(usuario=usuario, fecha__range=(desde, hasta)):
            self.comidas[r.fecha][r.tiempo] = r
        self.entrenos = set(RegistroEntrenamiento.objects.filter(
            usuario=usuario, fecha__range=(desde, hasta)).values_list('fecha', flat=True))
        self.dias_entreno = set(DiaRutina.objects.filter(
            rutina__usuario=usuario, rutina__activa=True).values_list('dia_semana', flat=True))
        self.suplementos = list(Suplemento.objects.filter(usuario=usuario).select_related('proceso'))
        self.minuta = minutas.vigente_de(usuario)
        self.contexto = Contexto(usuario, self.minuta) if self.minuta else None
        self.inicio_minuta = timezone.localtime(self.minuta.fecha_creacion).date() if self.minuta else None

    def proceso_en(self, fecha):
        for p in self.procesos:
            if p.fecha_inicio <= fecha and (p.fecha_fin is None or fecha <= p.fecha_fin):
                return p
        return None


def _agua(datos, fecha):
    meta = datos.habitos.agua_ml
    if not meta:
        return None
    hecho = datos.agua.get(fecha, 0)
    porcentaje = _porcentaje(hecho, meta)
    return _bloque('agua', hecho, meta, porcentaje, f'{hecho} de {meta} ml',
                   [] if porcentaje == 100 else [f'Tomaste {hecho} de {meta} ml'])


def _dormir(datos, fecha):
    hora = datos.habitos.hora_dormir
    if not hora:
        return None
    momento = datos.dormir.get(fecha)
    hecho = momento is not None
    detalle = (f'Te acostaste a las {timezone.localtime(momento):%H:%M} (meta {hora:%H:%M})' if hecho
               else f'No marcaste que te acostaste (meta {hora:%H:%M})')
    return _bloque('dormir', int(hecho), 1, 100 if hecho else 0, detalle,
                   [] if hecho else ['No marcaste la hora de acostarte'])


def _tomas(datos, fecha):
    esperadas = [(s, t) for s in datos.suplementos if s.activo_en(fecha) for t in s.tomas]
    if not esperadas:
        return None
    hechas = datos.tomas.get(fecha, set())
    faltan = [f'{s.nombre_visible} ({NOMBRE_TIEMPO.get(Suplemento.clave_toma(t), "otra hora").lower()})'
              for s, t in esperadas if (s.id, Suplemento.clave_toma(t)) not in hechas]
    hecho = len(esperadas) - len(faltan)
    return _bloque('tomas', hecho, len(esperadas), _porcentaje(hecho, len(esperadas)),
                   f'{hecho} de {len(esperadas)} tomas', [f'Faltó {f}' for f in faltan])


def _comidas(datos, fecha, ahora):
    if datos.minuta is None or fecha < datos.inicio_minuta:
        return None
    pedido_total = comido_total = Decimal(0)
    contadas = 0
    faltas = []
    for tiempo in datos.minuta.tiempos():
        pedidos = datos.contexto.requerido(fecha, tiempo)
        pedido = sum(pedidos.values(), Decimal(0))
        pedido_total += pedido
        registro = datos.comidas[fecha].get(tiempo)
        if registro is not None:
            contadas += 1
            comido_total += sum((Decimal(str(v['comido'])) for v in registro.grupos.values()), Decimal(0))
            if any(v['comido'] < v['pedido'] for v in registro.grupos.values()):
                faltas.append(f'{NOMBRE_TIEMPO[tiempo]}: no completaste lo que pedía el plan')
        elif fecha < ahora.date() or ahora.time() >= time(*HORA_TIEMPO[tiempo]):
            faltas.append(f'{NOMBRE_TIEMPO[tiempo]}: sin contar')
    if not pedido_total:
        return None
    total = len(datos.minuta.tiempos())
    return _bloque('comidas', float(comido_total), float(pedido_total),
                   _porcentaje(comido_total, pedido_total),
                   f'{contadas} de {total} comidas contadas', faltas)


def _entreno(datos, fecha):
    if fecha.isoweekday() not in datos.dias_entreno:
        return None
    hecho = fecha in datos.entrenos
    return _bloque('entreno', int(hecho), 1, 100 if hecho else 0,
                   'Entrenaste' if hecho else 'Te tocaba entrenar', [] if hecho else ['No entrenaste'])


def _dia(datos, fecha, ahora):
    proceso = datos.proceso_en(fecha)
    bloques = [_agua(datos, fecha), _dormir(datos, fecha)]
    if proceso is not None:
        bloques += [_comidas(datos, fecha, ahora), _tomas(datos, fecha), _entreno(datos, fecha)]
    bloques = sorted((b for b in bloques if b), key=lambda b: ORDEN.index(b['id']))
    peso = sum(b['peso'] for b in bloques)
    porcentaje = round(sum(b['peso'] * b['porcentaje'] for b in bloques) / peso) if peso else None
    return {'fecha': fecha, 'porcentaje': porcentaje, 'en_proceso': proceso is not None,
            'es_hoy': fecha == ahora.date(), 'bloques': bloques}


def _rachas(dias):
    """(la que sigue vigente, la mejor): días seguidos desde el umbral. Hoy no corta la racha
    mientras no se acabe."""
    mejor = actual = 0
    for d in dias:
        if d['porcentaje'] is not None and d['porcentaje'] >= UMBRAL_RACHA:
            actual += 1
            mejor = max(mejor, actual)
        elif not d['es_hoy']:
            actual = 0
    return actual, mejor


def calcular(usuario, desde, hasta):
    """Dos porcentajes: `porcentaje` es el promedio de los días que ya van, y `porcentaje_periodo` es
    cuánto se lleva de **todo** el periodo (los días que faltan cuentan como lo que aún no se hace):
    una semana con 2 días al 60 % lleva el 60 % de lo que va, pero apenas el 17 % de la semana."""
    ahora = timezone.localtime()
    hasta_pedido = hasta
    hasta = min(hasta, ahora.date())
    desde = max(desde, timezone.localtime(usuario.date_joined).date())
    dias_periodo = max(0, (hasta_pedido - desde).days + 1)
    if hasta - desde > timedelta(days=MAX_DIAS):
        raise ReglaNegocioError(f'Pide máximo {MAX_DIAS} días a la vez.')
    if desde > hasta:
        return {'desde': desde, 'hasta': hasta, 'porcentaje': None, 'porcentaje_periodo': None,
                'dias_periodo': dias_periodo, 'dias': [], 'bloques': [],
                'racha_actual': 0, 'mejor_racha': 0, 'umbral_racha': UMBRAL_RACHA, 'dias_cumplidos': 0}

    datos = _Datos(usuario, desde, hasta)
    dias = [_dia(datos, desde + timedelta(days=i), ahora) for i in range((hasta - desde).days + 1)]

    con_porcentaje = [d['porcentaje'] for d in dias if d['porcentaje'] is not None]
    por_bloque = defaultdict(list)
    for d in dias:
        for b in d['bloques']:
            por_bloque[b['id']].append(b['porcentaje'])
    actual, mejor = _rachas(dias)
    return {
        'desde': desde, 'hasta': hasta,
        'porcentaje': round(sum(con_porcentaje) / len(con_porcentaje)) if con_porcentaje else None,
        'porcentaje_periodo': round(sum(con_porcentaje) / dias_periodo) if con_porcentaje and dias_periodo else None,
        'dias_periodo': dias_periodo,
        'dias_cumplidos': sum(1 for p in con_porcentaje if p >= UMBRAL_RACHA),
        'bloques': [{'id': i, 'nombre': NOMBRES[i], 'peso': PESOS[i],
                     'porcentaje': round(sum(por_bloque[i]) / len(por_bloque[i])), 'dias': len(por_bloque[i])}
                    for i in ORDEN if por_bloque[i]],
        'racha_actual': actual, 'mejor_racha': mejor, 'umbral_racha': UMBRAL_RACHA,
        'dias': dias,
    }
