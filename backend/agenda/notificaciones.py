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
from nutricion.grupos import HORA_TIEMPO, NOMBRE_GRUPO, NOMBRE_TIEMPO
from nutricion import minutas
from nutricion.models import RegistroComida, Suplemento
from progress.models import RegistroEntrenamiento
from users.procesos import proceso_de_referencia
from routines.models import DiaRutina

from .models import Habitos, Notificacion, Recordatorio, RegistroHabito

ARTICULO_TIEMPO = {'desayuno': 'el', 'onces': 'las', 'almuerzo': 'el', 'algo': 'el', 'cena': 'la', 'merienda': 'la'}
VASO_ML = 250
HORA_LEVANTARSE = time(6, 0)
HORA_DORMIR = time(22, 0)
HORA_ENTRENO = time(7, 0)
HORA_RECORDATORIO = time(8, 0)
ANTES_DE_DORMIR = timedelta(minutes=30)
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


def vasos_meta(habitos):
    return math.ceil(habitos.agua_ml / VASO_ML) if habitos.agua_ml else 0


def _horas_agua(habitos, fecha):
    """La meta de vasos repartida entre una hora después de levantarse y una antes de dormir."""
    vasos = vasos_meta(habitos)
    if not vasos:
        return []
    inicio = _momento(fecha, habitos.hora_levantarse or HORA_LEVANTARSE) + timedelta(hours=1)
    fin = _momento(fecha, habitos.hora_dormir or HORA_DORMIR) - timedelta(hours=1)
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


def programados(usuario, fecha):
    """Los avisos que corresponden a ese día, con su hora: [dict]."""
    habitos = habitos_de(usuario)
    apagados = set(habitos.avisos_apagados)
    avisos = []

    if 'agua' not in apagados:
        horas = _horas_agua(habitos, fecha)
        for i, cuando in enumerate(horas, start=1):
            avisos.append({
                'tipo': 'agua', 'clave': f'agua:{fecha}:{i}', 'programada_para': cuando,
                'titulo': 'Toma un vaso de agua',
                'cuerpo': f'Vaso {i} de {len(horas)} de hoy.',
                'datos': {'vaso': i},
            })

    if 'toma' not in apagados:
        for s in _suplementos_del_dia(usuario, fecha):
            for toma in s.tomas:
                tiempo = toma['tiempo']
                scoops = toma.get('scoops')
                cantidad = f'{scoops:g} {"scoop" if scoops == 1 else "scoops"} de ' if scoops else ''
                cuerpo = f'En {NOMBRE_TIEMPO[tiempo].lower()}.'
                if toma['reemplaza']:
                    cuerpo += f' Va en lugar de {_reemplaza_en_palabras(toma["reemplaza"])}.'
                avisos.append({
                    'tipo': 'toma', 'clave': f'toma:{s.id}:{fecha}:{tiempo}',
                    'programada_para': _momento(fecha, time(*HORA_TIEMPO[tiempo])),
                    'titulo': f'Tómate {cantidad}{s.nombre_visible}'[:120],
                    'cuerpo': cuerpo, 'suplemento': s,
                    'datos': {'tiempo': tiempo, 'scoops': scoops},
                })

    if 'dormir' not in apagados and habitos.hora_dormir:
        hora = habitos.hora_dormir
        avisos.append({
            'tipo': 'dormir', 'clave': f'dormir:{fecha}',
            'programada_para': _momento(fecha, hora) - ANTES_DE_DORMIR,
            'titulo': 'En media hora, a dormir',
            'cuerpo': f'Tu hora de acostarte es a las {hora_en_palabras(hora)}',
            'datos': {'hora': hora.isoformat('minutes')},
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

    if 'comida' not in apagados:
        minuta = minutas.vigente_de(usuario)
        if minuta and minuta.proceso.fecha_inicio > fecha:
            minuta = None
        for tiempo in (minuta.tiempos() if minuta else []):
            avisos.append({
                'tipo': 'comida', 'clave': f'comida:{fecha}:{tiempo}',
                'programada_para': _momento(fecha, time(*HORA_TIEMPO[tiempo])),
                'titulo': f'¿Cómo te fue con {ARTICULO_TIEMPO[tiempo]} {NOMBRE_TIEMPO[tiempo].lower()}?',
                'cuerpo': 'Cuéntanos qué comiste, con foto si quieres, para ver si vas cumpliendo tu plan.',
                'datos': {'tiempo': tiempo},
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
            aviso = r.fecha - timedelta(days=r.avisar_dias_antes)
            if aviso != fecha:
                continue
            hora = r.hora if r.hora and aviso == r.fecha else HORA_RECORDATORIO
            cuando = r.fecha.strftime('%d/%m')
            avisos.append({
                'tipo': 'recordatorio', 'clave': f'recordatorio:{r.id}:{r.fecha}',
                'programada_para': _momento(fecha, hora),
                'titulo': r.titulo[:120],
                'cuerpo': 'Es hoy.' if aviso == r.fecha else f'Es el {cuando}.',
                'recordatorio': r, 'datos': {'fecha': r.fecha.isoformat()},
            })
    return avisos


def generar(usuario, ahora=None):
    """Crea los avisos de hoy cuya hora ya llegó, desde que la persona se registró (no los
    de horas anteriores). No repite: cada clave se crea una vez."""
    ahora = ahora or timezone.now()
    fecha = timezone.localdate(ahora)
    nuevas = []
    for aviso in programados(usuario, fecha):
        if aviso['programada_para'] > ahora or aviso['programada_para'] < usuario.date_joined:
            continue
        clave = aviso.pop('clave')
        n, creada = Notificacion.objects.get_or_create(usuario=usuario, clave=clave,
                                                       defaults={**aviso, 'fecha': fecha})
        if creada:
            nuevas.append(n)
    resolver_automaticas(usuario)
    return nuevas


def resolver_automaticas(usuario):
    """Lo que ya pasó por otro lado: entrenó, completó o movió el recordatorio."""
    ahora = timezone.now()
    pendientes = Notificacion.objects.filter(usuario=usuario, resuelta_en__isnull=True,
                                             tipo__in=['entreno', 'recordatorio', 'comida', 'proceso'])
    for n in pendientes.select_related('recordatorio'):
        if n.tipo == 'entreno':
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
    if n.tipo in ('agua', 'toma', 'dormir'):
        datos = n.datos
        RegistroHabito.objects.create(
            usuario=n.usuario, tipo=n.tipo, fecha=n.fecha, momento=ahora, notificacion=n,
            cantidad=datos.get('scoops') or 1, suplemento=n.suplemento, tiempo=datos.get('tiempo', ''))
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
    return RegistroHabito.objects.create(usuario=usuario, tipo='agua', fecha=hoy)


def resumen_de_hoy(usuario):
    """Cómo va el día: vasos, tomas, entreno y la hora de dormir."""
    hoy = timezone.localdate()
    habitos = habitos_de(usuario)
    registros = RegistroHabito.objects.filter(usuario=usuario, fecha=hoy)
    hechas = {(r.suplemento_id, r.tiempo) for r in registros if r.tipo == 'toma'}
    tomas = [{'suplemento': s.id, 'nombre': s.nombre_visible, 'tiempo': t['tiempo'], 'scoops': t.get('scoops'),
              'hecha': (s.id, t['tiempo']) in hechas}
             for s in _suplementos_del_dia(usuario, hoy) for t in s.tomas]
    toca_entreno = DiaRutina.objects.filter(rutina__usuario=usuario, rutina__activa=True,
                                            dia_semana=hoy.isoweekday()).exists()
    acostado = registros.filter(tipo='dormir').first()
    return {
        'fecha': hoy,
        'agua': {'meta': vasos_meta(habitos), 'vasos': sum(r.cantidad for r in registros if r.tipo == 'agua'),
                 'ml_vaso': VASO_ML},
        'tomas': tomas,
        'entreno': {'toca': toca_entreno,
                    'hecho': RegistroEntrenamiento.objects.filter(usuario=usuario, fecha=hoy).exists()},
        'dormir': {'hora': habitos.hora_dormir, 'acostado': acostado.momento if acostado else None},
    }


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


def accion_de(notificacion):
    """Texto del botón para confirmar, o vacío si se resuelve en otra parte."""
    return {
        'agua': 'Ya lo tomé',
        'toma': 'Ya me la tomé',
        'dormir': 'Ya me acosté',
        'entreno': 'Ya entrené',
        'comida': '',
        'proceso': '',
        'recordatorio': '' if notificacion.recordatorio_id and notificacion.recordatorio.automatico else 'Listo',
    }[notificacion.tipo]


def url_de(notificacion):
    """Adónde lleva el aviso al tocarlo."""
    if notificacion.tipo == 'comida':
        return f'/comidas/contar?tiempo={notificacion.datos.get("tiempo", "")}&fecha={notificacion.fecha}'
    if notificacion.tipo == 'proceso':
        return '/control'
    return '/avisos'
