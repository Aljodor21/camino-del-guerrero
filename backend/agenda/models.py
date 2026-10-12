from django.db import models
from django.utils import timezone

from core.exceptions import DatoInmutableError
from users.models import Proceso, Usuario


class RecordatorioQuerySet(models.QuerySet):
    def pendientes(self):
        return self.filter(completado_en__isnull=True)


class Recordatorio(models.Model):
    """Fecha importante del usuario: un control con la nutricionista, una medición, etc."""

    TIPOS = [
        ('control',  'Control con profesional'),
        ('medicion',   'Medición'),
        ('suplemento', 'Suplemento'),
        ('otro',       'Otro'),
    ]
    # Los que crea la app a partir de un suplemento. Se recalculan solos.
    MOTIVOS = [
        ('confirmar', 'Confirmar duración'),
        ('reponer',   'Reponer envase'),
        ('revisar',   'Revisar al terminar'),
    ]

    usuario           = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='recordatorios')
    proceso           = models.ForeignKey(Proceso, on_delete=models.SET_NULL, null=True, blank=True,
                                          related_name='recordatorios')
    tipo              = models.CharField(max_length=20, choices=TIPOS, default='otro')
    titulo            = models.CharField(max_length=120)
    fecha             = models.DateField()
    hora              = models.TimeField(null=True, blank=True)
    nota              = models.CharField(max_length=300, blank=True)
    avisar_dias_antes = models.PositiveSmallIntegerField(default=1)
    suplemento        = models.ForeignKey('nutricion.Suplemento', on_delete=models.CASCADE, null=True, blank=True,
                                          related_name='recordatorios')
    motivo            = models.CharField(max_length=20, choices=MOTIVOS, blank=True)
    completado_en     = models.DateTimeField(null=True, blank=True)
    fecha_creacion    = models.DateTimeField(auto_now_add=True)

    objects = RecordatorioQuerySet.as_manager()

    class Meta:
        ordering = ['fecha', models.F('hora').asc(nulls_first=True), 'id']
        constraints = [
            models.CheckConstraint(condition=models.Q(avisar_dias_antes__lte=30), name='recordatorio_aviso_maximo'),
            models.UniqueConstraint(
                fields=['suplemento', 'motivo'], condition=models.Q(completado_en__isnull=True),
                name='recordatorio_sugerido_unico_pendiente',
            ),
        ]
        indexes = [models.Index(fields=['usuario', 'fecha'])]

    def __str__(self):
        return f'{self.usuario.email} - {self.titulo} ({self.fecha})'

    @property
    def automatico(self):
        return self.suplemento_id is not None


class Habitos(models.Model):
    """Lo que indicó la nutricionista para el día a día y de lo que la app avisa.

    Sin hora de dormir no hay aviso de dormir (es opcional); el agua se reparte entre
    que se levanta y se acuesta.
    """

    usuario         = models.OneToOneField(Usuario, on_delete=models.CASCADE, related_name='habitos')
    agua_ml         = models.PositiveIntegerField(null=True, blank=True, help_text='Agua indicada al día')
    vaso_ml         = models.PositiveIntegerField(default=250, help_text='De cuántos ml es el vaso (o porción) de la persona')
    hora_levantarse = models.TimeField(null=True, blank=True)
    hora_dormir     = models.TimeField(null=True, blank=True, help_text='Hora de acostarse recomendada')
    hora_entreno    = models.TimeField(null=True, blank=True)
    # Tipos de aviso que el usuario apagó (ej. ['agua']).
    avisos_apagados = models.JSONField(default=list, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(agua_ml__lte=8000), name='habitos_agua_maxima'),
            models.CheckConstraint(condition=models.Q(vaso_ml__gte=50, vaso_ml__lte=1500), name='habitos_vaso_rango'),
        ]

    def __str__(self):
        return f'Hábitos de {self.usuario.email}'


class Notificacion(models.Model):
    """Un aviso. Llega al celular y queda en la app hasta que se confirma la acción
    (o, si es de un recordatorio o del entreno, hasta que eso se resuelve)."""

    TIPOS = [
        ('agua',         'Agua'),
        ('toma',         'Toma de suplemento'),
        ('dormir',       'Dormir'),
        ('entreno',      'Entreno'),
        ('recordatorio', 'Recordatorio'),
        ('comida',       'Contar la comida'),
        ('proceso',      'Control del proceso'),
    ]

    usuario         = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='notificaciones')
    tipo            = models.CharField(max_length=20, choices=TIPOS)
    # Identifica el aviso para no crearlo dos veces (ej. 'agua:2026-10-09:3').
    clave           = models.CharField(max_length=80)
    fecha           = models.DateField(help_text='Día al que corresponde')
    programada_para = models.DateTimeField()
    titulo          = models.CharField(max_length=120)
    cuerpo          = models.CharField(max_length=300, blank=True)
    suplemento      = models.ForeignKey('nutricion.Suplemento', on_delete=models.CASCADE, null=True, blank=True,
                                        related_name='notificaciones')
    recordatorio    = models.ForeignKey(Recordatorio, on_delete=models.CASCADE, null=True, blank=True,
                                        related_name='notificaciones')
    # Datos para registrar al confirmar (ej. {'tiempo': 'onces', 'scoops': 3}).
    datos           = models.JSONField(default=dict, blank=True)
    enviada_en      = models.DateTimeField(null=True, blank=True, help_text='Cuándo se mandó al celular')
    resuelta_en     = models.DateTimeField(null=True, blank=True)
    # 'confirmada': el usuario dijo que lo hizo. 'automatica': se resolvió por otro lado
    # (entrenó con el temporizador, completó o movió el recordatorio).
    resolucion      = models.CharField(max_length=20, blank=True,
                                       choices=[('confirmada', 'Confirmada'), ('automatica', 'Automática')])

    class Meta:
        ordering = ['programada_para', 'id']
        constraints = [
            models.UniqueConstraint(fields=['usuario', 'clave'], name='notificacion_clave_unica'),
        ]
        indexes = [
            models.Index(fields=['usuario', 'resuelta_en']),
            models.Index(fields=['enviada_en', 'programada_para']),
        ]

    def __str__(self):
        return f'{self.usuario.email} - {self.titulo} ({self.programada_para:%Y-%m-%d %H:%M})'


class RegistroHabito(models.Model):
    """Lo que el usuario confirmó que hizo: un vaso de agua, una toma, la hora en que se
    acostó. Es la historia del proceso: no se edita ni se borra."""

    TIPOS = [
        ('agua',   'Vaso de agua'),
        ('toma',   'Toma de suplemento'),
        ('dormir', 'Se acostó'),
    ]

    usuario      = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='registros_habito')
    tipo         = models.CharField(max_length=20, choices=TIPOS)
    fecha        = models.DateField(default=timezone.localdate)
    momento      = models.DateTimeField(default=timezone.now)
    cantidad     = models.DecimalField(max_digits=5, decimal_places=1, default=1,
                                       help_text='Vasos o scoops')
    ml           = models.PositiveIntegerField(null=True, blank=True,
                                               help_text='Tamaño del vaso en ese momento (solo agua)')
    suplemento   = models.ForeignKey('nutricion.Suplemento', on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='registros')
    tiempo       = models.CharField(max_length=20, blank=True, help_text='Comida de la toma')
    notificacion = models.OneToOneField(Notificacion, on_delete=models.SET_NULL, null=True, blank=True,
                                        related_name='registro')

    class Meta:
        ordering = ['-momento']
        indexes = [models.Index(fields=['usuario', 'tipo', 'fecha'])]

    def __str__(self):
        return f'{self.usuario.email} - {self.get_tipo_display()} ({self.fecha})'

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise DatoInmutableError('Un registro no se puede modificar.')
        super().save(*args, **kwargs)


class SuscripcionPush(models.Model):
    """Un navegador o celular del usuario que acepta notificaciones."""

    usuario        = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='suscripciones_push')
    endpoint       = models.URLField(max_length=600, unique=True)
    p256dh         = models.CharField(max_length=200)
    auth           = models.CharField(max_length=100)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.usuario.email} - {self.endpoint[:40]}'


class TokenCelular(models.Model):
    """Un celular con la app instalada que puede recibir avisos por Firebase (FCM)."""

    usuario        = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='tokens_celular')
    token          = models.CharField(max_length=400, unique=True)
    dispositivo    = models.CharField(max_length=80, blank=True)
    version_app    = models.CharField(max_length=20, blank=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    ultimo_uso     = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f'{self.usuario.email} - {self.dispositivo or "celular"}'
