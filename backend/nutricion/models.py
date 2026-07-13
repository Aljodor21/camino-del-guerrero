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


class ListaMercado(models.Model):
    usuario          = models.OneToOneField(Usuario, on_delete=models.CASCADE, related_name='lista_mercado')
    plan             = models.ForeignKey(PlanNutricional, on_delete=models.SET_NULL, null=True)
    fecha_generacion = models.DateTimeField(auto_now_add=True)
    consejos_compra  = models.JSONField(default=list, blank=True)
    plan_preparacion = models.JSONField(default=list, blank=True)

    def __str__(self):
        return f'Lista de {self.usuario.email}'


class ItemMercado(models.Model):
    CATEGORIAS = [
        ('proteinas',  'Proteínas'),
        ('verduras',   'Verduras'),
        ('frutas',     'Frutas'),
        ('lacteos',    'Lácteos'),
        ('granos',     'Granos y cereales'),
        ('condimentos','Condimentos y otros'),
    ]

    lista    = models.ForeignKey(ListaMercado, on_delete=models.CASCADE, related_name='items')
    nombre   = models.CharField(max_length=200)
    cantidad = models.CharField(max_length=100, blank=True)
    categoria= models.CharField(max_length=20, choices=CATEGORIAS, default='condimentos')
    comprado = models.BooleanField(default=False)

    class Meta:
        ordering = ['categoria', 'nombre']

    def __str__(self):
        return f'{self.nombre} ({self.cantidad})'
