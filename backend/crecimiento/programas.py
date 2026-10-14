"""Catálogo de programas: un proceso ya armado según una fuente (un libro y su autor), con sus proyectos.

Agregar un programa es agregar una entrada en `PROGRAMAS`. Cada proyecto lleva una `clave` estable dentro del
programa; si todavía no tiene pantalla propia va como `libre` y, cuando la tenga, los que ya existen se pasan a
su tipo por esa clave.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class ProyectoBase:
    clave: str
    tipo: str
    titulo: str
    detalle: str = ''


@dataclass(frozen=True)
class Programa:
    titulo: str
    fuente: str
    fuente_titulo: str
    autor: str
    area: str
    descripcion: str
    proyectos: tuple


PROGRAMAS = {
    'sana_tus_finanzas': Programa(
        titulo='Sana tus finanzas',
        fuente='libro',
        fuente_titulo='Sana tus finanzas, transforma tu vida',
        autor='Jaime Jaramillo',
        area='Educación financiera',
        descripcion='Los ejercicios del libro, capítulo por capítulo.',
        proyectos=(
            ProyectoBase('taller_creencias', 'libre', 'Taller de creencias', 'Capítulo 1'),
            ProyectoBase('vision_futuro', 'libre', 'Mi visión a futuro', 'Ejercicio del libro'),
            ProyectoBase('diario_gastos', 'diario_gastos', 'Diario de gastos', 'Capítulo 2 · Paso 1'),
            ProyectoBase('presupuesto', 'libre', 'Presupuesto personal', 'Capítulo 2'),
            ProyectoBase('mapa_suenos', 'libre', 'Mapa de sueños', 'Capítulo 2'),
            ProyectoBase('bola_nieve', 'libre', 'Bola de nieve: pagar deudas', 'Capítulo 2'),
        ),
    ),
}
