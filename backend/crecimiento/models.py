"""Crecimiento personal: lo que cada persona quiere trabajar además del cuerpo y la comida.

Cada persona arma sus propias **áreas** (por ejemplo «Educación financiera»); dentro de cada área lleva
**procesos** que salen de una fuente (un libro y su autor, un curso, un mentor o algo propio) y cada proceso
tiene **proyectos** (los ejercicios de cada capítulo). Cada proyecto puede dejar **notas**.

Los proyectos siguen un estándar (ver `tipos.py`) para que la app principal pueda traer su avance y sus notas
sin saber cómo funciona cada uno por dentro.
"""
from django.db import models
from django.utils import timezone

from users.models import Usuario


class Area(models.Model):
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='areas_crecimiento')
    nombre  = models.CharField(max_length=80)
    icono   = models.CharField(max_length=40, default='pi pi-compass', blank=True)
    orden   = models.PositiveSmallIntegerField(default=0)
    creada  = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['orden', 'id']
        constraints = [models.UniqueConstraint(fields=['usuario', 'nombre'], name='area_unica_por_usuario')]

    def __str__(self):
        return f'{self.nombre} ({self.usuario.email})'


class Proceso(models.Model):
    """Un camino dentro de un área, con su fuente: «según este libro / este autor / este curso»."""

    FUENTES = [('libro', 'Libro'), ('curso', 'Curso'), ('mentor', 'Mentor'), ('propio', 'Propio')]
    ESTADOS = [('en_curso', 'En curso'), ('pausado', 'Pausado'), ('terminado', 'Terminado')]

    area         = models.ForeignKey(Area, on_delete=models.CASCADE, related_name='procesos')
    titulo       = models.CharField(max_length=140)
    fuente       = models.CharField(max_length=10, choices=FUENTES, default='libro')
    fuente_titulo = models.CharField(max_length=160, blank=True, help_text='El libro, el curso o el mentor')
    autor        = models.CharField(max_length=120, blank=True)
    nota         = models.CharField(max_length=300, blank=True)
    estado       = models.CharField(max_length=10, choices=ESTADOS, default='en_curso')
    fecha_inicio = models.DateField(default=timezone.localdate)
    fecha_fin    = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ['fecha_inicio', 'id']

    def __str__(self):
        return self.titulo


class Proyecto(models.Model):
    """Un ejercicio dentro de un proceso (el taller de un capítulo, un diario, un presupuesto...).

    `tipo` dice cómo es: `libre` es el básico (título y notas); cada tipo nuevo se registra en `tipos.py`.
    `datos` es lo propio de cada tipo y solo ese tipo lo interpreta."""

    ESTADOS = [('por_empezar', 'Por empezar'), ('en_curso', 'En curso'), ('terminado', 'Terminado')]

    proceso    = models.ForeignKey(Proceso, on_delete=models.CASCADE, related_name='proyectos')
    tipo       = models.CharField(max_length=40, default='libre')
    titulo     = models.CharField(max_length=140)
    detalle    = models.CharField(max_length=300, blank=True, help_text='Por ejemplo, «Capítulo 2 · Paso 1»')
    orden      = models.PositiveSmallIntegerField(default=0)
    estado     = models.CharField(max_length=12, choices=ESTADOS, default='por_empezar')
    avance     = models.PositiveSmallIntegerField(default=0, help_text='De 0 a 100')
    datos      = models.JSONField(default=dict, blank=True)
    actualizado = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['orden', 'id']
        constraints = [models.CheckConstraint(condition=models.Q(avance__lte=100), name='proyecto_avance_maximo')]

    def __str__(self):
        return self.titulo


class Nota(models.Model):
    """Lo que la persona quiere recordar de un proyecto; es lo que la app principal puede traer."""

    proyecto = models.ForeignKey(Proyecto, on_delete=models.CASCADE, related_name='notas')
    titulo   = models.CharField(max_length=140, blank=True)
    texto    = models.TextField(max_length=2000)
    fecha    = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-fecha', '-id']

    def __str__(self):
        return self.titulo or self.texto[:40]
