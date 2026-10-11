import uuid
from datetime import timedelta
from decimal import Decimal

from django.db import models, transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.utils import timezone

from core.exceptions import DatoInmutableError
from users.models import Proceso, Usuario

from .grupos import GRUPOS, TIEMPOS


class ListaMercado(models.Model):
    usuario          = models.OneToOneField(Usuario, on_delete=models.CASCADE, related_name='lista_mercado')
    menu             = models.ForeignKey('MenuSemanal', on_delete=models.SET_NULL, null=True, blank=True)
    fecha_generacion = models.DateTimeField(auto_now_add=True)
    consejos_compra    = models.JSONField(default=list, blank=True)
    plan_preparacion   = models.JSONField(default=list, blank=True)
    num_personas       = models.PositiveSmallIntegerField(default=1)
    items_ya_comprados = models.JSONField(default=list, blank=True)
    # Para cuántos días se armó: una semana, 15 días o un mes.
    periodo            = models.CharField(max_length=10, default='semana',
                                          choices=[('semana', 'Una semana'), ('quincena', '15 días'), ('mes', 'Un mes')])

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
        ('mensual',   'Mensual'),
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


def ruta_info_suplemento(instancia, nombre):
    extension = nombre.rsplit('.', 1)[-1].lower() if '.' in nombre else 'jpg'
    return f'suplementos/{instancia.usuario_id}/{uuid.uuid4().hex}.{extension}'


class Suplemento(models.Model):
    """Suplemento que hace parte del proceso (ej. proteína hipercalórica en volumen, creatina).

    `duracion_dias` vacío significa que va mientras dure el proceso. Si la duración
    se asumió (ej. 3 meses para la proteína), queda sin confirmar hasta que el
    usuario la corrobore con lo que le indicó su profesional.
    """

    TIPOS = [
        ('hipercalorico', 'Proteína hipercalórica'),
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
    # Lo que dice la etiqueta: la porción es la del día, pesa tantos gramos y son tantos
    # scoops. Con el peso del envase se calcula cuántas porciones trae.
    peso_envase_g       = models.PositiveIntegerField(null=True, blank=True, help_text='Peso neto del envase')
    porcion_g           = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True,
                                              help_text='Gramos de una porción')
    scoops_porcion      = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True,
                                              help_text='Scoops que hacen una porción')
    porciones_dia       = models.DecimalField(max_digits=3, decimal_places=1, default=1)
    # Con qué se mezcla (opcional) y cuánto líquido lleva la porción completa del día.
    # Con leche, esos ml entran a la lista de mercado.
    liquido             = models.CharField(max_length=10, blank=True, choices=[('agua', 'Agua'), ('leche', 'Leche')])
    liquido_ml          = models.PositiveIntegerField(null=True, blank=True, help_text='ml de líquido por porción')
    envase_desde        = models.DateField(help_text='Día en que se abrió el envase actual')
    fecha_fin           = models.DateField(null=True, blank=True, help_text='Día en que se dejó de tomar')
    # Dónde entra en la minuta: la porción del día se reparte en tomas, cada una en una
    # comida, con sus scoops y lo que reemplaza en esa comida:
    # [{'tiempo': 'onces', 'scoops': 3, 'reemplaza': {'lacteos': 1}}]. Vacío si aún no se sabe.
    tomas               = models.JSONField(default=list, blank=True)
    # Información nutricional: un enlace y/o la foto o el PDF de la etiqueta (privado).
    info_url            = models.URLField(max_length=500, blank=True)
    info_archivo        = models.FileField(upload_to=ruta_info_suplemento, blank=True)
    # Foto del producto (el pote), aparte de la etiqueta con su información nutricional.
    foto                = models.FileField(upload_to=ruta_info_suplemento, blank=True)
    fecha_creacion      = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['fecha_inicio', 'id']
        constraints = [
            models.CheckConstraint(condition=models.Q(porciones_dia__gt=0), name='suplemento_porciones_dia_positivas'),
            models.CheckConstraint(condition=models.Q(liquido_ml__isnull=True) | models.Q(liquido_ml__lte=5000),
                                   name='suplemento_liquido_razonable'),
            models.CheckConstraint(
                condition=models.Q(fecha_fin__isnull=True) | models.Q(fecha_fin__gte=models.F('fecha_inicio')),
                name='suplemento_fechas_coherentes',
            ),
        ]

    def __str__(self):
        return f'{self.usuario.email} - {self.get_tipo_display()} {self.nombre}'.strip()

    ARTICULOS = {'hipercalorico': 'la', 'proteina': 'la', 'creatina': 'la', 'otro': 'el'}

    @property
    def nombre_visible(self):
        """Cómo se nombra en los recordatorios: 'Whey Gold', 'la proteína', 'la proteína hipercalórica'."""
        if self.nombre:
            return self.nombre
        generico = 'suplemento' if self.tipo == 'otro' else self.get_tipo_display().lower()
        return f'{self.ARTICULOS[self.tipo]} {generico}'

    def toma_en(self, tiempo):
        return next((t for t in self.tomas if t['tiempo'] == tiempo), None)

    def activo_en(self, fecha):
        fin = self.fecha_fin or self.fin_estimado
        return self.fecha_inicio <= fecha and (fin is None or fecha <= fin)

    @property
    def fin_estimado(self):
        """Último día planeado: por su duración o, si no tiene, el fin del plan del proceso."""
        if self.duracion_dias:
            return self.fecha_inicio + timedelta(days=self.duracion_dias - 1)
        return self.proceso.fecha_fin_plan

    @property
    def porciones_por_envase(self):
        """Las que se anotaron o, si no, las que salen del peso del envase y de la porción."""
        if self.porciones_envase:
            return self.porciones_envase
        if self.peso_envase_g and self.porcion_g:
            return int(self.peso_envase_g // self.porcion_g) or None
        return None

    @property
    def dias_envase(self):
        porciones = self.porciones_por_envase
        if not porciones:
            return None
        return int(porciones // self.porciones_dia) or 1

    @property
    def se_acaba(self):
        """Día en que se termina el envase actual si se toma como está indicado."""
        dias = self.dias_envase
        return self.envase_desde + timedelta(days=dias - 1) if dias else None


class AlimentoIntercambio(models.Model):
    """Alimento de la lista de intercambios: cuánto es una porción de su grupo."""
    GRUPOS = [g for g in GRUPOS if g[0] != 'agua'] + [
        ('azucares', 'Azúcares y dulces'),
        ('libres',   'Libres'),
    ]

    grupo    = models.CharField(max_length=20, choices=GRUPOS)
    subgrupo = models.CharField(max_length=60)
    nombre   = models.CharField(max_length=120)
    gramos   = models.PositiveSmallIntegerField(null=True, blank=True, help_text='Peso de una porción')
    medida   = models.CharField(max_length=80, help_text='Medida casera de una porción')

    class Meta:
        ordering = ['grupo', 'subgrupo', 'nombre']
        constraints = [models.UniqueConstraint(fields=['grupo', 'nombre'], name='intercambio_unico_por_grupo')]

    def __str__(self):
        return f'{self.nombre} ({self.get_grupo_display()})'


def ruta_minuta(instancia, nombre):
    extension = nombre.rsplit('.', 1)[-1].lower() if '.' in nombre else 'pdf'
    return f'minutas/{instancia.usuario_id}/{uuid.uuid4().hex}.{extension}'


class Minuta(models.Model):
    """Minuta patrón del proceso: porciones por grupo de alimentos en cada comida.

    La da la nutricionista (se llena con la plantilla de la app, a mano o desde su
    PDF) o la calcula la IA. Una vez guardada no cambia: si hay otra, se guarda una
    nueva y la anterior queda en el historial.
    """
    ORIGENES = [
        ('nutricionista', 'Nutricionista'),
        ('ia',            'Calculada por IA'),
    ]

    usuario         = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='minutas')
    proceso         = models.ForeignKey(Proceso, on_delete=models.CASCADE, related_name='minutas')
    origen          = models.CharField(max_length=20, choices=ORIGENES)
    archivo         = models.FileField(upload_to=ruta_minuta, blank=True, help_text='PDF o foto del original')
    # {grupo: {'dia': porciones, tiempo: porciones, ...}}. Lo del día que no se
    # reparte en comidas se come cuando se quiera (agua, semillas).
    porciones       = models.JSONField()
    kcal            = models.PositiveSmallIntegerField(null=True, blank=True)
    proteina_g_kg   = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True)
    menu_ejemplo    = models.JSONField(default=dict, blank=True)
    recomendaciones = models.TextField(blank=True)
    fecha_creacion  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-fecha_creacion', '-id']

    def __str__(self):
        return f'Minuta de {self.usuario.email} ({self.fecha_creacion:%Y-%m-%d})'

    def _filas(self):
        """Filas de la minuta en el orden de los grupos (el JSON guardado no conserva el orden)."""
        return [(g, self.porciones[g]) for g, _ in GRUPOS if g in self.porciones]

    def porciones_en(self, tiempo):
        """{grupo: porciones} de una comida, sin los grupos en cero."""
        return {g: Decimal(str(fila[tiempo])) for g, fila in self._filas() if g != 'agua' and fila.get(tiempo)}

    def tiempos(self):
        return [t for t, _ in TIEMPOS if any(fila.get(t) for g, fila in self._filas() if g != 'agua')]

    def durante_el_dia(self):
        """Porciones del día que la minuta no reparte en comidas (agua, semillas)."""
        libres = {}
        for g, fila in self._filas():
            resto = fila.get('dia', 0) - sum(v for k, v in fila.items() if k != 'dia')
            if resto > 0:
                libres[g] = resto
        return libres

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise DatoInmutableError('La minuta no se puede modificar: guarda una nueva.')
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise DatoInmutableError('La minuta no se puede eliminar.')


@receiver(post_delete, sender=Minuta)
def borrar_archivo_minuta(sender, instance, **kwargs):
    archivo = instance.archivo
    transaction.on_commit(lambda: archivo.storage.delete(archivo.name) if archivo.name else None)


class PreferenciasComida(models.Model):
    """Lo que el usuario decide sobre su menú y no viene de la nutricionista."""
    usuario   = models.OneToOneField(Usuario, on_delete=models.CASCADE, related_name='preferencias_comida')
    # {tiempo: 'entre_semana' | 'siempre'} para las comidas que hace por fuera de casa.
    por_fuera = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return f'Preferencias de {self.usuario.email}'

    def come_por_fuera(self, tiempo, fecha):
        regla = self.por_fuera.get(tiempo)
        return regla == 'siempre' or (regla == 'entre_semana' and fecha.weekday() < 5)


class MenuSemanal(models.Model):
    """Menú de una semana (de lunes a domingo) armado solo con la minuta y los intercambios."""
    usuario         = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='menus')
    minuta          = models.ForeignKey(Minuta, on_delete=models.CASCADE, related_name='menus')
    semana          = models.DateField(help_text='Lunes de la semana')
    generado_con_ia = models.BooleanField(default=False)
    fecha_creacion  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-semana']
        constraints = [models.UniqueConstraint(fields=['usuario', 'semana'], name='menu_unico_por_semana')]

    def __str__(self):
        return f'Menú de {self.usuario.email} ({self.semana})'


class ComidaMenu(models.Model):
    menu      = models.ForeignKey(MenuSemanal, on_delete=models.CASCADE, related_name='comidas')
    fecha     = models.DateField()
    tiempo    = models.CharField(max_length=20, choices=TIEMPOS)
    nombre    = models.CharField(max_length=120, blank=True, help_text='Nombre del plato, si lo tiene')
    por_fuera = models.BooleanField(default=False)
    cambiada  = models.BooleanField(default=False)

    class Meta:
        ordering = ['fecha', 'id']
        constraints = [models.UniqueConstraint(fields=['menu', 'fecha', 'tiempo'], name='comida_unica_por_tiempo')]

    def __str__(self):
        return f'{self.get_tiempo_display()} {self.fecha}'


class ComponenteComida(models.Model):
    """Un alimento de la lista de intercambios con las porciones que cubre de su grupo.
    Los alimentos libres acompañan sin contar porciones (0)."""
    comida    = models.ForeignKey(ComidaMenu, on_delete=models.CASCADE, related_name='componentes')
    alimento  = models.ForeignKey(AlimentoIntercambio, on_delete=models.PROTECT, related_name='+')
    porciones = models.DecimalField(max_digits=3, decimal_places=1)

    class Meta:
        ordering = ['id']
        constraints = [
            models.CheckConstraint(condition=models.Q(porciones__gte=0), name='componente_porciones_no_negativas'),
        ]

    def __str__(self):
        return f'{self.porciones} × {self.alimento.nombre}'


def _ruta_comida(instancia, carpeta):
    return f'comidas/{instancia.usuario_id}/{carpeta}/{uuid.uuid4().hex}.jpg'


def ruta_comida_foto(instancia, _nombre):
    return _ruta_comida(instancia, 'original')


def ruta_comida_miniatura(instancia, _nombre):
    return _ruta_comida(instancia, 'mini')


class RegistroComida(models.Model):
    """Lo que el usuario contó que comió en una comida, para compararlo con su minuta.
    Guarda lo que la minuta pedía ese día y lo que comió, por grupo. Es inmutable."""
    usuario   = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='registros_comida')
    fecha     = models.DateField(default=timezone.localdate)
    tiempo    = models.CharField(max_length=20, choices=TIEMPOS)
    momento   = models.DateTimeField(default=timezone.now)
    # {grupo: {'pedido': porciones que pedía la minuta, 'comido': porciones que comió}}
    grupos    = models.JSONField(default=dict)
    nota      = models.CharField(max_length=300, blank=True)
    foto      = models.ImageField(upload_to=ruta_comida_foto, blank=True)
    miniatura = models.ImageField(upload_to=ruta_comida_miniatura, blank=True)

    class Meta:
        ordering = ['-fecha', '-momento']
        constraints = [
            models.UniqueConstraint(fields=['usuario', 'fecha', 'tiempo'], name='registro_comida_unico'),
        ]

    def __str__(self):
        return f'{self.usuario.email} - {self.get_tiempo_display()} {self.fecha}'

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise DatoInmutableError('Lo que registraste de una comida no se puede modificar.')
        super().save(*args, **kwargs)


@receiver(post_delete, sender=RegistroComida)
def borrar_fotos_comida(sender, instance, **kwargs):
    archivos = [instance.foto, instance.miniatura]
    transaction.on_commit(lambda: [a.storage.delete(a.name) for a in archivos if a.name])


@receiver(post_delete, sender=Suplemento)
def borrar_info_suplemento(sender, instance, **kwargs):
    archivos = [instance.info_archivo, instance.foto]
    transaction.on_commit(lambda: [a.storage.delete(a.name) for a in archivos if a.name])


def ruta_ilustracion(instancia, nombre):
    return f'ilustraciones/{instancia.usuario_id}/{uuid.uuid4().hex}.jpg'


class Ilustracion(models.Model):
    """Imagen orientativa de cómo podría verse el cambio estimado hasta el control. La genera
    OpenAI a partir de la foto de frente de la persona, con su permiso. Es privada."""
    usuario           = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='ilustraciones')
    creada            = models.DateTimeField(default=timezone.now)
    peso_base         = models.FloatField()
    cambio_kg         = models.FloatField()
    # La estimación daba más de lo que se muestra: la imagen se queda en un cambio moderado.
    limitado          = models.BooleanField(default=False)
    dias              = models.PositiveSmallIntegerField()
    imagen            = models.FileField(upload_to=ruta_ilustracion)
    consentimiento_en = models.DateTimeField()

    class Meta:
        ordering = ['-creada', '-id']


@receiver(post_delete, sender=Ilustracion)
def borrar_imagen_ilustracion(sender, instance, **kwargs):
    archivo = instance.imagen
    if archivo.name:
        transaction.on_commit(lambda: archivo.storage.delete(archivo.name))
