"""Recordatorios que la app sugiere a partir de los suplementos del proceso.

Cada suplemento tiene como máximo un recordatorio pendiente por motivo. Se
recalculan cada vez que el suplemento cambia: si la fecha calculada se mueve,
el pendiente se mueve con ella; si ya no aplica, se borra. Se resuelven con las
acciones del suplemento (confirmar, abrir envase, decidir qué sigue), que dejan
el resuelto como historial.
"""
from django.utils import timezone

from .models import Recordatorio

AVISO = {'confirmar': 0, 'reponer': 5, 'revisar': 7}


def _duracion_en_palabras(dias):
    if dias % 30 == 0:
        meses = dias // 30
        return '1 mes' if meses == 1 else f'{meses} meses'
    if dias % 7 == 0:
        semanas = dias // 7
        return '1 semana' if semanas == 1 else f'{semanas} semanas'
    return f'{dias} días'


def _sugeridos(suplemento):
    """Los recordatorios que deberían estar pendientes hoy: {motivo: (fecha, titulo, nota)}."""
    if suplemento.fecha_fin:
        return {}

    hoy = timezone.localdate()
    nombre = suplemento.nombre_visible
    fin = suplemento.fin_estimado
    sugeridos = {}

    if not suplemento.duracion_confirmada:
        if suplemento.duracion_dias:
            duracion = _duracion_en_palabras(suplemento.duracion_dias)
            titulo, supuesto = f'Confirma si {nombre} va {duracion}', duracion
        else:
            titulo, supuesto = f'Confirma si {nombre} va todo el proceso', 'que va todo el proceso'
        sugeridos['confirmar'] = (
            max(hoy, suplemento.fecha_inicio),
            titulo,
            f'Asumimos {supuesto}. Corrígelo si tu profesional te indicó otra cosa.',
        )

    se_acaba = suplemento.se_acaba
    if se_acaba and (fin is None or se_acaba < fin):
        sugeridos['reponer'] = (
            se_acaba,
            f'Se acaba {nombre}',
            'Compra el siguiente con tiempo para no cortar la toma.',
        )

    if suplemento.duracion_dias:
        duracion = _duracion_en_palabras(suplemento.duracion_dias)
        sugeridos['revisar'] = (
            fin,
            f'Terminan los {duracion} de {nombre}: ¿qué sigue?',
            'Define si continúas, cambias de producto o lo dejas.',
        )
    return sugeridos


def sincronizar(suplemento):
    pendientes = {r.motivo: r for r in suplemento.recordatorios.filter(completado_en__isnull=True)}
    sugeridos = _sugeridos(suplemento)

    for motivo, recordatorio in pendientes.items():
        if motivo not in sugeridos:
            recordatorio.delete()

    for motivo, (fecha, titulo, nota) in sugeridos.items():
        Recordatorio.objects.update_or_create(
            suplemento=suplemento, motivo=motivo, completado_en=None,
            defaults={
                'usuario': suplemento.usuario, 'proceso': suplemento.proceso, 'tipo': 'suplemento',
                'fecha': fecha, 'titulo': titulo, 'nota': nota, 'avisar_dias_antes': AVISO[motivo],
            },
        )


def resolver(suplemento, motivo):
    """Marca como hecho el pendiente de ese motivo, si lo hay."""
    suplemento.recordatorios.filter(motivo=motivo, completado_en__isnull=True).update(
        completado_en=timezone.now())
