"""Catálogo de programas: un proceso ya armado según una fuente (un libro y su autor), con sus proyectos.

Los programas son solo los que se registran aquí: la persona elige uno y le llega con sus proyectos. Agregar un
programa es agregar una entrada en `PROGRAMAS`; agregar una actividad a un programa es agregar un `ProyectoBase`
con un tipo ya registrado en `tipos.py`. Cada proyecto lleva una `clave` estable dentro del programa.
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
        descripcion='El taller de creencias del capítulo 1 y el diario de gastos del capítulo 2.',
        proyectos=(
            ProyectoBase('taller_creencias', 'taller_creencias', 'Taller de creencias', 'Capítulo 1'),
            ProyectoBase('diario_gastos', 'diario_gastos', 'Diario de gastos', 'Capítulo 2 · Paso 1'),
        ),
    ),
}


PROGRAMAS['salud_protocolo'] = Programa(
    titulo='Protocolo y suplementos',
    fuente='propio',
    fuente_titulo='Protocolo Fadiman',
    autor='James Fadiman',
    area='Salud',
    descripcion='El calendario del protocolo Fadiman de microdosis, con sus días y su descanso, y el control '
                'de los otros suplementos que tomas.',
    proyectos=(
        ProyectoBase('fadiman', 'fadiman', 'Protocolo Fadiman', 'Ciclo de 4 días · 4 a 8 semanas'),
        ProyectoBase('otros_suplementos', 'otros_suplementos', 'Otros suplementos', 'Lo que tomas además'),
    ),
)
