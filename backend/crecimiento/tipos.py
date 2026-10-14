"""El estándar de un tipo de proyecto de crecimiento personal.

Cada tipo (el diario de gastos, y luego el taller de creencias, el presupuesto, el mapa de sueños, la bola de
nieve…) se registra en `TIPOS` con lo que el resto de la app necesita saber de él, y nada más:

- `nombre`: cómo se llama para la persona.
- `valida(datos)`: revisa sus ajustes propios (`Proyecto.datos`) y los devuelve limpios, o levanta
  `ReglaNegocioError`.
- `avance(proyecto)`: de 0 a 100, qué tanto va, calculado de lo que la persona hizo; `None` si el tipo no lo
  calcula y lo marca ella.
- `resumen(proyecto)`: una frase corta con lo más importante hoy («Octubre: $120.000 anotados»).
- `avisos(proyecto, fecha)`: los avisos de ese día, `[{'clave', 'hora', 'titulo', 'cuerpo', 'accion'}]`. Llegan
  a la bandeja y al celular como cualquier otro aviso (`crecimiento/avisos.py` los pasa a `agenda`).
- `confirmar(proyecto, clave, fecha)`: lo que se guarda cuando la persona toca la acción del aviso.
- `resuelto(proyecto, clave, fecha)`: si el aviso ya no hace falta (porque la persona lo hizo por otro lado).
- `del_servidor`: llaves de `datos` que la app no puede cambiar (lo cumplido no se escribe a mano).
- `acciones`: lo que se hace desde la pantalla (`POST /proyectos/<id>/accion/<nombre>/`).

Lo demás (pantallas, cálculos, sus propias tablas) vive en el módulo del tipo. Un tipo nuevo es una entrada
más en `TIPOS`: no cambia el resto de la app.
"""
from .tipos_base import Tipo


def _registrar():
    from . import creencias, diario
    return {
        # El básico: título y notas; el avance lo marca la persona.
        'libre': Tipo(nombre='Libre'),
        'taller_creencias': creencias.TIPO,
        'diario_gastos': diario.TIPO,
    }


TIPOS = _registrar()
