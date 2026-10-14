"""El estándar de un proyecto de crecimiento personal.

Cada **tipo** de proyecto (el taller de creencias, el diario de gastos, el presupuesto, el mapa de sueños, la
bola de nieve...) se registra aquí con lo mínimo que la app principal necesita saber:

- `nombre`: cómo se llama para la persona.
- `valida(datos)`: revisa lo propio del tipo (`Proyecto.datos`) y lo devuelve limpio; levanta
  `ReglaNegocioError` si no sirve.
- `avance(datos)`: de 0 a 100, qué tanto va (el proyecto no se lo inventa: sale de lo que la persona hizo).
- `resumen(datos)`: una frase corta con lo más importante hoy («3 de 21 días leídos»), para mostrarla fuera
  del proyecto.

Lo demás (pantallas, cálculos) vive en el propio proyecto. Un tipo nuevo es una entrada más en `TIPOS`: no
cambia el resto de la app.
"""
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class Tipo:
    nombre: str
    valida: Callable[[dict], dict]
    avance: Callable[[dict], int]
    resumen: Callable[[dict], str]


def _libre_valida(datos):
    return {}


TIPOS = {
    # El básico: un título y sus notas; el avance lo marca la persona.
    'libre': Tipo(nombre='Libre', valida=_libre_valida, avance=lambda datos: 0, resumen=lambda datos: ''),
}
