"""Cuánto podría cambiar el peso hasta el próximo control, uniendo lo que ya sabemos de la persona.

Es una estimación, no una promesa: compara las calorías de la minuta con lo que se gasta al día
(peso actual, estatura, edad, sexo y días de entreno) y las convierte en kilos con la regla
de unos 7.700 kcal por kilo. El peso de la báscula mezcla músculo, grasa y agua, así que se
muestra un rango según cuánto se cumpla la minuta.
"""
from datetime import date, timedelta
from decimal import Decimal

from core.exceptions import ReglaNegocioError
from users.procesos import proceso_de_referencia

from . import calculadora, comidas, minutas

KCAL_POR_KG = 7700
DIAS_SIN_FECHA = 28  # si no hay fecha de control, se calcula a cuatro semanas
VENTANA_CUMPLIMIENTO = 14


def _edad(nacimiento, hoy):
    return hoy.year - nacimiento.year - ((hoy.month, hoy.day) < (nacimiento.month, nacimiento.day))


def _kg(kcal_dia, dias):
    return round(kcal_dia * dias / KCAL_POR_KG, 1)


def proyectar(usuario, hoy=None):
    hoy = hoy or date.today()
    proceso = proceso_de_referencia(usuario)
    if proceso is None or not proceso.incluye_alimentacion:
        raise ReglaNegocioError('Tu proceso no incluye alimentación.')
    minuta = minutas.vigente(proceso)
    if minuta is None or not minuta.kcal:
        raise ReglaNegocioError('Para estimar cuánto puedes cambiar necesitamos tu plan con sus calorías.')
    medicion = usuario.mediciones.order_by('-fecha', '-id').first() or proceso.medicion_inicial
    if not (medicion and usuario.estatura and usuario.fecha_nacimiento):
        raise ReglaNegocioError('Necesitamos tu peso, tu estatura y tu fecha de nacimiento.')

    entreno = getattr(proceso, 'entrenamiento', None) if proceso.incluye_entrenamiento else None
    dias_entreno = entreno.dias_entrenamiento if entreno else 0
    edad = _edad(usuario.fecha_nacimiento, hoy)
    sexo = usuario.sexo.nombre if usuario.sexo else ''
    gasto = round(calculadora.gasto_diario(medicion.peso_kg, usuario.estatura, edad, sexo, dias_entreno))
    balance = minuta.kcal - gasto

    hasta = proceso.fecha_fin_plan
    dias = (hasta - hoy).days if hasta and hasta > hoy else DIAS_SIN_FECHA
    con_fecha = bool(hasta and hasta > hoy)

    cumplimiento = comidas.cumplimiento(usuario, hoy - timedelta(days=VENTANA_CUMPLIMIENTO), hoy)
    adherencia = cumplimiento['porcentaje']

    def escenario(nombre, porcentaje):
        # Si se come menos de lo pedido, el balance baja en proporción a lo que se deja de comer.
        comido = minuta.kcal * Decimal(porcentaje) / 100
        kcal_dia = float(comido) - gasto
        cambio = _kg(kcal_dia, dias)
        return {'nombre': nombre, 'porcentaje': porcentaje, 'cambio_kg': cambio,
                'peso_final_kg': round(medicion.peso_kg + cambio, 1)}

    escenarios = [escenario('Cumpliendo todo tu plan', 100)]
    if adherencia is not None and adherencia < 100:
        escenarios.append(escenario(f'Con tu cumplimiento actual ({adherencia} %)', adherencia))

    factores = [
        f'Peso actual: {str(medicion.peso_kg).replace(".", ",")} kg (medido el {medicion.fecha.strftime("%d/%m/%Y")})',
        f'Estatura {usuario.estatura} cm, {edad} años' + (f', {sexo.lower()}' if sexo else ''),
        f'Gasto estimado: unas {gasto} kcal al día'
        + (f', con {dias_entreno} entrenos por semana' if dias_entreno else ', sin entrenamiento'),
        f'Tu plan: {minuta.kcal} kcal al día ({"+" if balance >= 0 else "−"}{abs(balance)} kcal frente a tu gasto)',
        f'Periodo: {dias} días' + (f' hasta tu control del {hasta.strftime("%d/%m/%Y")}' if con_fecha
                                   else ' (sin fecha de control definida, se calcula a cuatro semanas)'),
        ('Cumplimiento de las últimas dos semanas: ' + (f'{adherencia} %' if adherencia is not None
                                                      else 'aún no cuentas comidas, se asume que cumples todo')),
    ]
    return {
        'peso_actual_kg': medicion.peso_kg, 'dias': dias, 'fecha_control': hasta if con_fecha else None,
        'kcal_plan': minuta.kcal, 'gasto_kcal': gasto, 'balance_kcal': balance,
        'cumplimiento': adherencia, 'escenarios': escenarios, 'factores': factores,
        'aviso': ('Es una estimación orientativa. El peso de la báscula mezcla músculo, grasa y agua, '
                  'así que no distingue cuánto de lo que subes es músculo. Tu nutricionista ajusta lo que haga falta.'),
    }
