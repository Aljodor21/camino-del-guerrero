"""Minuta del proceso: la que da la nutricionista o la que calcula la IA."""
from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from core.exceptions import ReglaNegocioError
from users.procesos import proceso_de_referencia

from .grupos import GRUPOS, TIEMPOS
from .models import Minuta

MAX_PORCIONES = Decimal(30)
PASO = Decimal('0.5')


def lunes(fecha):
    return fecha - timedelta(days=fecha.weekday())


def proceso_con_alimentacion(usuario, proceso_id=None):
    """El proceso al que va la minuta: el indicado (ej. uno programado recién creado) o el de referencia."""
    proceso = usuario.procesos.filter(pk=proceso_id).first() if proceso_id else proceso_de_referencia(usuario)
    if not proceso or not proceso.incluye_alimentacion:
        raise ReglaNegocioError('Tu proceso no incluye alimentación.')
    return proceso


def vigente(proceso):
    """La última minuta guardada del proceso: la que manda en el menú."""
    if proceso is None:
        return None
    return proceso.minutas.first()


def vigente_de(usuario):
    return vigente(proceso_de_referencia(usuario))


def normalizar_porciones(porciones):
    """Valida la minuta ({grupo: {tiempo: n, 'dia': n}}) y la deja con el total del día.

    El total del día es al menos la suma de las comidas; lo que sobra se come cuando
    se quiera (como el agua).
    """
    grupos, tiempos = dict(GRUPOS), dict(TIEMPOS)
    if not isinstance(porciones, dict):
        raise ReglaNegocioError('La minuta no tiene el formato esperado.')
    limpio = {}
    for grupo, fila in porciones.items():
        if grupo not in grupos or not isinstance(fila, dict):
            raise ReglaNegocioError(f'"{grupo}" no es un grupo de la minuta.')
        valores = {}
        for clave, valor in fila.items():
            if clave != 'dia' and clave not in tiempos:
                raise ReglaNegocioError(f'"{clave}" no es una comida de la minuta.')
            try:
                numero = Decimal(str(valor or 0))
            except ArithmeticError:
                raise ReglaNegocioError('Las porciones deben ser números.')
            if numero < 0 or numero > MAX_PORCIONES or numero % PASO:
                raise ReglaNegocioError('Las porciones van de media en media, hasta 30.')
            valores[clave] = numero
        en_comidas = sum((v for k, v in valores.items() if k != 'dia'), Decimal(0))
        dia = max(valores.get('dia', Decimal(0)), en_comidas)
        if dia:
            limpio[grupo] = {**{k: float(v) for k, v in valores.items() if k != 'dia' and v}, 'dia': float(dia)}
    if not any(len(fila) > 1 for g, fila in limpio.items() if g != 'agua'):
        raise ReglaNegocioError('La minuta debe tener porciones en al menos una comida.')
    return limpio


@transaction.atomic
def crear(usuario, datos, archivo=None):
    proceso = proceso_con_alimentacion(usuario, datos.get('proceso'))
    if proceso.estado == 'finalizado':
        raise ReglaNegocioError('Tu proceso ya terminó.')
    habia_plan = proceso.minutas.exists()
    minuta = Minuta.objects.create(
        usuario=usuario, proceso=proceso, origen=datos['origen'],
        archivo=archivo or '', porciones=normalizar_porciones(datos['porciones']),
        kcal=datos.get('kcal'), proteina_g_kg=datos.get('proteina_g_kg'),
        menu_ejemplo=datos.get('menu_ejemplo') or {}, recomendaciones=datos.get('recomendaciones', ''),
    )
    # Los menús desde esta semana salían de la minuta anterior: se vuelven a armar.
    usuario.menus.filter(semana__gte=lunes(timezone.localdate())).delete()
    # Un plan nuevo puede traer su propio periodo: el mismo del proceso, otro o ninguno.
    if habia_plan and 'fecha_fin_plan' in datos:
        from users.procesos import renovar
        renovar(proceso, datos['fecha_fin_plan'], con_plan_nuevo=True)
    return minuta
