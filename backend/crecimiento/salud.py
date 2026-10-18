"""Salud: el protocolo Fadiman de microdosis y el control de otros suplementos.

**Protocolo Fadiman** (`fadiman`): un ciclo de 4 días que se repite: día 1 la toma (por la mañana), día 2 de
transición (se observa el ánimo y la energía), día 3 normal y día 4 es otra vez día 1. Dura de 4 a 8 semanas y
sigue un descanso de 2 a 4 semanas para evaluar y evitar la tolerancia. La app solo lleva el calendario y lo que la
persona anota: no recomienda sustancias ni dosis (la sustancia y la cantidad las escribe ella), y lo que anota no se
edita. Una toma en un día que el protocolo no marcaba se guarda igual, marcada `fuera_de_protocolo`.

**Otros suplementos** (`otros_suplementos`): un registro simple de lo que toma además de lo del plan de nutrición
(que ya tiene sus propios avisos): qué, cuánto y cuándo, para tener a la vista todo lo que se toma.

Todo cuelga de `TomaSalud`. En `Proyecto.datos` del protocolo van solo los ajustes: `sustancia`, `dosis`, `inicio`
(el día 1 del primer ciclo), `semanas_ciclo`, `semanas_descanso`, `avisar` y `hora_aviso`.
"""
import math
from datetime import date, time, timedelta

from django.db import transaction
from django.utils import timezone

from agenda.horarios import a_hora
from core.exceptions import ReglaNegocioError

from .models import TomaSalud
from .tipos_base import Tipo

DIAS_CICLO = 4
SEMANAS_CICLO = (4, 8)
SEMANAS_DESCANSO = (2, 4)
HORA_AVISO = time(8, 0)
DIAS_ATRAS = 7
# De lo que dice el protocolo, para mostrarlo; no se usa para validar ni para aconsejar.
ETAPAS = {1: ('Día de la microdosis', 'Tomas la sustancia por la mañana.'),
          2: ('Día de transición', 'No consumes; observas cómo estás de ánimo y energía.'),
          3: ('Día normal', 'No consumes; tu cuerpo vuelve a su estado basal.')}
CUIDADOS = [
    'Puede provocar ansiedad, malestar estomacal u otros efectos adversos en un porcentaje de las personas.',
    'El uso prolongado de algunas de estas sustancias se ha asociado a riesgos cardiovasculares.',
    'Puede tener implicaciones legales: infórmate de la ley donde vives.',
    'Si tomas otros suplementos o medicamentos, o tienes una condición de salud, consúltalo con un profesional '
    'antes de empezar.',
]


def _texto(valor, maximo):
    if valor is None:
        return ''
    if not isinstance(valor, str):
        raise ReglaNegocioError('Eso va en texto.')
    return valor.strip()[:maximo]


def _entre(valor, rango, nombre):
    try:
        valor = int(valor)
    except (TypeError, ValueError):
        raise ReglaNegocioError(f'{nombre}: escribe un número entero.')
    if not rango[0] <= valor <= rango[1]:
        raise ReglaNegocioError(f'{nombre}: de {rango[0]} a {rango[1]}.')
    return valor


def _fecha(valor):
    if not valor:
        return None
    try:
        return date.fromisoformat(str(valor))
    except ValueError:
        raise ReglaNegocioError('La fecha de inicio va así: 2026-10-17.')


# ── El calendario del protocolo ─────────────────────────────────────────────────
def _ajustes(datos):
    return {
        'sustancia': datos.get('sustancia', ''), 'dosis': datos.get('dosis', ''),
        'inicio': _fecha(datos.get('inicio')),
        'semanas_ciclo': datos.get('semanas_ciclo', 4), 'semanas_descanso': datos.get('semanas_descanso', 2),
    }


def dia_del_protocolo(datos, fecha):
    """Dónde cae ese día: `{fase: 'sin_empezar'|'ciclo'|'descanso', dia (1 a 4, solo en ciclo), vuelta, semana}`.

    Desde `inicio` corren `semanas_ciclo` semanas en ciclo de 4 días y luego `semanas_descanso` de descanso; así
    se repite (la `vuelta` cuenta cuántos ciclos van)."""
    a = _ajustes(datos)
    if a['inicio'] is None or fecha < a['inicio']:
        return {'fase': 'sin_empezar', 'dia': None, 'vuelta': 0, 'semana': 0}
    corridos = (fecha - a['inicio']).days
    en_ciclo = a['semanas_ciclo'] * 7
    vuelta, posicion = divmod(corridos, en_ciclo + a['semanas_descanso'] * 7)
    if posicion < en_ciclo:
        return {'fase': 'ciclo', 'dia': posicion % DIAS_CICLO + 1, 'vuelta': vuelta + 1,
                'semana': posicion // 7 + 1}
    return {'fase': 'descanso', 'dia': None, 'vuelta': vuelta + 1, 'semana': (posicion - en_ciclo) // 7 + 1}


def dias_de_toma_del_ciclo(datos):
    """Las fechas en que toca la toma durante el primer ciclo."""
    inicio = _fecha(datos.get('inicio'))
    if inicio is None:
        return []
    return [inicio + timedelta(days=d) for d in range(0, datos.get('semanas_ciclo', 4) * 7, DIAS_CICLO)]


def _de_ese_dia(proyecto, fecha, clase):
    return proyecto.tomas_salud.filter(fecha=fecha, clase=clase)


# ── Anotar ──────────────────────────────────────────────────────────────────────
def _validar_fecha(fecha):
    hoy = timezone.localdate()
    if fecha > hoy:
        raise ReglaNegocioError('Ese día todavía no llega.')
    if fecha < hoy - timedelta(days=DIAS_ATRAS):
        raise ReglaNegocioError(f'Solo se anota lo de los últimos {DIAS_ATRAS} días.')


def _nivel(valor, nombre):
    if valor in (None, ''):
        return None
    return _entre(valor, (1, 5), nombre)


@transaction.atomic
def anotar(proyecto, fecha, clase, nombre='', cantidad='', animo=None, energia=None, nota=''):
    """Anota una toma o una observación. En el protocolo, la sustancia y la cantidad vienen de los ajustes si no
    se dicen; la toma del protocolo es una por día."""
    _validar_fecha(fecha)
    if clase not in ('dosis', 'observacion'):
        raise ReglaNegocioError('Di si es una toma o una observación.')
    protocolo = proyecto.tipo == 'fadiman'
    if clase == 'observacion':
        if not protocolo:
            raise ReglaNegocioError('Las observaciones son del protocolo.')
        animo, energia = _nivel(animo, 'Ánimo'), _nivel(energia, 'Energía')
        if animo is None and energia is None and not _texto(nota, 300):
            raise ReglaNegocioError('Cuenta cómo estás: ánimo, energía o una nota.')
        if _de_ese_dia(proyecto, fecha, 'observacion').exists():
            raise ReglaNegocioError('Ese día ya anotaste cómo estabas.')
        nombre, cantidad = '', ''
        fuera = False
    else:
        animo = energia = None
        if protocolo:
            ajustes = proyecto.datos
            nombre = _texto(nombre, 60) or ajustes.get('sustancia', '')
            cantidad = _texto(cantidad, 40) or ajustes.get('dosis', '')
            if _de_ese_dia(proyecto, fecha, 'dosis').exists():
                raise ReglaNegocioError('Ese día ya anotaste tu toma.')
            fuera = not (_ajustes(ajustes)['inicio'] and dia_del_protocolo(ajustes, fecha)['dia'] == 1)
        else:
            fuera = False
        nombre, cantidad = _texto(nombre, 60), _texto(cantidad, 40)
        if not nombre:
            raise ReglaNegocioError('Escribe qué tomaste.')
        if not cantidad:
            raise ReglaNegocioError('Escribe cuánto tomaste.')
    return TomaSalud.objects.create(proyecto=proyecto, fecha=fecha, clase=clase, nombre=nombre, cantidad=cantidad,
                                    animo=animo, energia=energia, nota=_texto(nota, 300),
                                    fuera_de_protocolo=fuera)


def borrar(toma):
    """Solo el mismo día que se anotó, por si fue un error."""
    if timezone.localtime(toma.anotado).date() != timezone.localdate():
        raise ReglaNegocioError('Solo puedes borrar lo que anotaste hoy.')
    toma.delete()


# ── Lo que ve la persona ────────────────────────────────────────────────────────
def _toma(t, hoy):
    return {'id': t.id, 'fecha': t.fecha, 'clase': t.clase, 'nombre': t.nombre, 'cantidad': t.cantidad,
            'animo': t.animo, 'energia': t.energia, 'nota': t.nota, 'fuera_de_protocolo': t.fuera_de_protocolo,
            'se_puede_borrar': timezone.localtime(t.anotado).date() == hoy}


def estado(proyecto, dias=60):
    """Todo lo de la pantalla: el día de hoy en el protocolo, lo anotado y, para los suplementos, lo que ya toma."""
    hoy = timezone.localdate()
    tomas = list(proyecto.tomas_salud.filter(fecha__gte=hoy - timedelta(days=dias)))
    datos = {
        'tipo': proyecto.tipo, 'hoy': hoy, 'tomas': [_toma(t, hoy) for t in tomas],
        'cuidados': CUIDADOS,
        # Lo que ya anotó antes, para volver a anotarlo con un toque.
        'frecuentes': [{'nombre': n, 'cantidad': c} for n, c in
                       proyecto.tomas_salud.filter(clase='dosis').exclude(nombre='')
                       .order_by('nombre', 'cantidad').values_list('nombre', 'cantidad').distinct()[:20]],
    }
    if proyecto.tipo != 'fadiman':
        return datos
    ajustes = proyecto.datos
    dia = dia_del_protocolo(ajustes, hoy)
    previstas = dias_de_toma_del_ciclo(ajustes)
    hechas = {t.fecha for t in proyecto.tomas_salud.filter(clase='dosis')}
    siguiente = None
    if _ajustes(ajustes)['inicio']:
        siguiente = next((hoy + timedelta(days=d) for d in range(0, 400)
                          if dia_del_protocolo(ajustes, hoy + timedelta(days=d))['dia'] == 1), None)
    datos.update({
        'dia': dia, 'etapa': ETAPAS.get(dia['dia']), 'toma_hoy': hoy in hechas,
        'observacion_hoy': _de_ese_dia(proyecto, hoy, 'observacion').exists(),
        'siguiente_toma': siguiente,
        'primer_ciclo': {'previstas': len(previstas), 'hechas': sum(1 for d in previstas if d in hechas)},
        'ajustes': {**{k: v for k, v in ajustes.items()}, 'rango_ciclo': SEMANAS_CICLO,
                    'rango_descanso': SEMANAS_DESCANSO},
    })
    return datos


# ── El tipo «protocolo Fadiman» ─────────────────────────────────────────────────
def _valida_fadiman(datos):
    if not isinstance(datos, dict):
        raise ReglaNegocioError('Ajustes no válidos.')
    hora = a_hora(datos.get('hora_aviso') or HORA_AVISO.isoformat('minutes'))
    if hora is None:
        raise ReglaNegocioError('La hora del aviso va así: 08:00.')
    inicio = _fecha(datos.get('inicio'))
    hoy = timezone.localdate()
    if inicio and not hoy - timedelta(days=120) <= inicio <= hoy + timedelta(days=30):
        raise ReglaNegocioError('El inicio debe estar entre hace cuatro meses y el próximo mes.')
    return {
        'sustancia': _texto(datos.get('sustancia'), 60), 'dosis': _texto(datos.get('dosis'), 40),
        'inicio': inicio.isoformat() if inicio else '',
        'semanas_ciclo': _entre(datos.get('semanas_ciclo', 4), SEMANAS_CICLO, 'Semanas del ciclo'),
        'semanas_descanso': _entre(datos.get('semanas_descanso', 2), SEMANAS_DESCANSO, 'Semanas de descanso'),
        'avisar': bool(datos.get('avisar', True)), 'hora_aviso': hora.isoformat('minutes'),
    }


def _avance_fadiman(proyecto):
    previstas = [d for d in dias_de_toma_del_ciclo(proyecto.datos) if d <= timezone.localdate()]
    if not previstas:
        return 0
    total = len(dias_de_toma_del_ciclo(proyecto.datos))
    hechas = set(proyecto.tomas_salud.filter(clase='dosis', fecha__in=previstas).values_list('fecha', flat=True))
    return round(100 * len(hechas) / total)


def _resumen_fadiman(proyecto):
    if not proyecto.datos.get('inicio'):
        return 'Aún no defines tu inicio'
    hoy = timezone.localdate()
    dia = dia_del_protocolo(proyecto.datos, hoy)
    if dia['fase'] == 'sin_empezar':
        return 'Empieza pronto'
    if dia['fase'] == 'descanso':
        return f'Descanso · semana {dia["semana"]} de {proyecto.datos["semanas_descanso"]}'
    return f'Ciclo {dia["vuelta"]} · semana {dia["semana"]} de {proyecto.datos["semanas_ciclo"]} · día {dia["dia"]}'


def _avisos_fadiman(proyecto, fecha):
    datos = proyecto.datos
    if not datos.get('avisar', True) or not datos.get('inicio'):
        return []
    dia = dia_del_protocolo(datos, fecha)
    hora = a_hora(datos.get('hora_aviso')) or HORA_AVISO
    if dia['fase'] == 'ciclo' and dia['dia'] == 1:
        if _de_ese_dia(proyecto, fecha, 'dosis').exists():
            return []
        return [{'clave': 'toma', 'hora': hora, 'titulo': 'Hoy es tu día 1 del protocolo',
                 'cuerpo': 'Toca tu toma de la mañana. Anótala en Salud cuando la hagas.', 'accion': ''}]
    if dia['fase'] == 'ciclo' and dia['dia'] == 2:
        if _de_ese_dia(proyecto, fecha, 'observacion').exists():
            return []
        return [{'clave': 'observar', 'hora': hora, 'titulo': 'Día de transición: ¿cómo estás?',
                 'cuerpo': 'Hoy no hay toma. Anota cómo van tu ánimo y tu energía.', 'accion': ''}]
    previo = dia_del_protocolo(datos, fecha - timedelta(days=1))
    if dia['fase'] == 'descanso' and previo['fase'] == 'ciclo':
        return [{'clave': 'descanso', 'hora': hora, 'titulo': 'Terminó tu ciclo: toca descansar',
                 'cuerpo': f'Descansa {datos.get("semanas_descanso", 2)} semanas para evaluar cómo te fue.',
                 'accion': ''}]
    return []


def _resuelto_fadiman(proyecto, clave, fecha):
    return fecha < timezone.localdate() or not _avisos_fadiman(proyecto, fecha)


FADIMAN = Tipo(nombre='Protocolo Fadiman', valida=_valida_fadiman, avance=_avance_fadiman,
               resumen=_resumen_fadiman, avisos=_avisos_fadiman, resuelto=_resuelto_fadiman)


# ── El tipo «otros suplementos» ─────────────────────────────────────────────────
def _resumen_suplementos(proyecto):
    hoy = timezone.localdate()
    hoy_n = proyecto.tomas_salud.filter(fecha=hoy).count()
    semana = proyecto.tomas_salud.filter(fecha__gt=hoy - timedelta(days=7)).count()
    return f'{hoy_n} {"toma" if hoy_n == 1 else "tomas"} hoy · {semana} en 7 días'


SUPLEMENTOS = Tipo(nombre='Otros suplementos', resumen=_resumen_suplementos)
