from django.db import models
from django.utils import timezone

from core.exceptions import DatoInmutableError
from users.models import Usuario


class Evento(models.Model):
    """Una huella de uso: qué consultó alguien, cuándo y desde qué dispositivo.

    Solo guarda quién, qué ruta, el resultado y el dispositivo; nunca el contenido de lo que
    se envía (fotos, medidas, claves). No se edita: se borra solo con el paso del tiempo
    (`limpiar_auditoria`).
    """

    TIPOS = [
        ('api', 'Consulta al servidor'),
        ('pantalla', 'Pantalla abierta'),
    ]
    CLIENTES = [('app', 'App instalada'), ('web', 'Navegador')]

    usuario     = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True, blank=True, related_name='eventos')
    # Se guarda aparte para que la huella siga diciendo quién fue aunque se borre la cuenta.
    correo      = models.CharField(max_length=254, blank=True)
    momento     = models.DateTimeField(default=timezone.now)
    tipo        = models.CharField(max_length=10, choices=TIPOS, default='api')
    metodo      = models.CharField(max_length=8, blank=True)
    # La ruta con su forma ("api/agenda/avisos/<int:pk>/confirmar/") para poder agrupar.
    ruta        = models.CharField(max_length=200)
    # La ruta tal cual se pidió ("/api/agenda/avisos/12/confirmar/").
    camino      = models.CharField(max_length=300, blank=True)
    consulta    = models.CharField(max_length=300, blank=True)
    estado      = models.PositiveSmallIntegerField(null=True, blank=True)
    duracion_ms = models.PositiveIntegerField(null=True, blank=True)
    # La app la pide sola cada minuto; así se pueden ocultar de la lista.
    automatico  = models.BooleanField(default=False)
    ip          = models.GenericIPAddressField(null=True, blank=True)
    cliente     = models.CharField(max_length=10, choices=CLIENTES, blank=True)
    version_app = models.CharField(max_length=20, blank=True)
    sistema     = models.CharField(max_length=40, blank=True)
    dispositivo = models.CharField(max_length=80, blank=True)
    navegador   = models.CharField(max_length=40, blank=True)
    agente      = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ['-momento', '-id']
        indexes = [
            models.Index(fields=['-momento']),
            models.Index(fields=['usuario', '-momento']),
            models.Index(fields=['tipo', '-momento']),
        ]

    def __str__(self):
        return f'{self.correo or "anónimo"} · {self.metodo} {self.camino or self.ruta} · {self.momento:%Y-%m-%d %H:%M}'

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise DatoInmutableError('Una huella de auditoría no se puede modificar.')
        super().save(*args, **kwargs)
