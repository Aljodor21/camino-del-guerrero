"""Los avisos de los proyectos de crecimiento, con el mismo camino que los demás avisos de la app.

`agenda.notificaciones` los pide aquí (`programados`) y, cuando la persona toca la acción o el aviso deja de hacer
falta, vuelve aquí (`confirmar`, `resuelto`). Cada tipo de proyecto dice sus avisos en su estándar (`tipos.py`).
"""
from datetime import datetime

from django.utils import timezone

from core.exceptions import ReglaNegocioError

from .models import Proyecto
from .tipos import TIPOS


def _proyectos_activos(usuario):
    return (Proyecto.objects.filter(proceso__area__usuario=usuario, proceso__estado='en_curso')
            .select_related('proceso'))


def programados(usuario, fecha):
    """Los avisos de ese día de todos los proyectos en curso, en la forma de `agenda.notificaciones`."""
    avisos = []
    for proyecto in _proyectos_activos(usuario):
        tipo = TIPOS.get(proyecto.tipo)
        if tipo is None:
            continue
        for a in tipo.avisos(proyecto, fecha):
            avisos.append({
                'tipo': 'crecimiento', 'clave': f'crecimiento:{proyecto.id}:{a["clave"]}:{fecha}',
                'programada_para': timezone.make_aware(datetime.combine(fecha, a['hora'])),
                'titulo': a['titulo'][:120], 'cuerpo': a.get('cuerpo', '')[:300],
                'datos': {'proyecto': proyecto.id, 'aviso': a['clave'], 'accion': a.get('accion', '')},
            })
    return avisos


def _proyecto_de(notificacion):
    return (Proyecto.objects.filter(pk=notificacion.datos.get('proyecto'),
                                    proceso__area__usuario=notificacion.usuario).first())


def confirmar(notificacion):
    """La persona tocó la acción del aviso: el tipo guarda lo que corresponde."""
    proyecto = _proyecto_de(notificacion)
    tipo = TIPOS.get(proyecto.tipo) if proyecto else None
    if tipo is None or tipo.confirmar is None or not notificacion.datos.get('accion'):
        raise ReglaNegocioError('Este aviso se resuelve desde su proyecto, en Crecimiento.')
    tipo.confirmar(proyecto, notificacion.datos.get('aviso', ''), notificacion.fecha)


def resuelto(notificacion):
    proyecto = _proyecto_de(notificacion)
    tipo = TIPOS.get(proyecto.tipo) if proyecto else None
    if tipo is None or proyecto.proceso.estado != 'en_curso':
        return True
    return tipo.resuelto(proyecto, notificacion.datos.get('aviso', ''), notificacion.fecha)
