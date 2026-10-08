from datetime import timedelta

from django.db import models

from users.models import Proceso, Usuario


class PlanNutricional(models.Model):
    usuario = models.OneToOneField(Usuario, on_delete=models.CASCADE, related_name='plan_nutricional')
    proceso = models.ForeignKey(Proceso, on_delete=models.SET_NULL, null=True, related_name='planes_nutricionales')
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
    consejos_compra    = models.JSONField(default=list, blank=True)
    plan_preparacion   = models.JSONField(default=list, blank=True)
    num_personas       = models.PositiveSmallIntegerField(default=1)
    items_ya_comprados = models.JSONField(default=list, blank=True)

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
    FRECUENCIAS = [
        ('semanal',   'Semanal'),
        ('quincenal', 'Quincenal'),
    ]

    lista     = models.ForeignKey(ListaMercado, on_delete=models.CASCADE, related_name='items')
    nombre    = models.CharField(max_length=200)
    cantidad  = models.CharField(max_length=100, blank=True)
    categoria = models.CharField(max_length=20, choices=CATEGORIAS, default='condimentos')
    frecuencia= models.CharField(max_length=10, choices=FRECUENCIAS, default='semanal')
    comprado  = models.BooleanField(default=False)

    class Meta:
        ordering = ['categoria', 'nombre']

    def __str__(self):
        return f'{self.nombre} ({self.cantidad})'


class ItemRecurrente(models.Model):
    """Última fecha de compra de un ítem quincenal — se actualiza, no se acumula."""
    usuario       = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='items_recurrentes')
    nombre        = models.CharField(max_length=200)
    ultima_compra = models.DateField()

    class Meta:
        unique_together = ('usuario', 'nombre')

    def __str__(self):
        return f'{self.nombre} - {self.usuario.email} ({self.ultima_compra})'


class Suplemento(models.Model):
    """Suplemento que hace parte del proceso (ej. hipercalórico en volumen, proteína).

    `duracion_dias` vacío significa que va mientras dure el proceso. Si la duración
    se asumió (ej. 3 meses para la proteína), queda sin confirmar hasta que el
    usuario la corrobore con lo que le indicó su profesional.
    """

    TIPOS = [
        ('hipercalorico', 'Hipercalórico'),
        ('proteina',      'Proteína'),
        ('creatina',      'Creatina'),
        ('otro',          'Otro'),
    ]

    usuario             = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='suplementos')
    proceso             = models.ForeignKey(Proceso, on_delete=models.CASCADE, related_name='suplementos')
    tipo                = models.CharField(max_length=20, choices=TIPOS)
    nombre              = models.CharField(max_length=120, blank=True, help_text='Marca o producto')
    fecha_inicio        = models.DateField()
    duracion_dias       = models.PositiveSmallIntegerField(null=True, blank=True)
    duracion_confirmada = models.BooleanField(default=False)
    porciones_envase    = models.PositiveSmallIntegerField(null=True, blank=True)
    porciones_dia       = models.DecimalField(max_digits=3, decimal_places=1, default=1)
    envase_desde        = models.DateField(help_text='Día en que se abrió el envase actual')
    fecha_fin           = models.DateField(null=True, blank=True, help_text='Día en que se dejó de tomar')
    fecha_creacion      = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['fecha_inicio', 'id']
        constraints = [
            models.CheckConstraint(condition=models.Q(porciones_dia__gt=0), name='suplemento_porciones_dia_positivas'),
            models.CheckConstraint(
                condition=models.Q(fecha_fin__isnull=True) | models.Q(fecha_fin__gte=models.F('fecha_inicio')),
                name='suplemento_fechas_coherentes',
            ),
        ]

    def __str__(self):
        return f'{self.usuario.email} - {self.get_tipo_display()} {self.nombre}'.strip()

    ARTICULOS = {'hipercalorico': 'el', 'proteina': 'la', 'creatina': 'la', 'otro': 'el'}

    @property
    def nombre_visible(self):
        """Cómo se nombra en los recordatorios: 'Whey Gold', 'la proteína', 'el hipercalórico'."""
        if self.nombre:
            return self.nombre
        generico = 'suplemento' if self.tipo == 'otro' else self.get_tipo_display().lower()
        return f'{self.ARTICULOS[self.tipo]} {generico}'

    @property
    def fin_estimado(self):
        """Último día planeado: por su duración o, si no tiene, el fin del plan del proceso."""
        if self.duracion_dias:
            return self.fecha_inicio + timedelta(days=self.duracion_dias - 1)
        return self.proceso.fecha_fin_plan

    @property
    def dias_envase(self):
        if not self.porciones_envase:
            return None
        return int(self.porciones_envase // self.porciones_dia) or 1

    @property
    def se_acaba(self):
        """Día en que se termina el envase actual si se toma como está indicado."""
        dias = self.dias_envase
        return self.envase_desde + timedelta(days=dias - 1) if dias else None
