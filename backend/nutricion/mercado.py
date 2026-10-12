"""Lista de mercado exacta: sale de lo que cada comida del menú pide, sin IA.

Lo perecedero (carnes, huevos, lácteos, frutas, verduras, aguacate, pan) se compra cada semana
con el menú de esa semana, porque el menú cambia. Lo que dura (arroz, avena, aceite, semillas,
leguminosas) se compra para 15 días o un mes con lo que el menú pide en promedio por semana.
"""
import calendar
from collections import defaultdict
from datetime import date
from decimal import Decimal

from . import cantidades, menus

DIAS_POR_PERIODO = {'semana': 7, 'quincena': 15, 'mes': 30}
FRECUENCIA_POR_PERIODO = {'semana': 'semanal', 'quincena': 'quincenal', 'mes': 'mensual'}
# Cuánto se considera que dura lo ya comprado (un par de días menos que el periodo).
VENTANA_YA_COMPRADO = {'quincena': 13, 'mes': 28}
DIAS_PROMOCION_COLANTA = (15, 30)

PALABRAS_QUE_DURAN = ('arroz', 'avena', 'pasta', 'fideo', 'quinua', 'cereal', 'harina', 'galleta')

CONSEJOS = [
    'Granos, avena, aceite, enlatados y aseo: compáralos en Ara o en D1, donde suelen salir más baratos.',
    'En lácteos, compara la marca propia de Ara o D1 con la marca que ya compras.',
    'El 15 y el 30 de cada mes hay promoción en Colanta: si puedes, deja los lácteos para esa fecha.',
]


def proxima_promocion_colanta(desde):
    """El próximo 15 o 30 (en febrero, el último día del mes), contando hoy."""
    for meses in range(3):
        mes = desde.month - 1 + meses
        anio, mes = desde.year + mes // 12, mes % 12 + 1
        ultimo = calendar.monthrange(anio, mes)[1]
        for dia in DIAS_PROMOCION_COLANTA:
            fecha = date(anio, mes, min(dia, ultimo))
            if fecha >= desde:
                return fecha


def dura(alimento):
    """Se puede comprar para varias semanas."""
    if alimento.grupo in ('semillas', 'leguminosas'):
        return True
    if alimento.grupo == 'grasas':
        return alimento.nombre.startswith('Aceite')
    if alimento.grupo == 'cereales':
        return any(p in alimento.nombre.lower() for p in PALABRAS_QUE_DURAN)
    return False


def _cantidad(alimento, porciones):
    peso = cantidades.gramos(alimento.gramos, porciones)
    if alimento.grupo == 'libres':
        return 'Al gusto'
    if peso and peso >= 1000:
        return f'{peso / 1000:.1f} kg'.replace('.', ',')
    return f'{peso} g' if peso else cantidades.escalar(alimento.medida, porciones)


def armar(menu, siguiente, num_personas, periodo, ya_comprados=()):
    """{'categorias': [{'categoria', 'items': [{'nombre', 'cantidad', 'frecuencia'}]}]}.

    `siguiente`: el menú de la semana que viene, si existe (ayuda a promediar lo que dura).
    `ya_comprados`: nombres de lo que dura y se compró hace poco; no se vuelve a pedir."""
    dias = DIAS_POR_PERIODO[periodo]
    semana_actual = menus.consolidado(menu)
    semanas = [semana_actual] + ([menus.consolidado(siguiente)] if siguiente else [])
    categorias = defaultdict(list)

    def agregar(alimento, porciones, frecuencia):
        categorias[menus.CATEGORIA_MERCADO[alimento.grupo]].append({
            'nombre': cantidades.nombre_visible(alimento),
            'cantidad': _cantidad(alimento, porciones * num_personas),
            'frecuencia': frecuencia,
        })

    for alimento, porciones in semana_actual.items():
        if periodo != 'semana' and dura(alimento):
            continue
        agregar(alimento, porciones, 'semanal')
    if periodo != 'semana':
        # Lo que dura: lo que el menú pide en promedio por semana, para todo el periodo.
        alimentos = {a for semana in semanas for a in semana if dura(a)}
        for alimento in alimentos:
            if cantidades.nombre_visible(alimento) in ya_comprados:
                continue
            promedio = sum((s.get(alimento, Decimal(0)) for s in semanas), Decimal(0)) / len(semanas)
            agregar(alimento, promedio * dias / 7, FRECUENCIA_POR_PERIODO[periodo])
    for items in categorias.values():
        items.sort(key=lambda i: i['nombre'])
    return {'categorias': [{'categoria': c, 'items': i} for c, i in categorias.items()],
            'consejos_compra': CONSEJOS}
