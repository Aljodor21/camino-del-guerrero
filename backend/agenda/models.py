from django.db import models
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
