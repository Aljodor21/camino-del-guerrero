"""Salud: el protocolo Fadiman de microdosis y el control de otros suplementos.

**Protocolo Fadiman** (`fadiman`): un ciclo de 3 días que se repite: día 1 la toma (por la mañana), día 2 de
transición (se observa el ánimo y la energía), día 3 normal y día 4 es otra vez día 1. Dura de 4 a 8 semanas y
sigue un descanso de 2 a 4 semanas para evaluar y evitar la tolerancia. La app solo lleva el calendario y lo que la
persona anota: no recomienda sustancias ni dosis (la sustancia y la cantidad las escribe ella), y lo que anota no se
edita. La toma solo se anota el día que toca (día 1 del ciclo y fuera del descanso); `fuera_de_protocolo` queda para
lo anotado antes de esa regla.

**Otros suplementos** (`otros_suplementos`): lo que toma además de lo del plan de nutrición. Cada suplemento es un
**plan** en `Proyecto.datos['planes']`: qué, cuánto, qué días de la semana, a qué horas y cuánto dura el tratamiento
(desde `inicio`, `duracion_dias` días, o sin fin). A cada hora llega un aviso con «Ya lo tomé», que anota la toma
ligada a su plan y hora (`TomaSalud.plan`). También se puede anotar una toma suelta.

Todo cuelga de `TomaSalud`. En `Proyecto.datos` del protocolo van solo los ajustes: `sustancia`, `dosis`, `inicio`
(el día 1 del primer ciclo), `semanas_ciclo`, `semanas_descanso`, `avisar` y `hora_aviso`.
"""
import uuid
from datetime import date, time, timedelta

from django.db import transaction
from django.utils import timezone

from agenda.horarios import a_hora
from core.exceptions import ReglaNegocioError

from .models import TomaSalud
from .tipos_base import Tipo

# Día 1 la toma, día 2 transición, día 3 normal; el siguiente vuelve a ser día 1 (una toma cada 3 días).
DIAS_CICLO = 3
SEMANAS_CICLO = (4, 8)
SEMANAS_DESCANSO = (2, 4)
HORA_AVISO = time(8, 0)
MAX_PLANES = 20
MAX_HORAS = 6
MAX_DURACION = 730
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
    """Dónde cae ese día: `{fase: 'sin_empezar'|'ciclo'|'descanso', dia (1 a 3, solo en ciclo), vuelta, semana}`.

    Desde `inicio` corren `semanas_ciclo` semanas en ciclo de 3 días y luego `semanas_descanso` de descanso; así
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


def tomas_del_primer_ciclo(proyecto):
    """Las tomas del primer ciclo que se pueden llevar en la app: si la persona ya había empezado antes de
    registrarse, lo de antes no se cuenta (no se anota hacia atrás), así el avance no queda en cero."""
    return [d for d in dias_de_toma_del_ciclo(proyecto.datos) if d >= proyecto.creado]


def _de_ese_dia(proyecto, fecha, clase):
    return proyecto.tomas_salud.filter(fecha=fecha, clase=clase)


# ── Anotar ──────────────────────────────────────────────────────────────────────
def _validar_fecha(fecha):
    """Lo de un día se anota ese día (como las comidas y los gastos)."""
    if fecha != timezone.localdate():
        raise ReglaNegocioError('Solo se anota lo de hoy.')


def _nivel(valor, nombre):
    if valor in (None, ''):
        return None
    return _entre(valor, (1, 5), nombre)


@transaction.atomic
def anotar(proyecto, fecha, clase, nombre='', cantidad='', animo=None, energia=None, nota='', plan=''):
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
            if not (_ajustes(ajustes)['inicio'] and dia_del_protocolo(ajustes, fecha)['dia'] == 1):
                raise ReglaNegocioError('Hoy no toca: la toma es solo el día 1 de cada ciclo de 3 días.')
            if _de_ese_dia(proyecto, fecha, 'dosis').exists():
                raise ReglaNegocioError('Ese día ya anotaste tu toma.')
            fuera = False
        else:
            fuera = False
            if plan:
                p = plan_de(proyecto, plan, fecha)
                if proyecto.tomas_salud.filter(fecha=fecha, plan=plan).exists():
                    raise ReglaNegocioError('Esa toma ya está anotada.')
                nombre, cantidad = p['nombre'], p['cantidad']
        nombre, cantidad = _texto(nombre, 60), _texto(cantidad, 40)
        if not nombre:
            raise ReglaNegocioError('Escribe qué tomaste.')
        if not cantidad:
            raise ReglaNegocioError('Escribe cuánto tomaste.')
    return TomaSalud.objects.create(proyecto=proyecto, fecha=fecha, clase=clase, nombre=nombre, cantidad=cantidad,
                                    animo=animo, energia=energia, nota=_texto(nota, 300),
                                    fuera_de_protocolo=fuera, plan=plan if clase == 'dosis' else '')


def borrar(toma):
    """Solo el mismo día que se anotó, por si fue un error."""
    if timezone.localtime(toma.anotado).date() != timezone.localdate():
        raise ReglaNegocioError('Solo puedes borrar lo que anotaste hoy.')
    toma.delete()


# ── Lo que ve la persona ────────────────────────────────────────────────────────
def _toma(t, hoy):
    return {'id': t.id, 'fecha': t.fecha, 'clase': t.clase, 'nombre': t.nombre, 'cantidad': t.cantidad,
            'animo': t.animo, 'energia': t.energia, 'nota': t.nota, 'fuera_de_protocolo': t.fuera_de_protocolo,
            'plan': t.plan, 'hora': _hora_de(t), 'se_puede_borrar': timezone.localtime(t.anotado).date() == hoy}


def _hora_de(toma):
    """La hora en que se anotó (la toma se anota cuando se hace: es la hora de la toma)."""
    return timezone.localtime(toma.anotado).strftime('%H:%M')


def calendario(proyecto, hoy):
    """La vuelta en curso (ciclo + descanso), día por día, para dibujarla: qué toca cada día y qué se hizo.

    Cada toma prevista queda `hecha`, `perdida` (ya pasó sin anotarse), `pendiente` (hoy o más adelante) o
    `antes` (antes de que se registrara en la app: no se sabe)."""
    ajustes = proyecto.datos
    a = _ajustes(ajustes)
    if a['inicio'] is None:
        return None
    periodo = (a['semanas_ciclo'] + a['semanas_descanso']) * 7
    vuelta = max(dia_del_protocolo(ajustes, hoy)['vuelta'], 1)
    desde = a['inicio'] + timedelta(days=(vuelta - 1) * periodo)
    hasta = desde + timedelta(days=periodo - 1)
    tomas = set(proyecto.tomas_salud.filter(clase='dosis', fecha__range=(desde, hasta)).values_list('fecha', flat=True))
    vistas = set(proyecto.tomas_salud.filter(clase='observacion', fecha__range=(desde, hasta))
                 .values_list('fecha', flat=True))
    dias = []
    for n in range(periodo):
        fecha = desde + timedelta(days=n)
        d = dia_del_protocolo(ajustes, fecha)
        toma = None
        if d['dia'] == 1:
            toma = ('hecha' if fecha in tomas else 'antes' if fecha < proyecto.creado
                    else 'pendiente' if fecha >= hoy else 'perdida')
        dias.append({'fecha': fecha, 'fase': d['fase'], 'dia': d['dia'], 'toma': toma,
                     'observacion': fecha in vistas, 'hoy': fecha == hoy})
    previstas = [x for x in dias if x['toma'] and x['toma'] != 'antes']
    fin_ciclo = desde + timedelta(days=a['semanas_ciclo'] * 7 - 1)
    return {
        'vuelta': vuelta, 'desde': desde, 'fin_ciclo': fin_ciclo, 'hasta': hasta,
        'siguiente_vuelta': hasta + timedelta(days=1), 'dias': dias,
        'tomas': {'previstas': len(previstas), 'hechas': sum(1 for x in previstas if x['toma'] == 'hecha'),
                  'perdidas': sum(1 for x in previstas if x['toma'] == 'perdida')},
    }


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
        datos.update(estado_planes(proyecto, hoy))
        return datos
    ajustes = proyecto.datos
    dia = dia_del_protocolo(ajustes, hoy)
    previstas = tomas_del_primer_ciclo(proyecto)
    hechas = {t.fecha for t in proyecto.tomas_salud.filter(clase='dosis')}
    siguiente = None
    if _ajustes(ajustes)['inicio']:
        siguiente = next((hoy + timedelta(days=d) for d in range(0, 400)
                          if dia_del_protocolo(ajustes, hoy + timedelta(days=d))['dia'] == 1), None)
    datos.update({
        'dia': dia, 'etapa': ETAPAS.get(dia['dia']), 'toma_hoy': hoy in hechas,
        'observacion_hoy': _de_ese_dia(proyecto, hoy, 'observacion').exists(),
        'siguiente_toma': siguiente, 'empezo': _ajustes(ajustes)['inicio'],
        'registrado': proyecto.creado, 'calendario': calendario(proyecto, hoy),
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
    previstas = tomas_del_primer_ciclo(proyecto)
    if not previstas:
        return 0
    hechas = set(proyecto.tomas_salud.filter(clase='dosis', fecha__in=previstas).values_list('fecha', flat=True))
    return round(100 * len(hechas) / len(previstas))


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


# ── El tipo «otros suplementos»: planes con días, horas y duración ──────────────
def _hora(valor):
    hora = a_hora(valor) if isinstance(valor, str) else None
    if hora is None:
        raise ReglaNegocioError('Las horas van así: 08:00.')
    return hora.isoformat('minutes')


def _plan_limpio(p, hoy):
    if not isinstance(p, dict):
        raise ReglaNegocioError('Suplemento no válido.')
    nombre, cantidad = _texto(p.get('nombre'), 60), _texto(p.get('cantidad'), 40)
    if not nombre:
        raise ReglaNegocioError('Escribe qué vas a tomar.')
    if not cantidad:
        raise ReglaNegocioError(f'{nombre}: escribe cuánto tomas.')
    dias = p.get('dias')
    if not isinstance(dias, list) or not dias or not all(isinstance(d, int) and 0 <= d <= 6 for d in dias):
        raise ReglaNegocioError(f'{nombre}: elige al menos un día.')
    horas = p.get('horas')
    if not isinstance(horas, list) or not horas:
        raise ReglaNegocioError(f'{nombre}: pon al menos una hora.')
    horas = sorted({_hora(h) for h in horas})
    if len(horas) > MAX_HORAS:
        raise ReglaNegocioError(f'{nombre}: hasta {MAX_HORAS} horas al día.')
    inicio = _fecha(p.get('inicio')) or hoy
    duracion = p.get('duracion_dias')
    duracion = None if duracion in (None, '') else _entre(duracion, (1, MAX_DURACION), f'{nombre}: días de tratamiento')
    ident = str(p.get('id') or '')
    if not (len(ident) == 8 and ident.isalnum()):
        ident = uuid.uuid4().hex[:8]
    return {'id': ident, 'nombre': nombre, 'cantidad': cantidad, 'dias': sorted(set(dias)), 'horas': horas,
            'inicio': inicio.isoformat(), 'duracion_dias': duracion, 'nota': _texto(p.get('nota'), 200),
            'avisar': bool(p.get('avisar', True))}


def _valida_suplementos(datos):
    if not isinstance(datos, dict):
        raise ReglaNegocioError('Datos no válidos.')
    planes = datos.get('planes') or []
    if not isinstance(planes, list) or len(planes) > MAX_PLANES:
        raise ReglaNegocioError(f'Hasta {MAX_PLANES} suplementos.')
    hoy = timezone.localdate()
    limpios = [_plan_limpio(p, hoy) for p in planes]
    if len({p['id'] for p in limpios}) != len(limpios):
        raise ReglaNegocioError('Hay suplementos repetidos.')
    return {'planes': limpios}


def _fin(plan):
    """El último día del tratamiento, o None si no tiene fin."""
    if plan['duracion_dias'] is None:
        return None
    return date.fromisoformat(plan['inicio']) + timedelta(days=plan['duracion_dias'] - 1)


def toca(plan, fecha):
    """¿Ese día le toca? Dentro del tratamiento y en uno de sus días de la semana (lunes = 0)."""
    fin = _fin(plan)
    return (date.fromisoformat(plan['inicio']) <= fecha and (fin is None or fecha <= fin)
            and fecha.weekday() in plan['dias'])


def _planes(proyecto):
    return proyecto.datos.get('planes', []) if proyecto.tipo == 'otros_suplementos' else []


def plan_de(proyecto, clave, fecha):
    """El plan de una toma («id@hora»), si ese día y a esa hora le toca."""
    ident, _, hora = clave.partition('@')
    plan = next((p for p in _planes(proyecto) if p['id'] == ident), None)
    if plan is None or hora not in plan['horas'] or not toca(plan, fecha):
        raise ReglaNegocioError('Esa toma no está en tu plan de ese día.')
    return plan


def estado_planes(proyecto, hoy):
    tomadas = {t.plan: _hora_de(t) for t in proyecto.tomas_salud.filter(fecha=hoy).exclude(plan='')}
    planes, de_hoy = [], []
    for p in _planes(proyecto):
        inicio, fin = date.fromisoformat(p['inicio']), _fin(p)
        planes.append({**p, 'fin': fin, 'termino': fin is not None and hoy > fin, 'toca_hoy': toca(p, hoy),
                       'dia_tratamiento': (hoy - inicio).days + 1 if inicio <= hoy and (fin is None or hoy <= fin)
                       else None})
        if toca(p, hoy):
            de_hoy += [{'clave': f'{p["id"]}@{h}', 'hora': h, 'nombre': p['nombre'], 'cantidad': p['cantidad'],
                        'tomada': f'{p["id"]}@{h}' in tomadas, 'tomada_a': tomadas.get(f'{p["id"]}@{h}')}
                       for h in p['horas']]
    return {'planes': planes, 'de_hoy': sorted(de_hoy, key=lambda x: x['hora'])}


def _avisos_suplementos(proyecto, fecha):
    tomadas = set(proyecto.tomas_salud.filter(fecha=fecha).exclude(plan='').values_list('plan', flat=True))
    avisos = []
    for p in _planes(proyecto):
        if not p.get('avisar', True) or not toca(p, fecha):
            continue
        for h in p['horas']:
            clave = f'{p["id"]}@{h}'
            if clave not in tomadas:
                avisos.append({'clave': clave, 'hora': a_hora(h), 'titulo': f'Hora de tu {p["nombre"]}',
                               'cuerpo': p['cantidad'] + (f' · {p["nota"]}' if p.get('nota') else ''),
                               'accion': 'Ya lo tomé'})
    return avisos


def _confirmar_suplemento(proyecto, clave, fecha):
    anotar(proyecto, fecha, 'dosis', plan=clave)


def _resuelto_suplemento(proyecto, clave, fecha):
    return fecha < timezone.localdate() or clave not in {a['clave'] for a in _avisos_suplementos(proyecto, fecha)}


def _resumen_suplementos(proyecto):
    de_hoy = estado_planes(proyecto, timezone.localdate())['de_hoy']
    activos = sum(1 for p in _planes(proyecto) if _fin(p) is None or _fin(p) >= timezone.localdate())
    if not activos:
        return 'Sin suplementos en curso'
    texto = f'{activos} {"suplemento" if activos == 1 else "suplementos"}'
    if de_hoy:
        texto += f' · hoy {sum(1 for x in de_hoy if x["tomada"])} de {len(de_hoy)}'
    return texto


SUPLEMENTOS = Tipo(nombre='Otros suplementos', valida=_valida_suplementos, resumen=_resumen_suplementos,
                   avisos=_avisos_suplementos, confirmar=_confirmar_suplemento, resuelto=_resuelto_suplemento,
                   con_avance=False)
