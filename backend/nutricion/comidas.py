"""Registro de lo que se comió y cumplimiento de la minuta.

Cada comida se registra con lo que el usuario cuenta (cuánto de cada grupo comió, una
foto y una nota opcionales). Se compara con lo que la minuta pedía en esa comida, ya
descontado lo que cubre la proteína. La foto es de apoyo: el cumplimiento sale de lo que
el usuario marca, no de interpretar la imagen.
"""
from datetime import time, timedelta
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.utils import timezone

from core.exceptions import ReglaNegocioError
from progress.fotos import LADO_MINIATURA, LADO_ORIGINAL, a_jpeg, leer_imagen

from . import minutas
from .grupos import HORA_TIEMPO, NOMBRE_GRUPO, NOMBRE_TIEMPO, ORDEN_TIEMPO
from .menus import Contexto
from .models import RegistroComida

# Hasta cuántos días atrás se puede contar lo que se comió.
DIAS_ATRAS = 7
# Avances permitidos por grupo: de cuánto de lo pedido comió.
AVANCES = {Decimal(x) for x in ('0', '0.25', '0.5', '0.75', '1')}


def _minuta(usuario):
    minuta = minutas.vigente_de(usuario)
    if minuta is None:
        raise ReglaNegocioError('Primero arma tu plan de comida.')
    return minuta


def pedido(usuario, fecha, tiempo, contexto=None):
    """{grupo: porciones} que la minuta pedía en esa comida ese día."""
    minuta = _minuta(usuario)
    if tiempo not in minuta.tiempos():
        raise ReglaNegocioError('Tu plan no tiene esa comida.')
    contexto = contexto or Contexto(usuario, minuta)
    return contexto.requerido(fecha, tiempo)


def _validar_fecha(fecha):
    hoy = timezone.localdate()
    if fecha > hoy:
        raise ReglaNegocioError('Aún no llega ese día.')
    if fecha < hoy - timedelta(days=DIAS_ATRAS):
        raise ReglaNegocioError(f'Solo puedes contar lo de los últimos {DIAS_ATRAS} días.')


# Cómo se nombran los grupos en una frase (los de la minuta son largos).
NOMBRE_EN_FRASE = {'cereales': 'cereales y tubérculos', 'grasas': 'aceites y aguacate'}


def _grupo_en_frase(grupo):
    return NOMBRE_EN_FRASE.get(grupo) or NOMBRE_GRUPO[grupo].lower()


@transaction.atomic
def registrar(usuario, fecha, tiempo, avances, nota='', archivo=None):
    """`avances`: {grupo: de 0 a 1} de cuánto de lo pedido comió en cada grupo.
    Lo que no se menciona cuenta como que no lo comió."""
    _validar_fecha(fecha)
    pedidos = pedido(usuario, fecha, tiempo)
    if RegistroComida.objects.filter(usuario=usuario, fecha=fecha, tiempo=tiempo).exists():
        raise ReglaNegocioError('Ya contaste esta comida.')
    sobran = set(avances) - set(pedidos)
    if sobran:
        raise ReglaNegocioError(f'Esa comida no lleva {NOMBRE_GRUPO.get(sobran.pop(), "ese grupo").lower()}.')

    grupos = {}
    for grupo, porciones in pedidos.items():
        try:
            avance = Decimal(str(avances.get(grupo, 0)))
        except ArithmeticError:
            raise ReglaNegocioError('Indica cuánto comiste de cada grupo.')
        if avance not in AVANCES:
            raise ReglaNegocioError('Indica cuánto comiste de cada grupo.')
        grupos[grupo] = {'pedido': float(porciones), 'comido': float((porciones * avance).quantize(Decimal('0.1')))}

    campos = {}
    if archivo is not None:
        imagen = leer_imagen(archivo)
        campos = {'foto': a_jpeg(imagen, LADO_ORIGINAL, 85), 'miniatura': a_jpeg(imagen, LADO_MINIATURA, 80)}
    try:
        return RegistroComida.objects.create(
            usuario=usuario, fecha=fecha, tiempo=tiempo, grupos=grupos, nota=nota.strip(), **campos)
    except IntegrityError:
        raise ReglaNegocioError('Ya contaste esta comida.')


def _ya_paso(fecha, tiempo, ahora):
    if fecha < ahora.date():
        return True
    return fecha == ahora.date() and ahora.time() >= time(*HORA_TIEMPO[tiempo])


def _en_palabras(faltan):
    """[('lacteos', 1.5), ...] → '1,5 de lácteos y 1 de verduras'."""
    partes = [f'{float(p):g} de {_grupo_en_frase(g)}'.replace('.', ',') for g, p in faltan]
    return partes[0] if len(partes) == 1 else f"{', '.join(partes[:-1])} y {partes[-1]}"


def cumplimiento(usuario, desde, hasta):
    """Qué tanto de la minuta se cumplió entre dos fechas, según lo que se contó.

    El porcentaje es sobre las comidas contadas; las que ya pasaron y no se contaron se
    muestran aparte (`sin_contar`) para no suponer que no se comió."""
    minuta = _minuta(usuario)
    ahora = timezone.localtime()
    hasta = min(hasta, ahora.date())
    desde = max(desde, timezone.localtime(minuta.fecha_creacion).date())

    registros = list(RegistroComida.objects.filter(usuario=usuario, fecha__range=(desde, hasta))
                     .order_by('fecha', 'momento'))
    contados = {(r.fecha, r.tiempo) for r in registros}
    sin_contar = []
    dia = desde
    while dia <= hasta:
        for tiempo in minuta.tiempos():
            if (dia, tiempo) not in contados and _ya_paso(dia, tiempo, ahora):
                sin_contar.append({'fecha': dia, 'tiempo': tiempo, 'nombre': NOMBRE_TIEMPO[tiempo]})
        dia += timedelta(days=1)

    por_grupo, comidas = {}, []
    total_pedido = total_comido = Decimal(0)
    for r in registros:
        faltan = []
        pedido_r = comido_r = Decimal(0)
        for grupo, v in r.grupos.items():
            p, c = Decimal(str(v['pedido'])), Decimal(str(v['comido']))
            pedido_r, comido_r = pedido_r + p, comido_r + c
            acum = por_grupo.setdefault(grupo, [Decimal(0), Decimal(0)])
            acum[0], acum[1] = acum[0] + p, acum[1] + c
            if c < p:
                faltan.append((grupo, p - c))
        total_pedido, total_comido = total_pedido + pedido_r, total_comido + comido_r
        comidas.append({
            'id': r.id, 'fecha': r.fecha, 'tiempo': r.tiempo, 'nombre': NOMBRE_TIEMPO[r.tiempo],
            'porcentaje': round(float(comido_r / pedido_r) * 100) if pedido_r else 100,
            'faltaron': [{'grupo': g, 'nombre': NOMBRE_GRUPO[g], 'porciones': float(p)} for g, p in faltan],
            'nota': r.nota, 'tiene_foto': bool(r.foto),
        })

    porcentaje = round(float(total_comido / total_pedido) * 100) if total_pedido else None
    faltantes = [(g, p - c) for g, (p, c) in por_grupo.items() if c < p]
    faltantes.sort(key=lambda x: -x[1])
    return {
        'desde': desde, 'hasta': hasta,
        'porcentaje': porcentaje,
        'porciones_pedidas': float(total_pedido), 'porciones_comidas': float(total_comido),
        'comidas': sorted(comidas, key=lambda c: (c['fecha'], ORDEN_TIEMPO[c['tiempo']])),
        'sin_contar': sin_contar,
        'por_grupo': [{'grupo': g, 'nombre': NOMBRE_GRUPO[g], 'pedido': float(p), 'comido': float(c)}
                      for g, (p, c) in por_grupo.items()],
        'faltantes': [{'grupo': g, 'nombre': NOMBRE_GRUPO[g], 'porciones': float(p)} for g, p in faltantes],
        'mensaje': _mensaje(porcentaje, faltantes, len(sin_contar), len(comidas)),
    }


def _mensaje(porcentaje, faltantes, sin_contar, contadas):
    if porcentaje is None:
        return 'Aún no has contado ninguna comida. Cuéntalas cuando llegue el aviso para ver cómo vas.'
    if porcentaje >= 100:
        texto = 'Estás cumpliendo al 100 %: comiste todo lo que pidió tu plan.'
    else:
        texto = f'Estás cumpliendo al {porcentaje} %.'
        if faltantes:
            texto += f' Te faltó {_en_palabras(faltantes[:3])}.'
    if sin_contar:
        texto += (f' Tienes {sin_contar} {"comida" if sin_contar == 1 else "comidas"} sin contar, '
                  'que no se suman al porcentaje.')
    return texto
