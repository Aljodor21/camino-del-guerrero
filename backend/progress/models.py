from django.db import models

from routines.models import DiaRutina
from users.models import Usuario


class RegistroPeso(models.Model):
    usuario  = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='registros_peso')
    peso_kg  = models.FloatField()
    fecha    = models.DateField(auto_now_add=True)
    nota     = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ['-fecha']

    def __str__(self):
        return f'{self.usuario.email} - {self.peso_kg}kg ({self.fecha})'


class RegistroEntrenamiento(models.Model):
    usuario                 = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='registros_entrenamiento')
    dia_rutina              = models.ForeignKey(DiaRutina, on_delete=models.SET_NULL, null=True, blank=True)
    fecha                   = models.DateField(auto_now_add=True)
    duracion_segundos       = models.PositiveIntegerField(default=0)
    ejercicios_completados  = models.JSONField(default=list, blank=True)
    notas                   = models.TextField(blank=True)

    class Meta:
        ordering = ['-fecha']

    def __str__(self):
        return f'{self.usuario.email} - {self.fecha}'
