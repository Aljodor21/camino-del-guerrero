from django.db import models

from users.models import ObjetivoUsuario, Usuario


class PlanNutricional(models.Model):
    usuario = models.OneToOneField(Usuario, on_delete=models.CASCADE, related_name='plan_nutricional')
    objetivo = models.ForeignKey(ObjetivoUsuario, on_delete=models.SET_NULL, null=True)
    fecha_generacion = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Plan de {self.usuario.email}'


class DiaNutricional(models.Model):
    DIAS = [
        (1, 'Lunes'), (2, 'Martes'), (3, 'Miércoles'),
        (4, 'Jueves'), (5, 'Viernes'), (6, 'Sábado'), (7, 'Domingo'),
    ]

    plan = models.ForeignKey(PlanNutricional, on_delete=models.CASCADE, related_name='dias')
    dia_semana = models.IntegerField(choices=DIAS)
    desayuno = models.TextField()
    almuerzo = models.TextField()
    cena = models.TextField()
    snacks = models.TextField(blank=True)
    calorias_aprox = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ['dia_semana']

    def __str__(self):
        return f'{self.plan} - {self.get_dia_semana_display()}'
