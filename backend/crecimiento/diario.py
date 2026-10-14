"""Diario de gastos («Sana tus finanzas», capítulo 2, paso 1), mes a mes.

Tiene cuatro partes, como el ejercicio:
- **La relación del mes** (`RubroMes`): los gastos que se tienen cada mes, por categoría, con cuánto vale cada
  uno y cuánto es cerebral (lo demás es emocional; un gasto mixto se parte así).
- **Los gastos no mensuales** (`GastoNoMensual`): anuales o semestrales; se suman en el año, se dividen entre 12
  para saber cuánto aprovisionar al mes y entre los meses que faltan para el pago para saber cuánto ahorrar.
- **Los gastos hormiga** (`GastoHormiga`): lo de todos los días, por 30 días al mes y por 12 meses.
- **El registro** (`Gasto`, `DiaSinGasto`): lo que se gastó de verdad cada día, sin engañarse; un día está «al
  día» si tiene gastos anotados o si la persona dijo que no gastó.
"""
import calendar
import math
from datetime import date, time, timedelta

from django.db import transaction
from django.utils import timezone

from agenda.horarios import a_hora
from core.exceptions import ReglaNegocioError

from .models import DiaSinGasto, Gasto, GastoHormiga, GastoNoMensual, RubroMes
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
# Hasta cuántos días atrás se puede anotar un gasto que se olvidó.
DIAS_ATRAS = 7
HORA_AVISO = time(20, 0)


def pesos(valor):
    return '$' + f'{round(valor):,}'.replace(',', '.')


def mes_de(fecha):
    return fecha.replace(day=1)


def fin_de_mes(mes):
    return mes.replace(day=calendar.monthrange(mes.year, mes.month)[1])


def leer_mes(texto):
    """'2026-10' → date(2026, 10, 1); vacío → el mes de hoy."""
    if not texto:
        return mes_de(timezone.localdate())
    try:
        anio, mes = (int(x) for x in str(texto).split('-')[:2])
        return date(anio, mes, 1)
    except (TypeError, ValueError):
        raise ReglaNegocioError('El mes va así: 2026-10.')


# ── La relación del mes ────────────────────────────────────────────────────────
def rubros_del_mes(proyecto, mes):
    """(rubros, de_donde): los guardados de ese mes; si no hay, los del último mes que tenga (para no empezar de
    cero) o la lista del libro en blanco. `de_donde` es 'guardado', el mes copiado ('2026-09') o 'plantilla'."""
    guardados = list(proyecto.rubros.filter(mes=mes))
    if guardados:
        return [_rubro(r.categoria, r.nombre, r.valor, r.cerebral) for r in guardados], 'guardado'
    anterior = proyecto.rubros.filter(mes__lt=mes).order_by('-mes').values_list('mes', flat=True).first()
    if anterior:
        return ([_rubro(r.categoria, r.nombre, r.valor, r.cerebral) for r in proyecto.rubros.filter(mes=anterior)],
                anterior.strftime('%Y-%m'))
    return [_rubro(c, nombre, 0, 0) for c, _, rubros in CATEGORIAS for nombre in rubros], 'plantilla'


def _rubro(categoria, nombre, valor, cerebral):
    return {'categoria': categoria, 'nombre': nombre, 'valor': valor, 'cerebral': cerebral,
            'emocional': valor - cerebral}


@transaction.atomic
def guardar_rubros(proyecto, mes, rubros):
    """Reemplaza la relación de ese mes con la que manda la persona."""
    limpios = []
    for i, r in enumerate(rubros):
        if not isinstance(r, dict):
            raise ReglaNegocioError('Cada gasto del mes va con su categoría, su nombre y su valor.')
        categoria, nombre = r.get('categoria'), str(r.get('nombre') or '').strip()
        if categoria not in NOMBRE_CATEGORIA or not nombre or len(nombre) > 80:
            raise ReglaNegocioError('Cada gasto del mes va con su categoría y su nombre.')
        valor, cerebral = _entero(r.get('valor')), _entero(r.get('cerebral'))
        if cerebral > valor:
            raise ReglaNegocioError(f'En «{nombre}», lo cerebral no puede pasar del valor.')
        limpios.append(RubroMes(proyecto=proyecto, mes=mes, categoria=categoria, nombre=nombre, valor=valor,
                                cerebral=cerebral, orden=i))
    proyecto.rubros.filter(mes=mes).delete()
    RubroMes.objects.bulk_create(limpios)


def _entero(valor):
    try:
        n = int(valor or 0)
    except (TypeError, ValueError):
        raise ReglaNegocioError('Los valores van en pesos, sin puntos ni comas.')
    if n < 0 or n > 10**12:
        raise ReglaNegocioError('Ese valor no es válido.')
    return n


# ── No mensuales y hormiga ─────────────────────────────────────────────────────
def meses_que_faltan(gasto, mes):
    """Cuántos meses faltan para el próximo pago, contando este: si se paga en marzo y estamos en octubre, son 5
    (oct, nov, dic, ene y feb). Si toca este mes, 0."""
    pagos = [gasto.mes_pago] if gasto.periodicidad == 'anual' else [gasto.mes_pago, (gasto.mes_pago + 5) % 12 + 1]
    return min((p - mes.month) % 12 for p in pagos)


def no_mensual(gasto, mes):
    veces = 2 if gasto.periodicidad == 'semestral' else 1
    total = gasto.valor * veces
    faltan = meses_que_faltan(gasto, mes)
    return {
        'id': gasto.id, 'nombre': gasto.nombre, 'valor': gasto.valor, 'periodicidad': gasto.periodicidad,
        'mes_pago': gasto.mes_pago, 'clase': gasto.clase,
        'total_anual': total,
        # Lo que hay que apartar cada mes para tenerlo cuando llegue (el total del año entre 12).
        'mensual': math.ceil(total / 12),
        'meses_faltan': faltan,
        # Si se empieza ahora: el próximo pago entre los meses que faltan para él.
        'ahorro_hasta_pago': math.ceil(gasto.valor / faltan) if faltan else gasto.valor,
    }


def hormiga(gasto):
    mensual = gasto.valor_dia * gasto.dias_mes
    return {'id': gasto.id, 'nombre': gasto.nombre, 'valor_dia': gasto.valor_dia, 'dias_mes': gasto.dias_mes,
            'clase': gasto.clase, 'mensual': mensual, 'anual': mensual * 12}


# ── El registro ────────────────────────────────────────────────────────────────
def _inicio(proyecto, mes):
    return max(mes, proyecto.creado)


def dias_al_dia(proyecto, mes, hoy=None):
    """(al_dia, transcurridos) del mes hasta hoy, desde que empezó el diario."""
    hoy = hoy or timezone.localdate()
    inicio, fin = _inicio(proyecto, mes), min(fin_de_mes(mes), hoy)
    if fin < inicio:
        return 0, 0
    con_gasto = set(proyecto.gastos.filter(fecha__range=(inicio, fin)).values_list('fecha', flat=True))
    sin_gasto = set(proyecto.dias_sin_gasto.filter(fecha__range=(inicio, fin)).values_list('fecha', flat=True))
    return len(con_gasto | sin_gasto), (fin - inicio).days + 1


def dia_al_dia(proyecto, fecha):
    return (proyecto.gastos.filter(fecha=fecha).exists()
            or proyecto.dias_sin_gasto.filter(fecha=fecha).exists())


def _validar_fecha(fecha):
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


def _por_clase(items, valor='valor'):
    total = sum(i[valor] for i in items)
    cerebral = sum(i[valor] for i in items if i['clase'] == 'cerebral')
    return {'total': total, 'cerebral': cerebral, 'emocional': total - cerebral}


def estado_del_mes(proyecto, mes):
    """Todo lo del diario para ese mes: la relación, los no mensuales, la hormiga, el registro y el resumen."""
    hoy = timezone.localdate()
    rubros, de_donde = rubros_del_mes(proyecto, mes)
    no_mensuales = [no_mensual(g, mes) for g in proyecto.no_mensuales.all()]
    hormigas = [hormiga(g) for g in proyecto.hormiga.all()]
    gastos = list(proyecto.gastos.filter(fecha__range=(mes, fin_de_mes(mes))))
    registro = [{'id': g.id, 'fecha': g.fecha, 'valor': g.valor, 'descripcion': g.descripcion,
                 'categoria': g.categoria, 'clase': g.clase,
                 'se_puede_borrar': timezone.localtime(g.anotado).date() == hoy} for g in gastos]
    al_dia, transcurridos = dias_al_dia(proyecto, mes, hoy)

    relacion = {'total': sum(r['valor'] for r in rubros), 'cerebral': sum(r['cerebral'] for r in rubros)}
    relacion['emocional'] = relacion['total'] - relacion['cerebral']
    provision = {'mensual': sum(n['mensual'] for n in no_mensuales),
                 'cerebral': sum(n['mensual'] for n in no_mensuales if n['clase'] == 'cerebral')}
    provision['emocional'] = provision['mensual'] - provision['cerebral']
    hormiga_mes = _por_clase(hormigas, 'mensual')
    anotado = _por_clase(registro)
    por_categoria = {}
    for g in registro:
        c = por_categoria.setdefault(g['categoria'], {'categoria': g['categoria'],
                                                      'nombre': NOMBRE_CATEGORIA[g['categoria']],
                                                      'total': 0, 'cerebral': 0, 'emocional': 0})
        c['total'] += g['valor']
        c[g['clase']] += g['valor']
    estimado = relacion['total'] + provision['mensual'] + hormiga_mes['total']
    return {
        'mes': mes.strftime('%Y-%m'),
        'categorias': [{'id': c, 'nombre': n, 'rubros': r} for c, n, r in CATEGORIAS],
        'rubros': rubros, 'rubros_de': de_donde,
        'no_mensuales': no_mensuales, 'hormiga': hormigas, 'registro': registro,
        'sin_gasto': [d.isoformat() for d in proyecto.dias_sin_gasto
                      .filter(fecha__range=(mes, fin_de_mes(mes))).values_list('fecha', flat=True)],
        'hoy_al_dia': dia_al_dia(proyecto, hoy),
        'resumen': {
            'relacion': relacion, 'provision': provision, 'hormiga': hormiga_mes,
            # Lo que se espera gastar el mes: lo de cada mes + lo que hay que apartar + la hormiga.
            'estimado': {'total': estimado,
                         'cerebral': relacion['cerebral'] + provision['cerebral'] + hormiga_mes['cerebral'],
                         'emocional': relacion['emocional'] + provision['emocional'] + hormiga_mes['emocional']},
            'anotado': {**anotado, 'por_categoria': sorted(por_categoria.values(), key=lambda c: -c['total'])},
            'dias_al_dia': al_dia, 'dias_transcurridos': transcurridos,
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
    al_dia, transcurridos = dias_al_dia(proyecto, mes_de(timezone.localdate()))
    return round(al_dia / transcurridos * 100) if transcurridos else 0


MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre',
         'noviembre', 'diciembre']


def _resumen(proyecto):
    mes = mes_de(timezone.localdate())
    al_dia, transcurridos = dias_al_dia(proyecto, mes)
    gastos = list(proyecto.gastos.filter(fecha__range=(mes, fin_de_mes(mes))).values('valor', 'clase'))
    dias = f'{al_dia} de {transcurridos} {"día" if transcurridos == 1 else "días"} al día'
    if not gastos:
        return f'{MESES[mes.month - 1].capitalize()}: {dias}'
    total = sum(g['valor'] for g in gastos)
    emocional = sum(g['valor'] for g in gastos if g['clase'] == 'emocional')
    return (f'{MESES[mes.month - 1].capitalize()}: {pesos(total)} anotados · '
            f'{round(emocional / total * 100)} % emocional · {dias}')


def _avisos(proyecto, fecha):
    if not proyecto.datos.get('avisar', True) or fecha < proyecto.creado or dia_al_dia(proyecto, fecha):
        return []
    return [{
        'clave': 'dia', 'hora': a_hora(proyecto.datos.get('hora_aviso')) or HORA_AVISO,
        'titulo': '¿En qué gastaste hoy?',
        'cuerpo': 'Anótalo en tu diario de gastos, sin engañarte. Si no gastaste nada, dilo.',
        'accion': 'Hoy no gasté',
    }]


def _confirmar(proyecto, clave, fecha):
    marcar_sin_gasto(proyecto, fecha)


def _resuelto(proyecto, clave, fecha):
    return fecha < timezone.localdate() or dia_al_dia(proyecto, fecha)


TIPO = Tipo(nombre='Diario de gastos', valida=_valida, avance=_avance, resumen=_resumen, avisos=_avisos,
            confirmar=_confirmar, resuelto=_resuelto)
