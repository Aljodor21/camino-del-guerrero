from django.contrib.auth.models import AbstractUser
from django.db import models


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

    email            = models.EmailField(unique=True)
    nombre           = models.CharField(max_length=150)
    rol              = models.ForeignKey(Rol,  on_delete=models.PROTECT, null=True, blank=True, related_name='usuarios')
    sexo             = models.ForeignKey(Sexo, on_delete=models.SET_NULL, null=True, blank=True, related_name='usuarios')
    fecha_nacimiento = models.DateField(null=True, blank=True)
    estatura         = models.PositiveIntegerField(null=True, blank=True, help_text='Estatura en centímetros')
    frecuencia_peso  = models.IntegerField(default=30, choices=FRECUENCIA_CHOICES)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'nombre']

    def __str__(self):
        return self.email


class ObjetivoUsuario(models.Model):
    OBJETIVOS = [
        ('bajar_peso',   'Bajar peso'),
        ('ganar_musculo','Ganar músculo'),
        ('mantener',     'Mantener peso'),
        ('resistencia',  'Mejorar resistencia'),
    ]

    usuario       = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='objetivos')
    objetivo      = models.CharField(max_length=50, choices=OBJETIVOS)
    peso_inicial  = models.FloatField()
    peso_objetivo = models.FloatField(null=True, blank=True)
    fecha_inicio  = models.DateField(auto_now_add=True)
    activo        = models.BooleanField(default=True)

    def __str__(self):
        return f'{self.usuario.email} - {self.objetivo}'
