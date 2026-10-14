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
