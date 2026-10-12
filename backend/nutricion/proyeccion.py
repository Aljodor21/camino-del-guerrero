"""Cuánto podría cambiar el peso hasta el próximo control, uniendo lo que ya sabemos de la persona.

Es una estimación aproximada, no una promesa, y dice sus supuestos. Junta:
- el gasto del día (peso, estatura, edad y sexo), que se vuelve a calcular cada semana con el
  peso nuevo: el cuerpo se adapta y por eso el cambio no es una línea recta;
- el entrenamiento, si el proceso lo tiene (enfoque, días y minutos); si no, es solo alimentación;
- las calorías de la minuta y, si su tabla está confirmada, lo que aporta la proteína en polvo;
- cuánto se cumple la minuta.
Dos límites mantienen la estimación en lo real: el cuerpo no cambia más de un 1 % de su peso por
semana, y el músculo que se puede ganar tiene un techo según el nivel de entrenamiento; lo que
sobra de un superávit es grasa y agua. La báscula no distingue músculo de grasa, por eso se
separan.
"""
from datetime import date, timedelta
from decimal import Decimal
from math import copysign

from core.exceptions import ReglaNegocioError
from users.models import ConfiguracionEntrenamiento
from users.procesos import proceso_de_referencia

from . import calculadora, comidas, minutas

KCAL_POR_KG = 7700
DIAS_SIN_FECHA = 28  # si no hay fecha de control, se calcula a cuatro semanas
VENTANA_CUMPLIMIENTO = 14
# El cuerpo no cambia más que esto por semana (como fracción de su peso).
TOPE_SEMANAL = 0.01
# Techo del músculo que se puede ganar al mes, como fracción del peso, según el nivel (valores
# de referencia usados en la literatura de hipertrofia: se gana más al empezar y cada vez menos).
MUSCULO_MES = {'principiante': 0.010, 'intermedio': 0.005, 'avanzado': 0.0025}
ENFOQUES_DE_FUERZA = ('fuerza', 'funcional', 'boxeo')
# Sin entrenamiento de fuerza casi todo lo que se sube es grasa y agua.
MUSCULO_SIN_FUERZA = 0.10
# Al bajar de peso, qué parte de lo perdido es músculo, con y sin entrenamiento de fuerza.
PERDIDA_MUSCULO = {True: 0.10, False: 0.25}

# MET de referencia por enfoque (Compendio de Actividades Físicas): cuántas veces el gasto en
# reposo cuesta cada actividad. Son valores aproximados para estimar, no medidas.
MET_ENFOQUE = {'boxeo': 7.0, 'fuerza': 5.0, 'funcional': 8.0, 'cardio_casa': 6.5, 'movilidad': 2.5}
NOMBRE_ENFOQUE = dict(ConfiguracionEntrenamiento.ENFOQUE_CHOICES)


def _edad(nacimiento, hoy):
    return hoy.year - nacimiento.year - ((hoy.month, hoy.day) < (nacimiento.month, nacimiento.day))


def _simular(peso, dias, ingesta, gasto_de):
    """Semana a semana: el gasto se recalcula con el peso del momento y el cambio de una semana
    no pasa del tope. Devuelve (kilos de cambio, si el tope se aplicó)."""
    inicial, transcurridos, limitado = peso, 0, False
    while transcurridos < dias:
        paso = min(7, dias - transcurridos)
        cambio = (ingesta - gasto_de(peso)) * paso / KCAL_POR_KG
        tope = TOPE_SEMANAL * peso * paso / 7
        if abs(cambio) > tope:
            cambio, limitado = copysign(tope, cambio), True
        peso += cambio
        transcurridos += paso
    return peso - inicial, limitado


def _composicion(cambio, peso, dias, entreno):
    """(músculo, grasa y agua) en kilos, con signo."""
    con_fuerza = bool(entreno and entreno.enfoque_entrenamiento in ENFOQUES_DE_FUERZA
                      and entreno.dias_entrenamiento >= 2)
    if cambio >= 0:
        techo = (MUSCULO_MES[entreno.nivel_actividad] * peso * dias / 30 * min(1, entreno.dias_entrenamiento / 3)
                 if con_fuerza else MUSCULO_SIN_FUERZA * cambio)
        musculo = min(cambio, techo)
        return round(musculo, 1), round(cambio - musculo, 1)
    perdido = -cambio * PERDIDA_MUSCULO[con_fuerza]
    return round(-perdido, 1), round(cambio + perdido, 1)


def _num(valor):
    return f'{valor:g}'.replace('.', ',')


def calorias_de_entreno(entreno, peso_kg):
    """kcal al día que suma el entrenamiento: lo que cuesta de más que estar en reposo, por
    sesión, repartido en los 7 días de la semana."""
    met = MET_ENFOQUE.get(entreno.enfoque_entrenamiento, 5.0)
    por_sesion = (met - 1) * peso_kg * entreno.duracion_sesion / 60
    return round(por_sesion * entreno.dias_entrenamiento / 7)


def _proteina(proceso, hoy):
    """Lo que aporta la proteína con tabla confirmada frente a lo que reemplaza de la minuta."""
    suplementos = [s for s in proceso.suplementos.all() if s.activo_en(hoy) and s.tipo == 'proteina']
    if not suplementos:
        return None
    con_tabla = [s for s in suplementos if s.tabla_nutricional]
    if not con_tabla:
        return {'sin_tabla': True}
    kcal = proteina_g = reemplazadas = 0.0
    leche_sin_tabla = False
    for s in con_tabla:
        porciones = float(s.porciones_dia)
        kcal += s.tabla_nutricional['kcal'] * porciones
        proteina_g += s.tabla_nutricional['proteina_g'] * porciones
        if s.leche_ml:
            leche = s.leche_nutricional
            if leche:
                # La leche de la porción también aporta: calorías y proteína por ml de su tabla.
                kcal += leche['kcal'] / leche['porcion_ml'] * s.leche_ml * porciones
                proteina_g += leche['proteina_g'] / leche['porcion_ml'] * s.leche_ml * porciones
            else:
                leche_sin_tabla = True
        for toma in s.tomas:
            reemplazadas += sum(calculadora.KCAL_PORCION.get(g, 0) * p for g, p in toma['reemplaza'].items())
    return {'sin_tabla': False, 'kcal': round(kcal), 'proteina_g': round(proteina_g),
            'reemplaza_kcal': round(reemplazadas), 'leche_sin_tabla': leche_sin_tabla}


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
    edad = _edad(usuario.fecha_nacimiento, hoy)
    sexo = usuario.sexo.nombre if usuario.sexo else ''

    def gasto_de(peso):
        reposo = calculadora.gasto_diario(peso, usuario.estatura, edad, sexo, 0)
        return reposo + (calorias_de_entreno(entreno, peso) if entreno else 0)

    extra_entreno = calorias_de_entreno(entreno, medicion.peso_kg) if entreno else 0
    gasto = round(gasto_de(medicion.peso_kg))

    proteina = _proteina(proceso, hoy)
    ajuste_proteina = 0
    if proteina and not proteina['sin_tabla']:
        ajuste_proteina = proteina['kcal'] - proteina['reemplaza_kcal']
    kcal_dia = minuta.kcal + ajuste_proteina
    balance = kcal_dia - gasto

    hasta = proceso.fecha_fin_plan
    dias = (hasta - hoy).days if hasta and hasta > hoy else DIAS_SIN_FECHA
    con_fecha = bool(hasta and hasta > hoy)

    cumplimiento = comidas.cumplimiento(usuario, hoy - timedelta(days=VENTANA_CUMPLIMIENTO), hoy)
    adherencia = cumplimiento['porcentaje']

    def escenario(nombre, porcentaje):
        # Si se come menos de lo pedido, la comida baja en proporción; la proteína se toma igual.
        ingesta = float(minuta.kcal * Decimal(porcentaje) / 100) + ajuste_proteina
        cambio, limitado = _simular(medicion.peso_kg, dias, ingesta, gasto_de)
        cambio = round(cambio, 1)
        musculo, grasa = _composicion(cambio, medicion.peso_kg, dias, entreno)
        return {'nombre': nombre, 'porcentaje': porcentaje, 'cambio_kg': cambio, 'musculo_kg': musculo,
                'grasa_kg': grasa, 'limitado': limitado, 'peso_final_kg': round(medicion.peso_kg + cambio, 1)}

    escenarios = [escenario('Cumpliendo todo tu plan', 100)]
    if adherencia is not None and adherencia < 100:
        escenarios.append(escenario(f'Con tu cumplimiento actual ({adherencia} %)', adherencia))

    detalle_entreno = None
    if entreno:
        detalle_entreno = {
            'enfoque': entreno.enfoque_entrenamiento, 'nombre': NOMBRE_ENFOQUE[entreno.enfoque_entrenamiento],
            'dias': entreno.dias_entrenamiento, 'duracion': entreno.duracion_sesion, 'kcal_dia': extra_entreno,
        }

    factores = [
        f'Peso actual: {_num(medicion.peso_kg)} kg (medido el {medicion.fecha.strftime("%d/%m/%Y")})',
        f'Estatura {usuario.estatura} cm, {edad} años' + (f', {sexo.lower()}' if sexo else ''),
        (f'Entrenamiento: {detalle_entreno["nombre"].lower()}, {entreno.dias_entrenamiento} días por semana de '
         f'{entreno.duracion_sesion} min: suma unas {extra_entreno} kcal al día'
         if entreno else
         'Sin entrenamiento: tu proceso es solo de alimentación, así que la estimación depende solo de lo que comes'),
        f'Gasto estimado: unas {gasto} kcal al día',
    ]
    if proteina is None:
        pass
    elif proteina['sin_tabla']:
        factores.append('Tu proteína no tiene tabla nutricional: léela desde su etiqueta (en Progreso › Agenda) '
                        'y la estimación se afina')
    else:
        factores.append(
            f'Tu proteína aporta {proteina["kcal"]} kcal y {proteina["proteina_g"]} g de proteína al día y reemplaza '
            f'{proteina["reemplaza_kcal"]} kcal de comida: {"+" if ajuste_proteina >= 0 else "−"}{abs(ajuste_proteina)} kcal')
    if proteina and not proteina['sin_tabla'] and proteina['leche_sin_tabla']:
        factores.append('La leche con la que mezclas tu proteína no tiene tabla nutricional: no suma calorías. '
                        'Agrégala en la proteína para afinar la estimación')
    factores += [
        f'Tu plan: {minuta.kcal} kcal al día' + (f' (con la proteína, {kcal_dia})' if ajuste_proteina else '')
        + f', {"+" if balance >= 0 else "−"}{abs(balance)} kcal frente a tu gasto',
        f'Periodo: {dias} días' + (f' hasta tu control del {hasta.strftime("%d/%m/%Y")}' if con_fecha
                                   else ' (sin fecha de control definida, se calcula a cuatro semanas)'),
        ('Cumplimiento de las últimas dos semanas: ' + (f'{adherencia} %' if adherencia is not None
                                                      else 'aún no cuentas comidas, se asume que cumples todo')),
    ]
    supuestos = [
        'El gasto se vuelve a calcular cada semana con tu peso nuevo, porque el cuerpo se adapta: por eso el cambio no es una línea recta.',
        f'El cuerpo no cambia más de un {TOPE_SEMANAL * 100:g} % de su peso por semana: es el tope de la estimación.',
        'El músculo que se puede ganar tiene un techo según tu nivel (' + (
            f'{entreno.get_nivel_actividad_display().lower()}: hasta un '
            f'{MUSCULO_MES[entreno.nivel_actividad] * 100:g} % de tu peso al mes, si entrenas fuerza'
            if entreno else 'sin entrenamiento de fuerza casi todo lo que subas será grasa y agua') + '); lo que sobra del superávit es grasa y agua.',
        'Las calorías de cada entrenamiento salen de valores de referencia por tipo de actividad: son aproximados.',
    ]
    return {
        'peso_actual_kg': medicion.peso_kg, 'dias': dias, 'fecha_control': hasta if con_fecha else None,
        'kcal_plan': minuta.kcal, 'gasto_kcal': gasto, 'balance_kcal': balance,
        'solo_alimentacion': entreno is None, 'entrenamiento': detalle_entreno,
        'proteina': (None if not proteina or proteina['sin_tabla'] else
                     {'kcal': proteina['kcal'], 'proteina_g': proteina['proteina_g']}),
        'cumplimiento': adherencia, 'escenarios': escenarios, 'factores': factores, 'supuestos': supuestos,
        'limitado': any(e['limitado'] for e in escenarios),
        'aviso': ('Es una estimación orientativa. El peso de la báscula mezcla músculo, grasa y agua, '
                  'así que no distingue cuánto de lo que subes es músculo. Tu nutricionista ajusta lo que haga falta.'),
    }
