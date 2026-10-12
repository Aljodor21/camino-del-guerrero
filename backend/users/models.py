from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone

from core.exceptions import DatoInmutableError


class Rol(models.Model):
    nombre = models.CharField(max_length=50, unique=True)
    descripcion = models.CharField(max_length=200, blank=True)

    def __str__(self):
        return self.nombre


class Sexo(models.Model):
    nombre = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.nombre


class Usuario(AbstractUser):
    FRECUENCIA_CHOICES = [(15, '15 días'), (30, '1 mes')]

    email                    = models.EmailField(unique=True)
    nombre                   = models.CharField(max_length=150)
    rol                      = models.ForeignKey(Rol,  on_delete=models.PROTECT, null=True, blank=True, related_name='usuarios')
    sexo                     = models.ForeignKey(Sexo, on_delete=models.SET_NULL, null=True, blank=True, related_name='usuarios')
    fecha_nacimiento         = models.DateField(null=True, blank=True)
    estatura                 = models.PositiveIntegerField(null=True, blank=True, help_text='Estatura en centímetros')
    frecuencia_peso          = models.IntegerField(default=30, choices=FRECUENCIA_CHOICES)
    nacionalidad             = models.CharField(max_length=100, blank=True, help_text='País de origen para personalizar recetas')
    region                   = models.CharField(max_length=150, blank=True, help_text='Región, departamento o ciudad para personalizar recetas')
    preferencias_alimentarias= models.CharField(max_length=300, blank=True, help_text='Restricciones o preferencias dietarias')
    implementos_adicionales  = models.CharField(max_length=300, blank=True, help_text='Implementos extra que tiene el usuario fuera del listado del admin')

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'nombre']

    def __str__(self):
        return self.email


class ProcesoQuerySet(models.QuerySet):
    def en_curso(self, hoy=None):
        hoy = hoy or timezone.localdate()
        return self.filter(fecha_inicio__lte=hoy).filter(
            models.Q(fecha_fin__isnull=True) | models.Q(fecha_fin__gte=hoy)
        )

    def programados(self, hoy=None):
        return self.filter(fecha_inicio__gt=hoy or timezone.localdate())


class Proceso(models.Model):
    """Etapa del usuario con un objetivo concreto (ej. volumen con hipercalórico).

    Alimentación y entrenamiento son módulos opcionales del proceso. El objetivo,
    la fase, la fecha de inicio y la medición inicial son datos sagrados: se fijan
    una sola vez y nunca se modifican (ver `save`).
    """

    OBJETIVOS = [
        ('bajar_peso',   'Bajar peso'),
        ('ganar_musculo','Ganar músculo'),
        ('mantener',     'Mantener peso'),
        ('resistencia',  'Mejorar resistencia'),
    ]
    FASES = [
        ('volumen',       'Volumen'),
        ('definicion',    'Definición'),
        ('mantenimiento', 'Mantenimiento'),
    ]
    ESTADOS = [
        ('programado', 'Programado'),
        ('en_curso',   'En curso'),
        ('finalizado', 'Finalizado'),
    ]
    CAMPOS_SAGRADOS = ('usuario_id', 'objetivo', 'fase', 'fecha_inicio')

    usuario               = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='procesos')
    objetivo              = models.CharField(max_length=50, choices=OBJETIVOS)
    fase                  = models.CharField(max_length=20, choices=FASES, blank=True)
    peso_objetivo         = models.FloatField(null=True, blank=True)
    incluye_alimentacion  = models.BooleanField(default=True)
    incluye_entrenamiento = models.BooleanField(default=False)
    fecha_inicio          = models.DateField(default=timezone.localdate)
    fecha_fin             = models.DateField(null=True, blank=True)
    # Hasta cuándo está pensado el proceso (ej. hasta el control con la nutricionista).
    # Es un plan, no un dato de inicio: se puede ajustar mientras el proceso no termine.
    fecha_fin_plan        = models.DateField(null=True, blank=True)
    # Fechas meta anteriores, cuando al llegar el control se siguió con otro periodo:
    # [{'hasta': '2026-12-01', 'cambiada_el': '2026-12-01'}]
    renovaciones          = models.JSONField(default=list, blank=True)
    medicion_inicial      = models.OneToOneField(
        'progress.Medicion', on_delete=models.PROTECT, null=True, blank=True,
        related_name='proceso_iniciado',
    )
    notas                 = models.TextField(blank=True)
    fecha_creacion        = models.DateTimeField(auto_now_add=True)

    objects = ProcesoQuerySet.as_manager()

    class Meta:
        ordering = ['-fecha_inicio', '-id']
        constraints = [
            models.UniqueConstraint(
                fields=['usuario'], condition=models.Q(fecha_fin__isnull=True),
                name='proceso_unico_abierto_por_usuario',
            ),
            models.CheckConstraint(
                condition=models.Q(incluye_alimentacion=True) | models.Q(incluye_entrenamiento=True),
                name='proceso_con_algun_modulo',
            ),
            models.CheckConstraint(
                condition=models.Q(fecha_fin__isnull=True) | models.Q(fecha_fin__gte=models.F('fecha_inicio')),
                name='proceso_fechas_coherentes',
            ),
            models.CheckConstraint(
                condition=models.Q(fecha_fin_plan__isnull=True) | models.Q(fecha_fin_plan__gt=models.F('fecha_inicio')),
                name='proceso_plan_despues_del_inicio',
            ),
        ]

    def __str__(self):
        return f'{self.usuario.email} - {self.get_objetivo_display()} ({self.fecha_inicio})'

    @property
    def estado(self):
        hoy = timezone.localdate()
        if self.fecha_inicio > hoy:
            return 'programado'
        if self.fecha_fin and self.fecha_fin < hoy:
            return 'finalizado'
        return 'en_curso'

    def save(self, *args, **kwargs):
        if not self._state.adding:
            self._verificar_datos_sagrados()
        super().save(*args, **kwargs)

    def _verificar_datos_sagrados(self):
        original = (Proceso.objects.filter(pk=self.pk)
                    .values(*self.CAMPOS_SAGRADOS, 'medicion_inicial_id').first())
        if original is None:
            return
        cambiados = [c for c in self.CAMPOS_SAGRADOS if getattr(self, c) != original[c]]
        if original['medicion_inicial_id'] and self.medicion_inicial_id != original['medicion_inicial_id']:
            cambiados.append('medicion_inicial')
        if cambiados:
            raise DatoInmutableError(f'Datos sagrados del proceso no modificables: {", ".join(cambiados)}')


class ConfiguracionEntrenamiento(models.Model):
    """Módulo de entrenamiento de un proceso: lo que la IA necesita para la rutina."""

    NIVEL_CHOICES = [
        ('principiante', 'Principiante'),
        ('intermedio',   'Intermedio'),
        ('avanzado',     'Avanzado'),
    ]
    DIAS_CHOICES     = [(3, '3 días'), (4, '4 días'), (5, '5 días')]
    DURACION_CHOICES = [(30, '30 min'), (45, '45 min'), (60, '60 min')]
    ENFOQUE_CHOICES  = [
        ('boxeo',       'Boxeo'),
        ('cardio_casa', 'Cardio en casa'),
        ('funcional',   'Funcional / HIIT'),
        ('fuerza',      'Fuerza'),
        ('movilidad',   'Yoga / Movilidad'),
    ]

    proceso               = models.OneToOneField(Proceso, on_delete=models.CASCADE, related_name='entrenamiento')
    nivel_actividad       = models.CharField(max_length=20, choices=NIVEL_CHOICES, default='principiante')
    dias_entrenamiento    = models.IntegerField(choices=DIAS_CHOICES, default=3)
    duracion_sesion       = models.IntegerField(choices=DURACION_CHOICES, default=45)
    enfoque_entrenamiento = models.CharField(max_length=30, choices=ENFOQUE_CHOICES, default='boxeo')

    def __str__(self):
        return f'Entrenamiento de {self.proceso}'


class SolicitudRecuperacion(models.Model):
    """Un enlace para crear una clave nueva. Sirve una sola vez, caduca y solo se puede abrir
    desde el navegador donde se pidió. Se guarda el hash, nunca el enlace."""
    usuario          = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='solicitudes_recuperacion')
    token_hash       = models.CharField(max_length=64, unique=True)
    dispositivo_hash = models.CharField(max_length=64)
    creada           = models.DateTimeField(default=timezone.now)
    usada_en         = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=['usuario', 'usada_en'])]
