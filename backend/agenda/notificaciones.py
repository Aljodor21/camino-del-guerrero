"""Avisos del día: agua, tomas de suplemento, dormir, entreno, comidas y recordatorios.

Cada aviso se crea cuando llega su hora (una sola vez por clave), se manda al celular
y queda pendiente en la app hasta que el usuario confirma que lo hizo. Al confirmar se
guarda el dato (vaso, toma, hora de acostarse, entreno). Los del entreno, los de contar
una comida y los recordatorios también se resuelven solos cuando eso pasa por otro lado.
"""
import math
from datetime import datetime, time, timedelta

from django.core import signing
from django.db import transaction
from django.utils import timezone

from core.exceptions import ReglaNegocioError
from . import horarios, sueno
from nutricion.grupos import NOMBRE_GRUPO, NOMBRE_TIEMPO
from nutricion import minutas
from nutricion.models import RegistroComida, Suplemento
from progress.models import RegistroEntrenamiento
from users.procesos import proceso_de_referencia
from routines.models import DiaRutina

from .models import Habitos, Notificacion, Recordatorio, RegistroHabito

ARTICULO_TIEMPO = {'desayuno': 'el', 'onces': 'las', 'almuerzo': 'el', 'algo': 'el', 'cena': 'la', 'merienda': 'la'}
VASO_ML = 250  # tamaño por defecto; cada persona puede indicar el suyo (Habitos.vaso_ml)
HORA_LEVANTARSE = horarios.LEVANTARSE_POR_DEFECTO
HORA_DORMIR = horarios.DORMIR_POR_DEFECTO
HORA_ENTRENO = time(7, 0)
HORA_RECORDATORIO = time(8, 0)
ANTES_DE_DORMIR = timedelta(minutes=30)
# El aviso de «¿cómo te fue con...?» llega un rato después de la hora de comer, no a la misma hora.
DESPUES_DE_COMER = timedelta(minutes=45)
# Hay avisos que solo tienen sentido cerca de su hora («¿ya te levantaste?» a las 11 de la mañana no lo tiene):
# pasado este rato no se crean, aunque sea la primera vez que la app los calcula (por ejemplo, al cambiar las
# horas o al estrenar el aviso), y si ya estaban pendientes se quitan solos.
VIGENCIA_DEL_MOMENTO = {'levantar': timedelta(minutes=90), 'dormir': timedelta(minutes=90)}
# Lo que se atrasó más de esto no se manda al celular (ej. el servidor estuvo apagado).
VIGENCIA_PUSH = timedelta(hours=2)
FIRMA = 'agenda.notificacion'
VIGENCIA_FIRMA = 7 * 24 * 3600


def hora_en_palabras(hora):
    """time(22, 0) → '10:00 p. m.'"""
    return f'{hora.hour % 12 or 12}:{hora.minute:02d} {"a. m." if hora.hour < 12 else "p. m."}'


def _momento(fecha, hora):
    return timezone.make_aware(datetime.combine(fecha, hora))


def habitos_de(usuario):
    return Habitos.objects.filter(usuario=usuario).first() or Habitos(usuario=usuario)


def vaso_ml(habitos):
    return habitos.vaso_ml or VASO_ML


def vasos_meta(habitos):
    return math.ceil(habitos.agua_ml / vaso_ml(habitos)) if habitos.agua_ml else 0


def _horas_agua(habitos, fecha, horas):
    """La meta de vasos repartida entre una hora después de levantarse y una antes de dormir
    (con las horas de ese día)."""
    vasos = vasos_meta(habitos)
    if not vasos:
        return []
    propias = habitos.horas_agua or {}
    desde, hasta = horarios.a_hora(propias.get('inicio')), horarios.a_hora(propias.get('fin'))
    inicio = _momento(fecha, desde) if desde else _momento(fecha, horas['levantarse'] or HORA_LEVANTARSE) + timedelta(hours=1)
    fin = _momento(fecha, hasta) if hasta else _momento(fecha, horas['dormir'] or HORA_DORMIR) - timedelta(hours=1)
    if fin <= inicio:
        fin = inicio + timedelta(hours=12)
    paso = (fin - inicio) / max(vasos - 1, 1)
    return [inicio + paso * i for i in range(vasos)]


def _reemplaza_en_palabras(reemplaza):
    partes = [f'{p:g} de {NOMBRE_GRUPO[g].lower()}' for g, p in reemplaza.items()]
    return ' y '.join(partes)


def _suplementos_del_dia(usuario, fecha):
    """Los que van ese día, de procesos que no han terminado."""
    return [s for s in Suplemento.objects.filter(usuario=usuario, fecha_fin__isnull=True)
            .select_related('proceso') if s.proceso.estado != 'finalizado' and s.activo_en(fecha)]


def _levantado_ese_dia(usuario, fecha):
    """La hora a la que la persona anotó que se levantó ese día, o None."""
    registro = (RegistroHabito.objects.filter(usuario=usuario, tipo='levantar', fecha=fecha)
                .order_by('-id').first())
    return timezone.localtime(registro.momento).time() if registro else None


def _comidas_del_dia(usuario, habitos, fecha, horas_dia, apagados, ahora):
    """(tiempos del plan, {tiempo: hora}, retenidas).

    Solo las comidas que el plan tiene. Si la persona aún no anota que se levantó y todavía no pasa
    la hora en que dijo que lo haría (más un rato de gracia), las comidas de hoy se retienen: no
    tiene sentido preguntar por el desayuno a quien sigue dormido."""
    minuta = minutas.vigente_de(usuario)
    if minuta and minuta.proceso.fecha_inicio > fecha:
        minuta = None
    tiempos = list(minuta.tiempos()) if minuta else []
    hoy = timezone.localdate(ahora) if ahora else None
    levantado = _levantado_ese_dia(usuario, fecha) if fecha == hoy else None
    horas = horarios.horas_de_comidas(habitos, fecha, tiempos, levantado=levantado)
    retenidas = bool(
        ahora and fecha == hoy and levantado is None and 'levantar' not in apagados and horas_dia['levantarse']
        and ahora < _momento(fecha, horas_dia['levantarse']) + horarios.GRACIA_LEVANTARSE)
    return tiempos, horas, retenidas


# Un pendiente con hora avisa una hora, media hora y un cuarto de hora antes, y en el momento. Cada
# aviso reemplaza al anterior (en la bandeja y en la barra de notificaciones del celular).
ETAPAS_RECORDATORIO = (60, 30, 15, 0)


def _con_punto(texto):
    """Cierra la frase con un punto, salvo que ya termine en uno (las horas terminan en «a. m.»)."""
    return texto if texto.endswith('.') else texto + '.'


def _texto_de_etapa(minutos):
    return {60: 'En 1 hora', 30: 'En 30 minutos', 15: 'En 15 minutos', 0: 'Ahora'}[minutos]


def _avisos_de_recordatorio(r, fecha):
    """Los avisos de un pendiente o de la agenda para ese día."""
    avisos = []
    grupo = f'recordatorio:{r.id}:{r.fecha}'
    # Días antes: un aviso por la mañana.
    if r.avisar_dias_antes and r.fecha - timedelta(days=r.avisar_dias_antes) == fecha:
        avisos.append({
            'tipo': 'recordatorio', 'clave': grupo, 'programada_para': _momento(fecha, HORA_RECORDATORIO),
            'titulo': r.titulo[:120], 'cuerpo': f'Es el {r.fecha.strftime("%d/%m")}.',
            'recordatorio': r, 'datos': {'fecha': r.fecha.isoformat()},
        })
    if r.fecha != fecha:
        return avisos
    if not r.hora:
        avisos.append({
            'tipo': 'recordatorio', 'clave': f'{grupo}:hoy', 'programada_para': _momento(fecha, HORA_RECORDATORIO),
            'titulo': r.titulo[:120], 'cuerpo': 'Es hoy.',
            'recordatorio': r, 'datos': {'fecha': r.fecha.isoformat()},
        })
        return avisos
    for minutos in ETAPAS_RECORDATORIO:
        cuando = _momento(fecha, r.hora) - timedelta(minutes=minutos)
        if timezone.localtime(cuando).date() != fecha:
            continue                        # a las 00:30 la «1 hora antes» caería el día anterior
        avisos.append({
            'tipo': 'recordatorio', 'clave': f'{grupo}:{minutos}', 'programada_para': cuando,
            'titulo': f'{_texto_de_etapa(minutos)}: {r.titulo}'[:120],
            'cuerpo': _con_punto(f'A las {hora_en_palabras(r.hora)}') + (f' {r.nota}' if r.nota else ''),
            'recordatorio': r, 'datos': {'fecha': r.fecha.isoformat(), 'grupo': grupo, 'minutos': minutos},
        })
    return avisos


def programados(usuario, fecha, ahora=None):
    """Los avisos que corresponden a ese día, con su hora: [dict]. `ahora` (solo para hoy) permite
    retener las comidas hasta que la persona diga que se levantó."""
    habitos = habitos_de(usuario)
    apagados = set(habitos.avisos_apagados)
    avisos = []
    horas_dia = horarios.horas_de(habitos, fecha)
    tiempos_plan, horas_comida, retenidas = _comidas_del_dia(usuario, habitos, fecha, horas_dia, apagados, ahora)

    if 'agua' not in apagados:
        horas = _horas_agua(habitos, fecha, horas_dia)
        for i, cuando in enumerate(horas, start=1):
            avisos.append({
                'tipo': 'agua', 'clave': f'agua:{fecha}:{i}', 'programada_para': cuando,
                'titulo': 'Toma un vaso de agua',
                'cuerpo': f'Un vaso de {vaso_ml(habitos)} ml.',
                'datos': {'vaso': i},
            })

    if 'toma' not in apagados:
        for s in _suplementos_del_dia(usuario, fecha):
            for toma in s.tomas:
                tiempo = Suplemento.clave_toma(toma)
                scoops = toma.get('scoops')
                cantidad = f'{scoops:g} {"scoop" if scoops == 1 else "scoops"} de ' if scoops else ''
                cuerpo = (_con_punto(f'A las {hora_en_palabras(time.fromisoformat(toma["hora"]))}') if toma['tiempo'] == 'otro'
                          else f'En {NOMBRE_TIEMPO[tiempo].lower()}.')
                if toma['reemplaza']:
                    cuerpo += f' Va en lugar de {_reemplaza_en_palabras(toma["reemplaza"])}.'
                if toma.get('nota'):
                    cuerpo += f' {toma["nota"]}'
                # Si la persona dijo a qué hora la toma, avisa a esa hora; si no, a la de la comida.
                if toma.get('hora'):
                    hora_toma = time.fromisoformat(toma['hora'])
                elif retenidas:
                    continue            # va con una comida y la persona sigue dormida
                else:
                    hora_toma = horas_comida.get(toma['tiempo']) or horarios.hora_comida(habitos, toma['tiempo'])
                avisos.append({
                    'tipo': 'toma', 'clave': f'toma:{s.id}:{fecha}:{tiempo}',
                    'programada_para': _momento(fecha, hora_toma),
                    'titulo': f'Tómate {cantidad}{s.nombre_visible}'[:120],
                    'cuerpo': cuerpo, 'suplemento': s,
                    # Si reemplaza algo de la comida, se cuenta junto con ella (una sola confirmación, con foto).
                    'datos': {'tiempo': tiempo, 'scoops': scoops,
                              **({'unida': True} if toma['reemplaza'] and toma['tiempo'] != 'otro' else {})},
                })

    if 'dormir' not in apagados and horas_dia['dormir']:
        hora = horas_dia['dormir']
        avisos.append({
            'tipo': 'dormir', 'clave': f'dormir:{fecha}',
            'programada_para': _momento(fecha, hora) - ANTES_DE_DORMIR,
            'titulo': 'En media hora, a dormir',
            'cuerpo': f'Tu hora de acostarte es a las {hora_en_palabras(hora)}',
            'datos': {'hora': hora.isoformat('minutes')},
        })

    if 'levantar' not in apagados and horas_dia['levantarse']:
        avisos.append({
            'tipo': 'levantar', 'clave': f'levantar:{fecha}',
            'programada_para': _momento(fecha, horas_dia['levantarse']),
            'titulo': 'Buenos días: ¿ya te levantaste?',
            'cuerpo': 'Anótalo para llevar tu promedio de sueño.',
            'datos': {'hora': horas_dia['levantarse'].isoformat('minutes')},
        })

    if 'entreno' not in apagados:
        dia = (DiaRutina.objects.filter(rutina__usuario=usuario, rutina__activa=True,
                                        dia_semana=fecha.isoweekday()).first())
        if dia:
            avisos.append({
                'tipo': 'entreno', 'clave': f'entreno:{fecha}',
                'programada_para': _momento(fecha, habitos.hora_entreno or HORA_ENTRENO),
                'titulo': 'Hoy toca entreno',
                'cuerpo': f'Tu rutina del {dia.get_dia_semana_display().lower()} te espera.',
                'datos': {'dia_rutina': dia.id},
            })

    if 'comida' not in apagados and not retenidas:
        contadas = set(RegistroComida.objects.filter(usuario=usuario, fecha=fecha).values_list('tiempo', flat=True))
        for tiempo in tiempos_plan:
            if tiempo in contadas:
                continue                    # ya la contó (por ejemplo antes de la hora): no hay nada que avisar
            hora_de_comer = _momento(fecha, horas_comida[tiempo])
            # A la hora de la comida: «es hora de comer». Si el de «¿cómo te fue?» ya le tocaba, ese basta.
            if ahora is None or ahora <= hora_de_comer + DESPUES_DE_COMER:
                avisos.append({
                    'tipo': 'comida', 'clave': f'comida:{fecha}:{tiempo}:hora',
                    'programada_para': hora_de_comer,
                    'titulo': f'Es hora {"del" if ARTICULO_TIEMPO[tiempo] == "el" else "de la"} {NOMBRE_TIEMPO[tiempo].lower()}',
                    'cuerpo': 'Cuando termines, cuéntanos qué comiste; si comes antes, también puedes contarla ya.',
                    'datos': {'tiempo': tiempo, 'grupo': f'comida:{fecha}:{tiempo}'},
                })
            avisos.append({
                'tipo': 'comida', 'clave': f'comida:{fecha}:{tiempo}',
                'programada_para': hora_de_comer + DESPUES_DE_COMER,
                'titulo': f'¿Cómo te fue con {ARTICULO_TIEMPO[tiempo]} {NOMBRE_TIEMPO[tiempo].lower()}?',
                'cuerpo': 'Cuéntanos qué comiste, con foto si quieres, para ver si vas cumpliendo tu plan.',
                # Mismo grupo que el de la hora: el de «¿cómo te fue?» lo reemplaza en la bandeja.
                'datos': {'tiempo': tiempo, 'grupo': f'comida:{fecha}:{tiempo}'},
            })

    if 'proceso' not in apagados:
        proceso = proceso_de_referencia(usuario)
        if proceso and proceso.fecha_fin_plan and proceso.fecha_fin_plan <= fecha:
            avisos.append({
                'tipo': 'proceso', 'clave': f'proceso:{proceso.id}:{proceso.fecha_fin_plan}',
                'programada_para': _momento(proceso.fecha_fin_plan, HORA_RECORDATORIO),
                'titulo': 'Llegó tu control: ¿sigues con tu proceso?',
                'cuerpo': 'Cuéntanos si sigues igual o si tienes cambios.',
                'datos': {'proceso': proceso.id, 'fin_plan': proceso.fecha_fin_plan.isoformat()},
            })

    if 'recordatorio' not in apagados:
        for r in Recordatorio.objects.pendientes().filter(usuario=usuario, fecha__gte=fecha):
            avisos.extend(_avisos_de_recordatorio(r, fecha))
    return avisos


def generar(usuario, ahora=None):
    """Crea los avisos de hoy cuya hora ya llegó, desde que la persona se registró (no los
    de horas anteriores). No repite: cada clave se crea una vez."""
    ahora = ahora or timezone.now()
    fecha = timezone.localdate(ahora)
    nuevas = []
    for aviso in programados(usuario, fecha, ahora):
        if aviso['programada_para'] > ahora or aviso['programada_para'] < usuario.date_joined:
            continue
        vigencia = VIGENCIA_DEL_MOMENTO.get(aviso['tipo'])
        if vigencia and ahora - aviso['programada_para'] > vigencia:
            continue
        clave = aviso.pop('clave')
        n, creada = Notificacion.objects.get_or_create(usuario=usuario, clave=clave,
                                                       defaults={**aviso, 'fecha': fecha})
        if creada:
            nuevas.append(n)
            _reemplazar_anteriores(n)
    resolver_automaticas(usuario, ahora)
    return nuevas


def _reemplazar_anteriores(n):
    """Un aviso del mismo grupo (el de «en 15 minutos» tras el de «en 30») deja sin pendiente al anterior:
    en la bandeja queda solo el último."""
    grupo = n.datos.get('grupo')
    if not grupo:
        return
    (Notificacion.objects.filter(usuario=n.usuario, resuelta_en__isnull=True, datos__grupo=grupo)
     .exclude(pk=n.pk).update(resuelta_en=timezone.now(), resolucion='automatica'))


def proximos(usuario, dias=7, ahora=None):
    """Los avisos que vienen en los próximos días, para que el celular los programe él mismo
    y suenen aunque la app esté cerrada. Solo los que aún no llegan a su hora: los que ya
    pasaron están en la bandeja."""
    ahora = ahora or timezone.now()
    hoy = timezone.localdate(ahora)
    ya_creados = set(Notificacion.objects.filter(usuario=usuario, fecha__gte=hoy).values_list('clave', flat=True))
    lista = []
    for i in range(dias):
        for aviso in programados(usuario, hoy + timedelta(days=i)):
            if aviso['programada_para'] <= ahora or aviso['clave'] in ya_creados:
                continue
            lista.append({'clave': aviso['clave'], 'grupo': aviso.get('datos', {}).get('grupo'),
                          'tipo': aviso['tipo'], 'titulo': aviso['titulo'],
                          'cuerpo': aviso['cuerpo'], 'programada_para': aviso['programada_para']})
    return sorted(lista, key=lambda a: a['programada_para'])


def resolver_automaticas(usuario, ahora=None):
    """Lo que ya pasó por otro lado: entrenó, completó o movió el recordatorio; o ya no tiene sentido
    (el aviso de levantarse horas después)."""
    ahora = ahora or timezone.now()
    pendientes = Notificacion.objects.filter(usuario=usuario, resuelta_en__isnull=True,
                                             tipo__in=['entreno', 'recordatorio', 'comida', 'proceso',
                                                       *VIGENCIA_DEL_MOMENTO])
    for n in pendientes.select_related('recordatorio'):
        if n.tipo in VIGENCIA_DEL_MOMENTO:
            hecho = ahora - n.programada_para > VIGENCIA_DEL_MOMENTO[n.tipo]
        elif n.tipo == 'entreno':
            hecho = RegistroEntrenamiento.objects.filter(usuario=usuario, fecha=n.fecha).exists()
        elif n.tipo == 'proceso':
            proceso = proceso_de_referencia(usuario)
            hecho = proceso is None or proceso.id != n.datos.get('proceso') \
                or (proceso.fecha_fin_plan.isoformat() if proceso.fecha_fin_plan else None) != n.datos.get('fin_plan')
        elif n.tipo == 'comida':
            hecho = RegistroComida.objects.filter(usuario=usuario, fecha=n.fecha, tiempo=n.datos.get('tiempo')).exists()
        else:
            r = n.recordatorio
            hecho = r is None or r.completado_en is not None or r.fecha.isoformat() != n.datos.get('fecha')
        if hecho:
            n.resuelta_en, n.resolucion = ahora, 'automatica'
            n.save(update_fields=['resuelta_en', 'resolucion'])


def pendientes(usuario):
    generar(usuario)
    return (Notificacion.objects.filter(usuario=usuario, resuelta_en__isnull=True)
            .select_related('suplemento', 'recordatorio'))


@transaction.atomic
def confirmar(notificacion):
    """El usuario dice que lo hizo: se guarda el dato y el aviso sale de la bandeja."""
    n = Notificacion.objects.select_for_update().get(pk=notificacion.pk)
    if n.resuelta_en:
        return n
    ahora = timezone.now()
    if n.tipo == 'toma' and n.datos.get('unida'):
        raise ReglaNegocioError('Esta toma va con tu comida: cuéntala desde ahí para guardar también la foto.')
    if n.tipo in ('agua', 'toma', 'dormir', 'levantar'):
        datos = n.datos
        RegistroHabito.objects.create(
            usuario=n.usuario, tipo=n.tipo, fecha=n.fecha, momento=ahora, notificacion=n,
            cantidad=datos.get('scoops') or 1, suplemento=n.suplemento, tiempo=datos.get('tiempo', ''),
            ml=vaso_ml(habitos_de(n.usuario)) if n.tipo == 'agua' else None)
    elif n.tipo == 'entreno':
        if not RegistroEntrenamiento.objects.filter(usuario=n.usuario, fecha=n.fecha).exists():
            RegistroEntrenamiento.objects.create(
                usuario=n.usuario, fecha=n.fecha, dia_rutina_id=n.datos.get('dia_rutina'),
                notas='Marcado desde el aviso.')
    elif n.tipo == 'proceso':
        raise ReglaNegocioError('Cuéntanos qué sigue desde "Tu control": así queda registrado.')
    elif n.tipo == 'comida':
        raise ReglaNegocioError('Cuenta qué comiste desde el aviso: así guardamos cómo vas con tu plan.')
    elif n.tipo == 'recordatorio':
        r = n.recordatorio
        if r is not None and r.automatico:
            raise ReglaNegocioError('Este se resuelve desde tu suplemento, en Progreso.')
        if r is not None and r.completado_en is None:
            r.completado_en = ahora
            r.save(update_fields=['completado_en'])
    n.resuelta_en, n.resolucion = ahora, 'confirmada'
    n.save(update_fields=['resuelta_en', 'resolucion'])
    return n


@transaction.atomic
def registrar_agua(usuario):
    """Un vaso que el usuario anota sin esperar el aviso: cumple el aviso de agua pendiente
    más viejo de hoy, si hay."""
    hoy = timezone.localdate()
    n = (Notificacion.objects.select_for_update()
         .filter(usuario=usuario, tipo='agua', fecha=hoy, resuelta_en__isnull=True).first())
    if n:
        return confirmar(n).registro
    return RegistroHabito.objects.create(usuario=usuario, tipo='agua', fecha=hoy,
                                         ml=vaso_ml(habitos_de(usuario)))


def _la_ultima(usuario, tipo, **filtro):
    """Lo último que la persona dijo: si corrige una hora, manda la nueva (los registros viejos no se tocan)."""
    return RegistroHabito.objects.filter(usuario=usuario, tipo=tipo, **filtro).order_by('-id').first()


@transaction.atomic
def registrar_levantar(usuario):
    """«Me levanté»: anota la hora de ahora, una sola vez al día, y cumple el aviso si está pendiente. Es un
    valor y ya: no se cambia a mano (para no engañarse); si hubo más de uno, vale el último."""
    hoy = timezone.localdate()
    ya = _la_ultima(usuario, 'levantar', fecha=hoy)
    if ya:
        return ya
    n = (Notificacion.objects.select_for_update()
         .filter(usuario=usuario, tipo='levantar', fecha=hoy, resuelta_en__isnull=True).first())
    if n:
        return confirmar(n).registro
    return RegistroHabito.objects.create(usuario=usuario, tipo='levantar', fecha=hoy)


# Antes de esta hora, acostarse todavía es del día anterior (se fue a dormir pasada la medianoche).
HORA_CORTE_DORMIR = time(4, 0)


@transaction.atomic
def registrar_dormir(usuario):
    """«Me acosté»: anota la hora de ahora, una sola vez por noche, y cumple el aviso si está pendiente."""
    ahora = timezone.localtime()
    fecha = ahora.date() - timedelta(days=1) if ahora.time() < HORA_CORTE_DORMIR else ahora.date()
    ya = _la_ultima(usuario, 'dormir', fecha=fecha)
    if ya:
        return ya
    n = (Notificacion.objects.select_for_update()
         .filter(usuario=usuario, tipo='dormir', fecha=fecha, resuelta_en__isnull=True).first())
    if n:
        return confirmar(n).registro
    return RegistroHabito.objects.create(usuario=usuario, tipo='dormir', fecha=fecha)


def resumen_de_hoy(usuario):
    """Cómo va el día: vasos, tomas, entreno y la hora de dormir."""
    hoy = timezone.localdate()
    habitos = habitos_de(usuario)
    registros = RegistroHabito.objects.filter(usuario=usuario, fecha=hoy)
    hechas = {(r.suplemento_id, r.tiempo) for r in registros if r.tipo == 'toma'}
    tomas = [{'suplemento': s.id, 'nombre': s.nombre_visible, 'tiempo': Suplemento.clave_toma(t),
              'hora': t.get('hora'), 'scoops': t.get('scoops'),
              'hecha': (s.id, Suplemento.clave_toma(t)) in hechas}
             for s in _suplementos_del_dia(usuario, hoy) for t in s.tomas]
    toca_entreno = DiaRutina.objects.filter(rutina__usuario=usuario, rutina__activa=True,
                                            dia_semana=hoy.isoweekday()).exists()
    acostado = registros.filter(tipo='dormir').order_by('-id').first()
    levantado = registros.filter(tipo='levantar').order_by('-id').first()
    horas_hoy = horarios.horas_de(habitos, hoy)
    anoche = sueno.anoche(usuario)
    vasos = sorted((r for r in registros if r.tipo == 'agua'), key=lambda r: r.momento)
    return {
        'fecha': hoy,
        'agua': {'meta': vasos_meta(habitos), 'vasos': sum(r.cantidad for r in vasos),
                 'ml_vaso': vaso_ml(habitos), 'meta_ml': habitos.agua_ml,
                 # Lo que se tomó de verdad: cada vaso con su tamaño de entonces y la hora del clic.
                 'ml_total': sum(r.ml or VASO_ML for r in vasos),
                 'registros': [{'momento': r.momento, 'ml': r.ml or VASO_ML} for r in vasos]},
        'tomas': tomas,
        'comidas': _comidas_de_hoy(usuario, habitos, hoy),
        'entreno': {'toca': toca_entreno,
                    'hecho': RegistroEntrenamiento.objects.filter(usuario=usuario, fecha=hoy).exists()},
        'dormir': {'hora': horas_hoy['dormir'], 'acostado': acostado.momento if acostado else None},
        'levantar': {'hora': horas_hoy['levantarse'], 'levantado': levantado.momento if levantado else None,
                     'dormiste_horas': (anoche or {}).get('horas'),
                     # Cuántos minutos antes (−) o después (+) de lo previsto se acostó anoche y se levantó hoy.
                     'acostarse_min': (anoche or {}).get('dif_acostarse_min'),
                     'levantarse_min': (anoche or {}).get('dif_levantarse_min')},
        # Las horas de hoy y de mañana, para poder cambiarlas solo por ese día.
        'horario': {'hoy': {**_en_texto(horas_hoy)},
                    'manana': {**_en_texto(horarios.horas_de(habitos, hoy + timedelta(days=1)))}},
    }


def _comidas_de_hoy(usuario, habitos, hoy):
    """Las comidas del plan de hoy con su hora y si ya se contaron: así se puede contar una antes del aviso."""
    minuta = minutas.vigente_de(usuario)
    if minuta is None:
        return []
    tiempos = list(minuta.tiempos())
    horas = horarios.horas_de_comidas(habitos, hoy, tiempos)
    contadas = set(RegistroComida.objects.filter(usuario=usuario, fecha=hoy).values_list('tiempo', flat=True))
    return [{'tiempo': t, 'nombre': NOMBRE_TIEMPO[t], 'hora': horas[t].isoformat('minutes'),
             'contada': t in contadas} for t in tiempos]


def _en_texto(horas):
    return {'levantarse': horas['levantarse'].isoformat('minutes') if horas['levantarse'] else None,
            'dormir': horas['dormir'].isoformat('minutes') if horas['dormir'] else None,
            'personalizado': horas['personalizado']}


# ── Confirmar desde el celular ──────────────────────────────────────────────
# El aviso lleva una firma para confirmar con el botón de la notificación, sin abrir la app.

def firmar(notificacion):
    return signing.dumps({'n': notificacion.id}, salt=FIRMA)


def desde_firma(token):
    try:
        datos = signing.loads(token, salt=FIRMA, max_age=VIGENCIA_FIRMA)
    except signing.BadSignature:
        raise ReglaNegocioError('El aviso ya no es válido. Ábrelo desde la app.')
    n = Notificacion.objects.filter(pk=datos.get('n')).first()
    if n is None:
        raise ReglaNegocioError('El aviso ya no existe.')
    return n


def cuerpo_de(n):
    """El texto del aviso. El del agua se arma al mostrarlo y dice cuánto llevas hoy: el número del
    recordatorio (el 3 de 4) no es lo que la persona ha tomado y la confundía."""
    if n.tipo != 'agua':
        return n.cuerpo
    habitos = habitos_de(n.usuario)
    meta = vasos_meta(habitos)
    if not meta:
        return n.cuerpo
    tomados = sum(r.cantidad for r in RegistroHabito.objects.filter(usuario=n.usuario, tipo='agua', fecha=n.fecha))
    llevas = int(tomados) if tomados == int(tomados) else float(tomados)
    return f'Llevas {llevas} de {meta} vasos de hoy ({vaso_ml(habitos)} ml cada uno).'


def toma_registrada(usuario, fecha, suplemento, tiempo):
    return RegistroHabito.objects.filter(usuario=usuario, tipo='toma', fecha=fecha,
                                         suplemento=suplemento, tiempo=tiempo).exists()


@transaction.atomic
def registrar_tomas_de_comida(usuario, fecha, tiempo, suplementos):
    """Las tomas que la persona dice haber hecho al contar su comida: quedan registradas y su aviso, cumplido."""
    ahora = timezone.now()
    for s in _suplementos_del_dia(usuario, fecha):
        toma = s.toma_en(tiempo)
        if toma is None or s.id not in suplementos:
            continue
        if toma_registrada(usuario, fecha, s, tiempo):
            continue
        n = (Notificacion.objects.select_for_update()
             .filter(usuario=usuario, clave=f'toma:{s.id}:{fecha}:{tiempo}', resuelta_en__isnull=True).first())
        RegistroHabito.objects.create(
            usuario=usuario, tipo='toma', fecha=fecha, momento=ahora, notificacion=n,
            cantidad=toma.get('scoops') or 1, suplemento=s, tiempo=tiempo)
        if n:
            n.resuelta_en, n.resolucion = ahora, 'confirmada'
            n.save(update_fields=['resuelta_en', 'resolucion'])


def accion_de(notificacion):
    """Texto del botón para confirmar, o vacío si se resuelve en otra parte."""
    return {
        'agua': 'Ya lo tomé',
        'toma': '' if notificacion.datos.get('unida') else 'Ya me la tomé',
        'dormir': 'Ya me acosté',
        'levantar': 'Ya me levanté',
        'entreno': 'Ya entrené',
        'comida': '',
        'proceso': '',
        'recordatorio': '' if notificacion.recordatorio_id and notificacion.recordatorio.automatico else 'Listo',
    }[notificacion.tipo]


def url_de(notificacion):
    """Adónde lleva el aviso al tocarlo."""
    if notificacion.tipo == 'comida' or (notificacion.tipo == 'toma' and notificacion.datos.get('unida')):
        return f'/comidas/contar?tiempo={notificacion.datos.get("tiempo", "")}&fecha={notificacion.fecha}'
    if notificacion.tipo == 'proceso':
        return '/control'
    return '/avisos'
