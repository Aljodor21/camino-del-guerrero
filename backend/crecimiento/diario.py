"""Diario de gastos («Sana tus finanzas», capítulo 2, paso 1).

Es el ejercicio tal cual, con dos mejoras:
- **La lista de gastos** (`Rubro`): las categorías y rubros del libro, con su valor y cuánto es cerebral (lo
  demás es emocional; un gasto mixto se parte así). Cada rubro dice cada cuánto se paga: los de cada mes van
  tal cual; los anuales (o semestrales) se suman en el año y se dividen entre 12; los hormiga (de todos los
  días) se multiplican por los días del mes. Al final todo es **un solo gasto mensual**.
- **El registro** (`Gasto`, `DiaSinGasto`): lo que se gastó de verdad cada día de este mes (hasta 7 días atrás, por si se pasó), sin engañarse; un día
  está «al día» si tiene gastos anotados o si la persona dijo que no gastó.
"""
import calendar
import math
from datetime import time, timedelta

from django.db import transaction
from django.utils import timezone

from agenda.horarios import a_hora
from core.exceptions import ReglaNegocioError

from .models import DiaSinGasto, Gasto, Rubro
from .tipos_base import Tipo

# Las categorías y los rubros del diario de gastos del libro.
CATEGORIAS = [
    ('hogar', 'Gastos del hogar', ['Cuota préstamo hipotecario', 'Arriendo', 'Energía', 'Gas',
                                   'Servicio de agua y alcantarillado', 'Teléfono', 'TV cable', 'Internet',
                                   'Empleada / Niñera', 'Mantenimiento', 'Mercado', 'Administración']),
    ('transporte', 'Transporte', ['Cuota crédito del vehículo', 'SOAT', 'Combustible', 'Revisión tecnomecánica',
                                  'Transporte en servicio público', 'Cambio de aceite', 'Cambio de llantas',
                                  'Lavada del vehículo', 'Impuesto de rodamiento']),
    ('salud', 'Salud', ['Plan complementario', 'Consultas médicas / odontológicas', 'Medicamentos', 'Copagos',
                        'Atención domiciliaria']),
    ('donaciones', 'Donaciones', ['Donación familiar', 'Donación política / religiosa', 'Donación de caridad']),
    ('estilo_vida', 'Estilo de vida', ['Peluquería', 'Gimnasio', 'Ropa', 'Lavandería', 'Restaurante / Domicilios',
                                       'Mascotas']),
    ('entretenimiento', 'Entretenimiento', ['Música', 'Teatro / Cines', 'Conciertos', 'Libros', 'Fotografía',
                                            'Deportes', 'Vacaciones', 'Rumba', 'Mecato']),
    ('seguros_ahorros', 'Seguros y ahorros', ['Seguro del vehículo', 'Póliza de educación', 'Seguro de vida',
                                              'Ahorro', 'Póliza del hogar']),
    ('obligaciones', 'Obligaciones', ['Colegio', 'Universidad', 'Tarjeta de crédito', 'Impuestos nacionales',
                                      'Impuestos locales', 'Créditos de consumo', 'Deudas con terceros',
                                      'Créditos bancarios', 'Cuota alimentaria']),
    ('suscripciones', 'Suscripciones', ['Periódicos', 'Revistas', 'Clubes sociales', 'Plataformas de video',
                                        'Plataformas de música']),
    ('otros', 'Otros', []),
]
NOMBRE_CATEGORIA = {c: n for c, n, _ in CATEGORIAS}
# Los rubros de la lista que se pagan una vez al año (se pueden cambiar).
ANUALES = {'SOAT', 'Revisión tecnomecánica', 'Impuesto de rodamiento', 'Vacaciones', 'Impuestos nacionales',
           'Impuestos locales'}
FRECUENCIAS = {f for f, _ in Rubro.FRECUENCIAS}
DIAS_ATRAS = 7
HORA_AVISO = time(20, 0)
MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre',
         'noviembre', 'diciembre']


def pesos(valor):
    return '$' + f'{round(valor):,}'.replace(',', '.')


def _mes_actual():
    hoy = timezone.localdate()
    return hoy.replace(day=1), hoy.replace(day=calendar.monthrange(hoy.year, hoy.month)[1])


# ── La lista de gastos ─────────────────────────────────────────────────────────
def _factor(frecuencia, dias_mes):
    """Cuánto de un pago cae en un mes."""
    return {'mensual': 1, 'anual': 1 / 12, 'semestral': 2 / 12, 'hormiga': dias_mes}[frecuencia]


def meses_que_faltan(mes_pago, frecuencia, mes):
    """Meses que faltan para el próximo pago contando este (marzo visto desde octubre: 5). 0 si toca este mes."""
    pagos = [mes_pago] if frecuencia == 'anual' else [mes_pago, (mes_pago + 5) % 12 + 1]
    return min((p - mes) % 12 for p in pagos)


def rubro(r):
    """Un rubro con su parte del mes: lo que se suma a «cuánto se va a gastar este mes»."""
    factor = _factor(r['frecuencia'], r['dias_mes'])
    mensual = math.ceil(r['valor'] * factor)
    cerebral = math.ceil(r['cerebral'] * factor)
    datos = {**r, 'emocional': r['valor'] - r['cerebral'],
             'mensual': mensual, 'mensual_cerebral': cerebral, 'mensual_emocional': mensual - cerebral}
    if r['frecuencia'] in ('anual', 'semestral'):
        datos['al_anio'] = r['valor'] * (2 if r['frecuencia'] == 'semestral' else 1)
        if r.get('mes_pago'):
            faltan = meses_que_faltan(r['mes_pago'], r['frecuencia'], timezone.localdate().month)
            datos['meses_faltan'] = faltan
            datos['ahorro_hasta_pago'] = math.ceil(r['valor'] / faltan) if faltan else r['valor']
    if r['frecuencia'] == 'hormiga':
        datos['al_anio'] = mensual * 12
    return datos


def _de_modelo(r):
    return {'categoria': r.categoria, 'nombre': r.nombre, 'frecuencia': r.frecuencia, 'valor': r.valor,
            'cerebral': r.cerebral, 'dias_mes': r.dias_mes, 'mes_pago': r.mes_pago}


def rubros_de(proyecto):
    """(rubros, guardados): los de la persona o, si aún no ha guardado, la lista del libro en blanco."""
    guardados = [_de_modelo(r) for r in proyecto.rubros.all()]
    if guardados:
        return guardados, True
    return [{'categoria': c, 'nombre': n, 'frecuencia': 'anual' if n in ANUALES else 'mensual', 'valor': 0,
             'cerebral': 0, 'dias_mes': 30, 'mes_pago': None}
            for c, _, nombres in CATEGORIAS for n in nombres], False


def _entero(valor, minimo=0, maximo=10**12):
    try:
        n = int(valor or 0)
    except (TypeError, ValueError):
        raise ReglaNegocioError('Los valores van en pesos, sin puntos ni comas.')
    if not minimo <= n <= maximo:
        raise ReglaNegocioError('Ese valor no es válido.')
    return n


@transaction.atomic
def guardar_rubros(proyecto, rubros):
    """Reemplaza la lista de gastos con la que manda la persona."""
    limpios = []
    for i, r in enumerate(rubros):
        if not isinstance(r, dict):
            raise ReglaNegocioError('Cada gasto va con su categoría, su nombre y su valor.')
        categoria, nombre = r.get('categoria'), str(r.get('nombre') or '').strip()
        if categoria not in NOMBRE_CATEGORIA or not nombre or len(nombre) > 80:
            raise ReglaNegocioError('Cada gasto va con su categoría y su nombre.')
        frecuencia = r.get('frecuencia') or 'mensual'
        if frecuencia not in FRECUENCIAS:
            raise ReglaNegocioError(f'En «{nombre}», di cada cuánto se paga.')
        valor, cerebral = _entero(r.get('valor')), _entero(r.get('cerebral'))
        if cerebral > valor:
            raise ReglaNegocioError(f'En «{nombre}», lo cerebral no puede pasar del valor.')
        mes_pago = r.get('mes_pago') or None
        if mes_pago is not None:
            mes_pago = _entero(mes_pago, 1, 12)
        limpios.append(Rubro(proyecto=proyecto, categoria=categoria, nombre=nombre, frecuencia=frecuencia,
                             valor=valor, cerebral=cerebral, dias_mes=_entero(r.get('dias_mes') or 30, 1, 31),
                             mes_pago=mes_pago if frecuencia in ('anual', 'semestral') else None, orden=i))
    proyecto.rubros.all().delete()
    Rubro.objects.bulk_create(limpios)


# ── El registro ────────────────────────────────────────────────────────────────
def dias_al_dia(proyecto, hoy=None):
    """(al_dia, transcurridos) de este mes hasta hoy, desde que empezó el diario."""
    hoy = hoy or timezone.localdate()
    inicio = max(hoy.replace(day=1), proyecto.creado)
    if hoy < inicio:
        return 0, 0
    con_gasto = set(proyecto.gastos.filter(fecha__range=(inicio, hoy)).values_list('fecha', flat=True))
    sin_gasto = set(proyecto.dias_sin_gasto.filter(fecha__range=(inicio, hoy)).values_list('fecha', flat=True))
    return len(con_gasto | sin_gasto), (hoy - inicio).days + 1


def dia_al_dia(proyecto, fecha):
    return (proyecto.gastos.filter(fecha=fecha).exists()
            or proyecto.dias_sin_gasto.filter(fecha=fecha).exists())


def _validar_fecha(fecha):
    """Un gasto se puede anotar hasta 7 días después, por si se pasó; el futuro no."""
    hoy = timezone.localdate()
    if fecha > hoy:
        raise ReglaNegocioError('Ese día todavía no llega.')
    if fecha < hoy - timedelta(days=DIAS_ATRAS):
        raise ReglaNegocioError(f'Solo se anota lo de los últimos {DIAS_ATRAS} días.')


@transaction.atomic
def anotar_gasto(proyecto, fecha, valor, descripcion, categoria, clase):
    _validar_fecha(fecha)
    if categoria not in NOMBRE_CATEGORIA:
        raise ReglaNegocioError('Elige una categoría.')
    if clase not in ('cerebral', 'emocional'):
        raise ReglaNegocioError('Di si el gasto es cerebral o emocional.')
    valor = _entero(valor)
    if not valor:
        raise ReglaNegocioError('Escribe cuánto gastaste.')
    descripcion = (descripcion or '').strip()
    if not descripcion:
        raise ReglaNegocioError('Escribe en qué gastaste.')
    # Si ese día había dicho que no gastó, lo que cuenta es lo que anota ahora.
    proyecto.dias_sin_gasto.filter(fecha=fecha).delete()
    return Gasto.objects.create(proyecto=proyecto, fecha=fecha, valor=valor, descripcion=descripcion[:120],
                                categoria=categoria, clase=clase)


def borrar_gasto(gasto):
    """Solo el mismo día que se anotó, por si fue un error: el diario es sincero."""
    if timezone.localtime(gasto.anotado).date() != timezone.localdate():
        raise ReglaNegocioError('Solo puedes borrar un gasto el mismo día que lo anotaste.')
    gasto.delete()


def marcar_sin_gasto(proyecto, fecha):
    _validar_fecha(fecha)
    if proyecto.gastos.filter(fecha=fecha).exists():
        raise ReglaNegocioError('Ese día ya tiene gastos anotados.')
    DiaSinGasto.objects.get_or_create(proyecto=proyecto, fecha=fecha)


def estado(proyecto):
    """Todo el diario: la lista de gastos con lo que cae en el mes, el registro de este mes y el resumen."""
    hoy = timezone.localdate()
    inicio, fin = _mes_actual()
    lista, guardados = rubros_de(proyecto)
    rubros = [rubro(r) for r in lista]
    gastos = list(proyecto.gastos.filter(fecha__range=(inicio, fin)))
    registro = [{'id': g.id, 'fecha': g.fecha, 'valor': g.valor, 'descripcion': g.descripcion,
                 'categoria': g.categoria, 'clase': g.clase,
                 'se_puede_borrar': timezone.localtime(g.anotado).date() == hoy} for g in gastos]
    al_dia, transcurridos = dias_al_dia(proyecto, hoy)

    def suma(items, campo):
        return sum(i[campo] for i in items)

    por_frecuencia = {f: suma([r for r in rubros if r['frecuencia'] == f], 'mensual') for f in FRECUENCIAS}
    plan = {'total': suma(rubros, 'mensual'), 'cerebral': suma(rubros, 'mensual_cerebral')}
    plan['emocional'] = plan['total'] - plan['cerebral']
    anotado = {'total': suma(registro, 'valor'),
               'cerebral': suma([g for g in registro if g['clase'] == 'cerebral'], 'valor')}
    anotado['emocional'] = anotado['total'] - anotado['cerebral']
    por_categoria = []
    for c, nombre, _ in CATEGORIAS:
        del_mes = [r for r in rubros if r['categoria'] == c]
        reg = [g for g in registro if g['categoria'] == c]
        if del_mes or reg:
            por_categoria.append({'categoria': c, 'nombre': nombre, 'plan': suma(del_mes, 'mensual'),
                                  'anotado': suma(reg, 'valor')})
    return {
        'mes': f'{MESES[hoy.month - 1]} {hoy.year}',
        'categorias': [{'id': c, 'nombre': n} for c, n, _ in CATEGORIAS],
        'rubros': rubros, 'guardados': guardados, 'registro': registro,
        'hoy_al_dia': dia_al_dia(proyecto, hoy),
        'resumen': {
            # Lo que se va a gastar este mes: lo de cada mes + la parte del mes de lo anual + la hormiga.
            'plan': plan, 'por_frecuencia': por_frecuencia, 'anotado': anotado,
            'por_categoria': por_categoria, 'dias_al_dia': al_dia, 'dias_transcurridos': transcurridos,
        },
        'ajustes': {'avisar': proyecto.datos.get('avisar', True),
                    'hora_aviso': proyecto.datos.get('hora_aviso', HORA_AVISO.isoformat('minutes'))},
    }


# ── El estándar del tipo ───────────────────────────────────────────────────────
def _valida(datos):
    if not isinstance(datos, dict):
        raise ReglaNegocioError('Ajustes no válidos.')
    hora = a_hora(datos.get('hora_aviso') or HORA_AVISO.isoformat('minutes'))
    if hora is None:
        raise ReglaNegocioError('La hora del aviso va así: 20:00.')
    return {'avisar': bool(datos.get('avisar', True)), 'hora_aviso': hora.isoformat('minutes')}


def _avance(proyecto):
    al_dia, transcurridos = dias_al_dia(proyecto)
    return round(al_dia / transcurridos * 100) if transcurridos else 0


def _resumen(proyecto):
    hoy = timezone.localdate()
    al_dia, transcurridos = dias_al_dia(proyecto, hoy)
    gastos = list(proyecto.gastos.filter(fecha__range=_mes_actual()).values('valor', 'clase'))
    dias = f'{al_dia} de {transcurridos} {"día" if transcurridos == 1 else "días"} al día'
    mes = MESES[hoy.month - 1].capitalize()
    if not gastos:
        return f'{mes}: {dias}'
    total = sum(g['valor'] for g in gastos)
    emocional = sum(g['valor'] for g in gastos if g['clase'] == 'emocional')
    return f'{mes}: {pesos(total)} anotados · {round(emocional / total * 100)} % emocional · {dias}'


def _avisos(proyecto, fecha):
    if not proyecto.datos.get('avisar', True) or fecha < proyecto.creado or dia_al_dia(proyecto, fecha):
        return []
    return [{
        'clave': 'dia', 'hora': a_hora(proyecto.datos.get('hora_aviso')) or HORA_AVISO,
        'titulo': '¿En qué gastaste hoy?',
        'cuerpo': 'Anótalo en tu diario de gastos, sin engañarte. Si no gastaste nada, dilo.',
        'accion': 'Hoy no gasté',
    }]


TIPO = Tipo(nombre='Diario de gastos', valida=_valida, avance=_avance, resumen=_resumen, avisos=_avisos,
            confirmar=lambda proyecto, clave, fecha: marcar_sin_gasto(proyecto, fecha),
            resuelto=lambda proyecto, clave, fecha: fecha < timezone.localdate() or dia_al_dia(proyecto, fecha),
            acciones={'sin_gasto': marcar_sin_gasto})
