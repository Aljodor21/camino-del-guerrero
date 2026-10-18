"""La forma de un tipo de proyecto (ver `tipos.py`)."""
from dataclasses import dataclass, field
from datetime import date
from typing import Callable, Optional


def _sin_ajustes(datos):
    return {}


@dataclass(frozen=True)
class Tipo:
    nombre: str
    valida: Callable[[dict], dict] = _sin_ajustes
    avance: Optional[Callable[[object], int]] = None
    resumen: Callable[[object], str] = field(default=lambda proyecto: '')
    avisos: Callable[[object, date], list] = field(default=lambda proyecto, fecha: [])
    confirmar: Optional[Callable[[object, str, date], None]] = None
    resuelto: Callable[[object, str, date], bool] = field(default=lambda proyecto, clave, fecha: False)
    # Las llaves de `datos` que solo cambia el servidor (por ejemplo, los días ya cumplidos): lo que mande la app
    # en ellas se ignora.
    del_servidor: tuple = ()
    # Lo que la persona puede hacer desde la pantalla del proyecto: {nombre: función(proyecto, fecha)}.
    acciones: dict = field(default_factory=dict)
    # Si tiene sentido un porcentaje de avance (un registro que no se termina, como los suplementos, no lo
    # tiene): sin él no se muestra ni cuenta en el avance del área.
    con_avance: bool = True
