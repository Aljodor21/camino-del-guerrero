"""Las tarjetas de crédito del diario de gastos.

Una compra con tarjeta es un gasto más del registro (`Gasto.tarjeta`, `Gasto.cuotas`): cuenta en el día y en el
mes como cualquier otro. Aquí se calcula lo propio de la tarjeta, sin guardar nada: el **periodo** (del día después
del corte anterior hasta el corte; sin día de corte, el mes), lo que entra en la factura de ese corte (las compras
a cuotas se reparten en los cortes siguientes, sin intereses: cada banco cobra distinto), lo que falta por pagar y
lo que queda del cupo. Lo de una factura se da por pagado cuando pasa su día de pago (no se anotan los pagos: las
compras ya están en el registro).
"""
import calendar
from datetime import date, time, timedelta

from django.utils import timezone

from core.exceptions import ReglaNegocioError

from .models import Tarjeta

MAX_TARJETAS = 10
MAX_CUOTAS = 48
HORA_AVISO_PAGO = time(9, 0)
DIAS_ANTES_DEL_PAGO = 2


def _dia(anio, mes, dia):
    """El día del mes, o el último si ese mes es más corto (corte el 31 en febrero → 28 o 29)."""
    return date(anio, mes, min(dia, calendar.monthrange(anio, mes)[1]))


def _mes(ordinal):
    anio, mes = divmod(ordinal, 12)
    return anio, mes + 1


def corte(tarjeta, ordinal):
    """La fecha del corte número `ordinal` (un corte por mes: año × 12 + mes − 1)."""
    return _dia(*_mes(ordinal), tarjeta.dia_corte or 31)


def ordinal(tarjeta, fecha):
    """En qué corte cae una compra de esa fecha."""
    o = fecha.year * 12 + fecha.month - 1
    return o + 1 if fecha > corte(tarjeta, o) else o


def periodo(tarjeta, o):
    return corte(tarjeta, o - 1) + timedelta(days=1), corte(tarjeta, o)


def pago(tarjeta, o):
    """El día en que se paga la factura de ese corte: el primer día de pago después del corte."""
    if not tarjeta.dia_pago:
        return None
    c = corte(tarjeta, o)
    dia = _dia(c.year, c.month, tarjeta.dia_pago)
    return dia if dia > c else _dia(*_mes(o + 1), tarjeta.dia_pago)


def cuotas_de(valor, cuotas):
    """Lo de cada cuota, sin intereses; lo que no se reparte parejo va en la primera."""
    base = valor // cuotas
    return [base + valor - base * cuotas] + [base] * (cuotas - 1)


def _por_corte(tarjeta, compras):
    """{ordinal: lo que entra en esa factura} con las cuotas repartidas."""
    facturas = {}
    for g in compras:
        o = ordinal(tarjeta, g.fecha)
        for i, v in enumerate(cuotas_de(g.valor, g.cuotas)):
            facturas[o + i] = facturas.get(o + i, 0) + v
    return facturas


def resumen_de(tarjeta, hoy=None):
    hoy = hoy or timezone.localdate()
    compras = list(tarjeta.compras.all())
    facturas = _por_corte(tarjeta, compras)
    o = ordinal(tarjeta, hoy)
    desde, hasta = periodo(tarjeta, o)
    del_periodo = [g for g in compras if desde <= g.fecha <= hasta]
    # La factura del corte anterior sigue pendiente hasta su día de pago.
    pago_anterior = pago(tarjeta, o - 1)
    factura = None
    if facturas.get(o - 1) and pago_anterior and pago_anterior >= hoy:
        factura = {'valor': facturas[o - 1], 'corte': corte(tarjeta, o - 1), 'pago': pago_anterior}
    deuda = sum(v for k, v in facturas.items() if k >= o) + (factura['valor'] if factura else 0)
    return {
        'id': tarjeta.id, 'nombre': tarjeta.nombre, 'ultimos': tarjeta.ultimos, 'cupo': tarjeta.cupo,
        'dia_corte': tarjeta.dia_corte, 'dia_pago': tarjeta.dia_pago, 'avisar': tarjeta.avisar,
        'periodo': {'desde': desde, 'hasta': hasta, 'pago': pago(tarjeta, o)},
        'compras': [{'id': g.id, 'fecha': g.fecha, 'valor': g.valor, 'descripcion': g.descripcion,
                     'clase': g.clase, 'cuotas': g.cuotas} for g in del_periodo],
        'comprado': sum(g.valor for g in del_periodo),
        'emocional': sum(g.valor for g in del_periodo if g.clase == 'emocional'),
        # Lo que va en la factura de este corte: las compras de contado y las cuotas que caen aquí.
        'este_corte': facturas.get(o, 0),
        'factura': factura,
        'deuda': deuda,
        'disponible': max(0, tarjeta.cupo - deuda) if tarjeta.cupo else None,
    }


def estado(proyecto, hoy=None):
    return [resumen_de(t, hoy) for t in proyecto.tarjetas.filter(activa=True).prefetch_related('compras')]


# ── Agregar, cambiar y quitar ─────────────────────────────────────────────────
def _limpio(datos):
    nombre = str(datos.get('nombre') or '').strip()
    if not nombre:
        raise ReglaNegocioError('Ponle un nombre a la tarjeta.')
    ultimos = str(datos.get('ultimos') or '').strip()
    if ultimos and not (len(ultimos) == 4 and ultimos.isdigit()):
        raise ReglaNegocioError('De la tarjeta solo van los 4 últimos números (o nada).')

    def numero(llave, minimo, maximo, texto):
        valor = datos.get(llave)
        if valor in (None, ''):
            return None
        try:
            valor = int(valor)
        except (TypeError, ValueError):
            raise ReglaNegocioError(texto)
        if not minimo <= valor <= maximo:
            raise ReglaNegocioError(texto)
        return valor

    return {
        'nombre': nombre[:40], 'ultimos': ultimos,
        'cupo': numero('cupo', 1, 10**12, 'El cupo va en pesos, sin puntos.'),
        'dia_corte': numero('dia_corte', 1, 31, 'El día de corte va del 1 al 31.'),
        'dia_pago': numero('dia_pago', 1, 31, 'El día de pago va del 1 al 31.'),
        'avisar': bool(datos.get('avisar', True)),
    }


def agregar(proyecto, datos):
    if proyecto.tarjetas.filter(activa=True).count() >= MAX_TARJETAS:
        raise ReglaNegocioError(f'Puedes llevar hasta {MAX_TARJETAS} tarjetas.')
    return Tarjeta.objects.create(proyecto=proyecto, **_limpio(datos))


def cambiar(tarjeta, datos):
    for llave, valor in _limpio(datos).items():
        setattr(tarjeta, llave, valor)
    tarjeta.save()


def quitar(tarjeta):
    """Sin compras se borra; con compras se retira (deja de salir) y sus compras siguen en el registro."""
    if tarjeta.compras.exists():
        tarjeta.activa = False
        tarjeta.save(update_fields=['activa'])
    else:
        tarjeta.delete()


def para_la_compra(proyecto, tarjeta_id, cuotas):
    """La tarjeta y las cuotas de un gasto nuevo (sin tarjeta, de contado)."""
    if not tarjeta_id:
        if cuotas not in (None, 1):
            raise ReglaNegocioError('Las cuotas son solo para compras con tarjeta.')
        return None, 1
    tarjeta = proyecto.tarjetas.filter(pk=tarjeta_id, activa=True).first()
    if tarjeta is None:
        raise ReglaNegocioError('Esa tarjeta no está en tu diario.')
    cuotas = cuotas or 1
    if not 1 <= cuotas <= MAX_CUOTAS:
        raise ReglaNegocioError(f'Las cuotas van de 1 a {MAX_CUOTAS}.')
    return tarjeta, cuotas


# ── Avisos del pago ───────────────────────────────────────────────────────────
def avisos(proyecto, fecha):
    """Dos días antes del pago y ese día, si la factura tiene algo."""
    from .diario import pesos
    lista = []
    for t in proyecto.tarjetas.filter(activa=True, avisar=True).exclude(dia_pago=None).prefetch_related('compras'):
        facturas = _por_corte(t, t.compras.all())
        o_hoy = ordinal(t, fecha)
        for o in (o_hoy - 2, o_hoy - 1, o_hoy):
            dia = pago(t, o)
            faltan = (dia - fecha).days if dia else -1
            if facturas.get(o) and faltan in (0, DIAS_ANTES_DEL_PAGO):
                lista.append({
                    'clave': f'pago:{t.id}', 'hora': HORA_AVISO_PAGO,
                    'titulo': (f'Hoy pagas tu {t}' if faltan == 0 else f'En {faltan} días pagas tu {t}'),
                    'cuerpo': f'La factura del corte del {corte(t, o).day} es de {pesos(facturas[o])}.',
                    'accion': '',
                })
    return lista
