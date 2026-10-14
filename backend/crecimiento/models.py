"""Crecimiento personal: lo que cada persona quiere trabajar además del cuerpo y la comida.

Cada persona arma sus propias **áreas** (por ejemplo «Educación financiera»); dentro de cada área lleva
**procesos** que salen de una fuente (un libro y su autor, un curso, un mentor o algo propio) y cada proceso
tiene **proyectos** (los ejercicios de cada capítulo). Cada proyecto puede dejar **notas**.

Todo sigue un estándar: un programa del catálogo (`programas.py`) trae su fuente y sus proyectos ya puestos, y
cada tipo de proyecto (`tipos.py`) dice su avance, su frase de resumen y sus avisos, que llegan a la bandeja y al
celular como los demás avisos de la app.
"""
from core.exceptions import DatoInmutableError
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
    # El programa del catálogo del que salió (`programas.py`), o vacío si lo armó la persona.
    programa     = models.CharField(max_length=40, blank=True)
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
    # Cuál de los proyectos del programa es (`programas.py`); así, cuando ese proyecto tenga su propio tipo,
    # los que ya existen se pueden pasar a él.
    clave      = models.CharField(max_length=40, blank=True)
    titulo     = models.CharField(max_length=140)
    detalle    = models.CharField(max_length=300, blank=True, help_text='Por ejemplo, «Capítulo 2 · Paso 1»')
    orden      = models.PositiveSmallIntegerField(default=0)
    estado     = models.CharField(max_length=12, choices=ESTADOS, default='por_empezar')
    avance     = models.PositiveSmallIntegerField(default=0, help_text='De 0 a 100')
    datos      = models.JSONField(default=dict, blank=True)
    creado     = models.DateField(default=timezone.localdate)
    actualizado = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['orden', 'id']
        constraints = [
            models.CheckConstraint(condition=models.Q(avance__lte=100), name='proyecto_avance_maximo'),
            models.UniqueConstraint(fields=['proceso', 'clave'], condition=~models.Q(clave=''),
                                    name='proyecto_clave_unica_en_proceso'),
        ]

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


# ── Diario de gastos ────────────────────────────────────────────────────────────
# Cerebral: si no se hace, pasa algo grave (indispensable). Emocional: se hace por gusto.
CLASES_GASTO = [('cerebral', 'Cerebral'), ('emocional', 'Emocional')]


class Rubro(models.Model):
    """Una línea del diario de gastos, como en el ejercicio: categoría, rubro, valor y cuánto es cerebral (lo
    demás es emocional; así un gasto mixto se parte). Cada rubro dice cada cuánto se paga: lo anual se divide
    entre 12 y lo hormiga (de todos los días) se multiplica por los días del mes, y todo se suma al mes."""

    FRECUENCIAS = [('mensual', 'Cada mes'), ('anual', 'Una vez al año'), ('semestral', 'Dos veces al año'),
                   ('hormiga', 'Todos los días')]

    proyecto   = models.ForeignKey(Proyecto, on_delete=models.CASCADE, related_name='rubros')
    categoria  = models.CharField(max_length=20)
    nombre     = models.CharField(max_length=80)
    frecuencia = models.CharField(max_length=10, choices=FRECUENCIAS, default='mensual')
    # Lo que vale cada pago (o cada día, si es hormiga) y cuánto de eso es cerebral.
    valor      = models.PositiveBigIntegerField(default=0)
    cerebral   = models.PositiveBigIntegerField(default=0)
    dias_mes   = models.PositiveSmallIntegerField(default=30, help_text='Solo para los gastos hormiga')
    mes_pago   = models.PositiveSmallIntegerField(null=True, blank=True, help_text='Mes del pago (anual/semestral)')
    orden      = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['orden', 'id']
        constraints = [
            models.CheckConstraint(condition=models.Q(cerebral__lte=models.F('valor')),
                                   name='rubro_cerebral_no_pasa_del_valor'),
            models.CheckConstraint(condition=models.Q(dias_mes__gte=1, dias_mes__lte=31), name='rubro_dias_validos'),
        ]


class Gasto(models.Model):
    """Lo que se gastó de verdad, el día que pasó: el diario sincero. No se edita; solo se puede borrar el
    mismo día que se anotó (por si fue un error)."""

    proyecto    = models.ForeignKey(Proyecto, on_delete=models.CASCADE, related_name='gastos')
    fecha       = models.DateField(default=timezone.localdate)
    valor       = models.PositiveBigIntegerField()
    descripcion = models.CharField(max_length=120)
    categoria   = models.CharField(max_length=20)
    clase       = models.CharField(max_length=10, choices=CLASES_GASTO)
    anotado     = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-fecha', '-anotado', '-id']
        indexes = [models.Index(fields=['proyecto', 'fecha'])]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise DatoInmutableError('Un gasto anotado no se cambia.')
        super().save(*args, **kwargs)


class DiaSinGasto(models.Model):
    """La persona dijo que ese día no gastó nada: también cuenta como día al día."""

    proyecto = models.ForeignKey(Proyecto, on_delete=models.CASCADE, related_name='dias_sin_gasto')
    fecha    = models.DateField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=['proyecto', 'fecha'], name='dia_sin_gasto_unico')]
