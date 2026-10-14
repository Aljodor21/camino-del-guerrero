"""Taller de creencias («Sana tus finanzas», capítulo 1), en cuatro pasos:

1. **Cuestionario**: sí o no a cada creencia sobre el dinero, por grupos.
2. **Reflexiona**: por cada «sí», a dónde lo ha llevado esa creencia y qué le impide lograr.
3. **Transforma**: por cada «sí», una creencia nueva con sus palabras.
4. **Resultado**: sus creencias nuevas como post-its, para leerlas 21 días seguidos.

Las preguntas viven en la pantalla (`taller-creencias.ts`); aquí solo sus llaves, para validar. Todo va en
`Proyecto.datos`: `ans` {llave: 'si'|'no'}, `ref` {llave: {a, b}}, `pos` {llave: texto} y `dias` (las fechas en
que las leyó, que solo agrega el servidor: con el botón o con el aviso).
"""
from datetime import date, time, timedelta

from django.utils import timezone

from agenda.horarios import a_hora
from core.exceptions import ReglaNegocioError

from .tipos_base import Tipo

# Los grupos del cuestionario y cuántas preguntas tiene cada uno (a: merecimiento, b: esfuerzo, c: ahorro,
# d: inversión).
GRUPOS = {'a': 5, 'b': 3, 'c': 4, 'd': 4}
LLAVES = [f'{g}{i}' for g, n in GRUPOS.items() for i in range(n)]
DIAS_META = 21
HORA_AVISO = time(8, 0)
MAX_TEXTO = 1500


def _texto(valor, maximo=MAX_TEXTO):
    if valor is None:
        return ''
    if not isinstance(valor, str):
        raise ReglaNegocioError('Las respuestas van en texto.')
    return valor.strip()[:maximo]


def _valida(datos):
    if not isinstance(datos, dict):
        raise ReglaNegocioError('Respuestas no válidas.')
    ans = {k: v for k, v in (datos.get('ans') or {}).items() if k in LLAVES and v in ('si', 'no')}
    ref = {}
    for k, v in (datos.get('ref') or {}).items():
        if k in LLAVES and isinstance(v, dict):
            ref[k] = {'a': _texto(v.get('a')), 'b': _texto(v.get('b'))}
    pos = {k: _texto(v, 300) for k, v in (datos.get('pos') or {}).items() if k in LLAVES}
    hora = a_hora(datos.get('hora_aviso') or HORA_AVISO.isoformat('minutes'))
    if hora is None:
        raise ReglaNegocioError('La hora del aviso va así: 08:00.')
    return {'ans': ans, 'ref': ref, 'pos': {k: v for k, v in pos.items() if v},
            'dias': [], 'avisar': bool(datos.get('avisar', True)), 'hora_aviso': hora.isoformat('minutes')}


def _si(datos):
    return [k for k in LLAVES if datos.get('ans', {}).get(k) == 'si']


def _nuevas(datos):
    return [k for k in _si(datos) if datos.get('pos', {}).get(k)]


def _dias(datos):
    return sorted({date.fromisoformat(d) for d in datos.get('dias', [])})


def rachas(datos, hoy=None):
    """(actual, mejor): días seguidos leyéndolas; la actual cuenta hasta hoy o ayer."""
    hoy = hoy or timezone.localdate()
    dias = _dias(datos)
    mejor = actual = 0
    previo = None
    for d in dias:
        actual = actual + 1 if previo and d - previo == timedelta(days=1) else 1
        mejor = max(mejor, actual)
        previo = d
    if not dias or hoy - dias[-1] > timedelta(days=1):
        actual = 0
    return actual, mejor


def _avance(proyecto):
    datos = proyecto.datos
    respondidas = len(datos.get('ans', {}))
    si = _si(datos)
    if respondidas == len(LLAVES) and not si:
        return 100
    paso1 = respondidas / len(LLAVES)
    paso2 = sum(1 for k in si if all((datos.get('ref', {}).get(k) or {}).get(x) for x in 'ab')) / len(si) if si else 0
    paso3 = len(_nuevas(datos)) / len(si) if si else 0
    _, mejor = rachas(datos)
    paso4 = min(mejor, DIAS_META) / DIAS_META
    return round((paso1 + paso2 + paso3 + paso4) * 25)


def _resumen(proyecto):
    datos = proyecto.datos
    nuevas = _nuevas(datos)
    if not nuevas:
        return f'Cuestionario: {len(datos.get("ans", {}))} de {len(LLAVES)}'
    actual, mejor = rachas(datos)
    if mejor >= DIAS_META:
        return f'{len(nuevas)} creencias nuevas · 21 días cumplidos'
    return f'{len(nuevas)} creencias nuevas · {actual} de {DIAS_META} días seguidos'


def marcar_leido(proyecto, fecha):
    """Hoy las leyó. Solo se marca el día de hoy: lo cumplido no se escribe hacia atrás."""
    if fecha != timezone.localdate():
        raise ReglaNegocioError('Solo se marca el día de hoy.')
    if not _nuevas(proyecto.datos):
        raise ReglaNegocioError('Primero escribe tus creencias nuevas.')
    dias = set(proyecto.datos.get('dias', []))
    dias.add(fecha.isoformat())
    proyecto.datos = {**proyecto.datos, 'dias': sorted(dias)}
    proyecto.save(update_fields=['datos'])


def _avisos(proyecto, fecha):
    datos = proyecto.datos
    if not datos.get('avisar', True) or not _nuevas(datos) or fecha.isoformat() in datos.get('dias', []):
        return []
    actual, mejor = rachas(datos, fecha)
    if mejor >= DIAS_META:
        return []
    return [{
        'clave': 'leer', 'hora': a_hora(datos.get('hora_aviso')) or HORA_AVISO,
        'titulo': 'Lee tus creencias nuevas',
        'cuerpo': f'Día {actual + 1} de {DIAS_META}: léelas con calma, donde las tengas pegadas.',
        'accion': 'Ya las leí',
    }]


def _resuelto(proyecto, clave, fecha):
    return fecha < timezone.localdate() or not _avisos(proyecto, fecha)


TIPO = Tipo(nombre='Taller de creencias', valida=_valida, avance=_avance, resumen=_resumen, avisos=_avisos,
            confirmar=lambda proyecto, clave, fecha: marcar_leido(proyecto, fecha), resuelto=_resuelto,
            del_servidor=('dias',), acciones={'leer': marcar_leido})
