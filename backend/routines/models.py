from django.db import models

from users.models import Usuario


class Implemento(models.Model):
    nombre = models.CharField(max_length=100)
    descripcion = models.CharField(max_length=300, blank=True)
    categoria = models.CharField(max_length=100, blank=True)
    es_sin_implemento = models.BooleanField(default=False)

    def __str__(self):
        return self.nombre


class UsuarioImplemento(models.Model):
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='implementos')
    implemento = models.ForeignKey(Implemento, on_delete=models.CASCADE, related_name='usuarios')

    class Meta:
        unique_together = ('usuario', 'implemento')

    def __str__(self):
        return f'{self.usuario.email} - {self.implemento.nombre}'


class Ejercicio(models.Model):
    nombre = models.CharField(max_length=150)
    descripcion = models.TextField(blank=True)
    url_youtube = models.URLField(blank=True)  # el admin agrega esto
    requiere_implemento = models.BooleanField(default=True)
    implementos = models.ManyToManyField(Implemento, through='EjercicioImplemento', blank=True)

    def __str__(self):
        return self.nombre


class EjercicioImplemento(models.Model):
    ejercicio = models.ForeignKey(Ejercicio, on_delete=models.CASCADE)
    implemento = models.ForeignKey(Implemento, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('ejercicio', 'implemento')


class Rutina(models.Model):
    usuario = models.OneToOneField(Usuario, on_delete=models.CASCADE, related_name='rutina')
    nombre = models.CharField(max_length=150)
    descripcion = models.TextField(blank=True)
    fecha_generacion = models.DateTimeField(auto_now_add=True)
    activa = models.BooleanField(default=True)

    def __str__(self):
        return f'Rutina de {self.usuario.email}'


class DiaRutina(models.Model):
    DIAS = [
        (1, 'Lunes'), (2, 'Martes'), (3, 'Miércoles'),
        (4, 'Jueves'), (5, 'Viernes'), (6, 'Sábado'), (7, 'Domingo'),
    ]

    rutina = models.ForeignKey(Rutina, on_delete=models.CASCADE, related_name='dias')
    dia_semana = models.IntegerField(choices=DIAS)

    class Meta:
        unique_together = ('rutina', 'dia_semana')
        ordering = ['dia_semana']

    def __str__(self):
        return f'{self.rutina} - {self.get_dia_semana_display()}'


class Recomendacion(models.Model):
    CATEGORIAS = [
        ('tecnica',   'Técnica'),
        ('fisico',    'Físico'),
        ('nutricion', 'Nutrición'),
        ('mental',    'Mental'),
        ('general',   'General'),
    ]
    titulo       = models.CharField(max_length=200)
    descripcion  = models.TextField(blank=True)
    url_video    = models.URLField(blank=True)
    categoria    = models.CharField(max_length=20, choices=CATEGORIAS, default='general')
    activa       = models.BooleanField(default=True)
    orden        = models.PositiveIntegerField(default=0)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['orden', '-fecha_creacion']

    def __str__(self):
        return self.titulo


class EjercicioDia(models.Model):
    dia = models.ForeignKey(DiaRutina, on_delete=models.CASCADE, related_name='ejercicios')
    ejercicio = models.ForeignKey(Ejercicio, on_delete=models.CASCADE)
    series = models.PositiveIntegerField(null=True, blank=True)
    repeticiones = models.PositiveIntegerField(null=True, blank=True)
    duracion_segundos = models.PositiveIntegerField(null=True, blank=True)
    orden = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['orden']

    def __str__(self):
        return f'{self.dia} - {self.ejercicio.nombre}'
