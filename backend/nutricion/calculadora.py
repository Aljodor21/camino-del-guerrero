"""Minuta calculada para quien no tiene nutricionista.

Las calorías se estiman con la fórmula de Mifflin-St Jeor y la actividad, y se
ajustan según la fase (superávit en volumen, déficit en definición). La IA reparte
esas calorías en porciones por grupo y por comida; si su reparto no da las
calorías que toca, se usa uno fijo escalado.
"""
import logging
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from core.ai_service import AIService
from core.exceptions import ReglaNegocioError

from .grupos import NOMBRE_GRUPO
from .minutas import normalizar_porciones

log = logging.getLogger(__name__)

# Calorías aproximadas de una porción de intercambio de cada grupo.
KCAL_PORCION = {
    'sustitutos': 75, 'lacteos': 140, 'carnes': 130, 'leguminosas': 120, 'cereales': 100,
    'verduras': 25, 'frutas': 60, 'grasas': 45, 'semillas': 50, 'agua': 0,
}
# Reparto base en cinco comidas (unas 2.600 kcal): se escala a las calorías de cada uno.
PATRON = {
    'sustitutos': {'desayuno': 3},
    'lacteos':    {'onces': 1, 'algo': 1},
    'carnes':     {'almuerzo': 2, 'cena': 2},
    'cereales':   {'desayuno': 2, 'onces': 1, 'almuerzo': 4, 'algo': 1, 'cena': 2},
    'verduras':   {'almuerzo': 1, 'cena': 1},
    'frutas':     {'onces': 1, 'algo': 1},
    'grasas':     {'desayuno': 2, 'almuerzo': 3, 'cena': 2},
    'semillas':   {'dia': 2},
    'agua':       {'dia': 8},
}
AJUSTE_FASE = {'volumen': 350, 'definicion': -400, 'mantenimiento': 0}
AJUSTE_OBJETIVO = {'ganar_musculo': 300, 'bajar_peso': -400, 'mantener': 0, 'resistencia': 150}
PROTEINA = {'volumen': Decimal('1.8'), 'definicion': Decimal('2.0'), 'mantenimiento': Decimal('1.6')}
TOLERANCIA = Decimal('0.10')


def kcal_de(porciones):
    return sum(KCAL_PORCION[g] * Decimal(str(fila.get('dia', 0))) for g, fila in porciones.items())


def _medio(valor):
    return (Decimal(valor) * 2).quantize(Decimal(1), rounding=ROUND_HALF_UP) / 2


def _datos(usuario, proceso):
    medicion = usuario.mediciones.first() or proceso.medicion_inicial
    if not (medicion and usuario.estatura and usuario.fecha_nacimiento):
        raise ReglaNegocioError('Para calcular tu plan necesitamos tu peso, tu estatura y tu fecha de nacimiento.')
    hoy, nacimiento = date.today(), usuario.fecha_nacimiento
    edad = hoy.year - nacimiento.year - ((hoy.month, hoy.day) < (nacimiento.month, nacimiento.day))
    entreno = getattr(proceso, 'entrenamiento', None) if proceso.incluye_entrenamiento else None
    return {'peso': medicion.peso_kg, 'estatura': usuario.estatura, 'edad': edad,
            'sexo': usuario.sexo.nombre if usuario.sexo else '', 'dias': entreno.dias_entrenamiento if entreno else 0}


def gasto_diario(peso, estatura, edad, sexo, dias_entreno):
    """Calorías que se gastan al día: metabolismo basal de Mifflin-St Jeor por el factor de actividad."""
    ajuste_sexo = {'Masculino': 5, 'Femenino': -161}.get(sexo, -78)
    basal = 10 * peso + 6.25 * estatura - 5 * edad + ajuste_sexo
    actividad = {0: 1.4, 3: 1.55, 4: 1.6, 5: 1.7}.get(dias_entreno, 1.4)
    return basal * actividad


def objetivo_kcal(usuario, proceso):
    d = _datos(usuario, proceso)
    gasto = gasto_diario(d['peso'], d['estatura'], d['edad'], d['sexo'], d['dias'])
    ajuste = AJUSTE_FASE.get(proceso.fase, AJUSTE_OBJETIVO.get(proceso.objetivo, 0))
    kcal = int(round((gasto + ajuste) / 50) * 50)
    return kcal, int(round(gasto / 50) * 50), ajuste, d


def proteina_g_kg(proceso):
    if proceso.fase in PROTEINA:
        return PROTEINA[proceso.fase]
    return {'ganar_musculo': Decimal('1.8'), 'bajar_peso': Decimal('2.0')}.get(proceso.objetivo, Decimal('1.6'))


def escalar_patron(kcal):
    factor = Decimal(kcal) / kcal_de(normalizar_porciones(PATRON))
    porciones = {g: {t: (v if g == 'agua' else float(_medio(v * factor))) for t, v in fila.items()}
                 for g, fila in PATRON.items()}
    diferencia = Decimal(kcal) - kcal_de(normalizar_porciones(porciones))
    almuerzo = porciones['cereales']
    almuerzo['almuerzo'] = float(max(Decimal(1), Decimal(str(almuerzo['almuerzo']))
                                     + _medio(diferencia / KCAL_PORCION['cereales'])))
    return normalizar_porciones(porciones)


def calcular(usuario, proceso):
    """Propuesta de minuta para mostrarle al usuario antes de guardarla."""
    kcal, gasto, ajuste, d = objetivo_kcal(usuario, proceso)
    proteina = proteina_g_kg(proceso)
    porciones, recomendaciones = None, ''
    try:
        respuesta = AIService().calcular_minuta(
            usuario=usuario, proceso=proceso, kcal=kcal, proteina=proteina,
            kcal_porcion='\n'.join(f'- {g} ({NOMBRE_GRUPO[g]}): {v} kcal' for g, v in KCAL_PORCION.items() if v),
        )
        propuesta = normalizar_porciones(respuesta.get('porciones') or {})
        if abs(kcal_de(propuesta) - kcal) <= kcal * TOLERANCIA:
            porciones = propuesta
            recomendaciones = str(respuesta.get('recomendaciones') or '')[:1000]
        else:
            log.warning('La minuta de la IA no da las calorías (%s de %s).', kcal_de(propuesta), kcal)
    except Exception:
        log.exception('La IA no pudo calcular la minuta; se usa el reparto fijo.')
    if porciones is None:
        porciones = escalar_patron(kcal)

    verbo = 'suma' if ajuste > 0 else 'resta'
    explicacion = (f'Gastas unas {gasto} kcal al día ({str(d["peso"]).replace('.', ',')} kg, {d["estatura"]} cm, {d["edad"]} años'
                   + (f', {d["dias"]} entrenos por semana' if d['dias'] else '') + ')'
                   + (f' y tu meta {verbo} {abs(ajuste)} kcal' if ajuste else '') + f': quedan {kcal} kcal.')
    return {'origen': 'ia', 'porciones': porciones, 'kcal': kcal, 'proteina_g_kg': proteina,
            'recomendaciones': recomendaciones, 'explicacion': explicacion}
