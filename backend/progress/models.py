import uuid

from django.db import models, transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.utils import timezone

from core.exceptions import DatoInmutableError
from routines.models import DiaRutina
from users.models import Usuario


class Medicion(models.Model):
    """Medición corporal en una fecha. Es inmutable: se registra una vez y no se edita."""

    ORIGENES = [
        ('propia',      'Tomada por mí'),
        ('profesional', 'Tomada por un profesional'),
    ]

    usuario    = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='mediciones')
    fecha      = models.DateField(default=timezone.localdate)
    origen     = models.CharField(max_length=20, choices=ORIGENES, default='propia')
    peso_kg    = models.FloatField()
    talla_cm   = models.FloatField(null=True, blank=True)

    # Perímetros (cm)
    cintura_cm = models.FloatField(null=True, blank=True)
    abdomen_cm = models.FloatField(null=True, blank=True)
    cadera_cm  = models.FloatField(null=True, blank=True)
    brazo_cm   = models.FloatField(null=True, blank=True)
    muslo_cm   = models.FloatField(null=True, blank=True)
    pierna_cm  = models.FloatField(null=True, blank=True)

    # Pliegues cutáneos (mm)
    pliegue_triceps_mm       = models.FloatField(null=True, blank=True)
    pliegue_biceps_mm        = models.FloatField(null=True, blank=True)
    pliegue_subescapular_mm  = models.FloatField(null=True, blank=True)
    pliegue_supraespinal_mm  = models.FloatField(null=True, blank=True)
    pliegue_abdominal_mm     = models.FloatField(null=True, blank=True)
    pliegue_muslo_mm         = models.FloatField(null=True, blank=True)
    pliegue_pierna_mm        = models.FloatField(null=True, blank=True)
    pliegue_cresta_iliaca_mm = models.FloatField(null=True, blank=True)

    nota           = models.CharField(max_length=300, blank=True)
    fecha_registro = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-fecha', '-id']

    def __str__(self):
        return f'{self.usuario.email} - {self.peso_kg}kg ({self.fecha})'

    @property
    def imc(self):
        if not self.talla_cm:
            return None
        return round(self.peso_kg / (self.talla_cm / 100) ** 2, 2)

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise DatoInmutableError('Una medición registrada no se puede modificar.')
        super().save(*args, **kwargs)


def _ruta_foto(instancia, carpeta):
    return f'progreso/{instancia.medicion.usuario_id}/{carpeta}/{uuid.uuid4().hex}.jpg'


def ruta_foto_original(instancia, _nombre):
    return _ruta_foto(instancia, 'original')


def ruta_foto_miniatura(instancia, _nombre):
    return _ruta_foto(instancia, 'mini')


class FotoProgreso(models.Model):
    """Foto del cuerpo tomada junto a una medición. Es privada e inmutable: se sube
    una por pose y no se reemplaza."""

    POSES = [
        ('frente',  'Frente'),
        ('perfil',  'Perfil'),
        ('espalda', 'Espalda'),
    ]

    medicion       = models.ForeignKey(Medicion, on_delete=models.CASCADE, related_name='fotos')
    pose           = models.CharField(max_length=10, choices=POSES)
    imagen         = models.ImageField(upload_to=ruta_foto_original, width_field='ancho', height_field='alto')
    miniatura      = models.ImageField(upload_to=ruta_foto_miniatura)
    ancho          = models.PositiveIntegerField(editable=False)
    alto           = models.PositiveIntegerField(editable=False)
    fecha_registro = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['medicion', 'pose']
        constraints = [
            models.UniqueConstraint(fields=['medicion', 'pose'], name='foto_unica_por_pose'),
        ]

    def __str__(self):
        return f'{self.medicion} - {self.pose}'

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise DatoInmutableError('Una foto registrada no se puede modificar.')
        super().save(*args, **kwargs)


class RegistroEntrenamiento(models.Model):
    usuario                 = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='registros_entrenamiento')
    dia_rutina              = models.ForeignKey(DiaRutina, on_delete=models.SET_NULL, null=True, blank=True)
    fecha                   = models.DateField(default=timezone.localdate, editable=False)
    duracion_segundos       = models.PositiveIntegerField(default=0)
    ejercicios_completados  = models.JSONField(default=list, blank=True)
    notas                   = models.TextField(blank=True)

    class Meta:
        ordering = ['-fecha']

    def __str__(self):
        return f'{self.usuario.email} - {self.fecha}'


@receiver(post_delete, sender=FotoProgreso)
def borrar_archivos_foto(sender, instance, **kwargs):
    archivos = [instance.imagen, instance.miniatura]
    transaction.on_commit(lambda: [a.storage.delete(a.name) for a in archivos if a.name])
