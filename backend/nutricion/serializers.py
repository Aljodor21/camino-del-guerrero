import json
from datetime import time
from decimal import Decimal

from django.utils import timezone
from rest_framework import serializers

from . import cantidades, mercado
from .grupos import GRUPOS_CON_ALIMENTOS, NOMBRE_GRUPO, NOMBRE_TIEMPO, ORDEN_TIEMPO, POR_FUERA, TIEMPOS
from .models import (AlimentoIntercambio, Ilustracion, ComidaMenu, ComponenteComida, ItemMercado, ListaMercado,
                     MenuSemanal, Minuta, PreferenciasComida, RegistroComida, Suplemento)


class ItemMercadoSerializer(serializers.ModelSerializer):
    categoria_nombre  = serializers.CharField(source='get_categoria_display', read_only=True)
    frecuencia_nombre = serializers.CharField(source='get_frecuencia_display', read_only=True)

    class Meta:
        model  = ItemMercado
        fields = ['id', 'nombre', 'cantidad', 'categoria', 'categoria_nombre',
                  'frecuencia', 'frecuencia_nombre', 'comprado']


class ListaMercadoSerializer(serializers.ModelSerializer):
    items = ItemMercadoSerializer(many=True, read_only=True)
    promocion_colanta = serializers.SerializerMethodField()

    class Meta:
        model  = ListaMercado
        fields = ['id', 'fecha_generacion', 'items', 'consejos_compra', 'plan_preparacion',
                  'num_personas', 'items_ya_comprados', 'periodo', 'promocion_colanta']

    def get_promocion_colanta(self, lista):
        return mercado.proxima_promocion_colanta(timezone.localdate())


LIMITES_TABLA = {'porcion_g': (1, 1000), 'liquido_ml': (10, 3000), 'kcal': (0, 1500), 'proteina_g': (0, 200),
                 'carbohidratos_g': (0, 300), 'grasa_g': (0, 200)}


def validar_tabla_leche(tabla):
    """La tabla de la leche por porción: cuántos ml, calorías y proteína."""
    if tabla in (None, {}):
        return None
    limites = {'porcion_ml': (10, 1000), 'kcal': (0, 1000), 'proteina_g': (0, 100)}
    if not isinstance(tabla, dict) or set(tabla) - set(limites) or set(limites) - set(tabla):
        raise serializers.ValidationError('Escribe los ml de la porción, las calorías y la proteína de la leche.')
    limpia = {}
    for campo, (minimo, maximo) in limites.items():
        try:
            numero = float(str(tabla[campo]).replace(',', '.'))
        except ValueError:
            raise serializers.ValidationError(f'{campo}: escribe un número.')
        if not minimo <= numero <= maximo:
            raise serializers.ValidationError(f'{campo}: debe estar entre {minimo} y {maximo}.')
        limpia[campo] = round(numero, 1)
    return limpia


def validar_tabla(tabla):
    """La tabla nutricional por porción: kcal y proteína son obligatorias; el resto, opcional."""
    if tabla in (None, {}):
        return None
    if not isinstance(tabla, dict) or set(tabla) - set(LIMITES_TABLA):
        raise serializers.ValidationError('La tabla nutricional no tiene el formato esperado.')
    limpia = {}
    for campo, (minimo, maximo) in LIMITES_TABLA.items():
        valor = tabla.get(campo)
        if valor in (None, ''):
            continue
        try:
            numero = float(str(valor).replace(',', '.'))
        except ValueError:
            raise serializers.ValidationError(f'{campo}: escribe un número.')
        if not minimo <= numero <= maximo:
            raise serializers.ValidationError(f'{campo}: debe estar entre {minimo} y {maximo}.')
        limpia[campo] = round(numero, 1)
    if 'kcal' not in limpia or 'proteina_g' not in limpia:
        raise serializers.ValidationError('La tabla necesita al menos las calorías y los gramos de proteína por porción.')
    return limpia


class SuplementoSerializer(serializers.ModelSerializer):
    tipo_nombre  = serializers.CharField(source='get_tipo_display', read_only=True)
    fin_estimado = serializers.DateField(read_only=True)
    dias_envase  = serializers.IntegerField(read_only=True)
    se_acaba     = serializers.DateField(read_only=True)
    porciones_por_envase = serializers.IntegerField(read_only=True)
    info_archivo_tipo    = serializers.SerializerMethodField()
    tiene_foto           = serializers.SerializerMethodField()

    class Meta:
        model  = Suplemento
        fields = ['id', 'tipo', 'tipo_nombre', 'nombre', 'fecha_inicio', 'duracion_dias', 'duracion_confirmada',
                  'porciones_envase', 'porciones_dia', 'envase_desde', 'fecha_fin', 'fin_estimado',
                  'peso_envase_g', 'porcion_g', 'scoops_porcion', 'porciones_por_envase', 'liquido', 'liquido_ml', 'leche_ml', 'leche_nutricional',
                  'info_url', 'info_archivo_tipo', 'tiene_foto', 'tabla_nutricional',
                  'dias_envase', 'se_acaba', 'proceso', 'tomas']
        read_only_fields = ['fecha_inicio', 'envase_desde', 'fecha_fin', 'proceso']
        extra_kwargs = {
            'duracion_dias':    {'min_value': 1, 'max_value': 730},
            'porciones_envase': {'min_value': 1, 'max_value': 500},
            'porciones_dia':    {'min_value': Decimal('0.5'), 'max_value': 10, 'coerce_to_string': False},
            'peso_envase_g':    {'min_value': 50, 'max_value': 20000},
            'porcion_g':        {'min_value': Decimal('1'), 'max_value': Decimal('1000'), 'coerce_to_string': False},
            'scoops_porcion':   {'min_value': Decimal('0.5'), 'max_value': Decimal('20'), 'coerce_to_string': False},
            'liquido_ml':       {'min_value': 10, 'max_value': 5000},
            'leche_ml':         {'min_value': 10, 'max_value': 5000},
        }

    def validate_nombre(self, nombre):
        return nombre.strip()

    def validate_info_url(self, url):
        if url and not url.lower().startswith(('http://', 'https://')):
            raise serializers.ValidationError('El enlace debe empezar por http:// o https://.')
        return url

    def validate_tabla_nutricional(self, tabla):
        return validar_tabla(tabla)

    def validate_leche_nutricional(self, tabla):
        return validar_tabla_leche(tabla)

    def get_tiene_foto(self, s):
        return bool(s.foto)

    def get_info_archivo_tipo(self, s):
        """'pdf', 'imagen' o None si no hay archivo."""
        if not s.info_archivo:
            return None
        return 'pdf' if s.info_archivo.name.lower().endswith('.pdf') else 'imagen'

    @staticmethod
    def _medio(valor, maximo, mensaje):
        """Número positivo, de media en media, hasta `maximo`."""
        try:
            valor = Decimal(str(valor))
        except ArithmeticError:
            raise serializers.ValidationError(mensaje)
        if not valor.is_finite() or valor <= 0 or valor > maximo or valor % Decimal('0.5'):
            raise serializers.ValidationError(mensaje)
        return float(valor)

    def _reemplaza(self, reemplaza):
        if not isinstance(reemplaza, dict):
            raise serializers.ValidationError('Indica las porciones que reemplaza por grupo.')
        limpio = {}
        for grupo, porciones in reemplaza.items():
            if grupo not in GRUPOS_CON_ALIMENTOS:
                raise serializers.ValidationError(f'"{grupo}" no es un grupo de la minuta.')
            limpio[grupo] = self._medio(porciones, 5, 'Las porciones van de media en media, hasta 5.')
        return limpio

    MAX_OTRAS_TOMAS = 4

    def validate_tomas(self, tomas):
        """Una toma por comida de la minuta, y además "otras tomas" a la hora que la persona elija."""
        if not isinstance(tomas, list) or len(tomas) > len(TIEMPOS) + self.MAX_OTRAS_TOMAS:
            raise serializers.ValidationError('Indica en qué comidas lo tomas.')
        limpias, vistos, horas = [], set(), set()
        for toma in tomas:
            tiempo = toma.get('tiempo') if isinstance(toma, dict) else None
            if tiempo != 'otro' and tiempo not in NOMBRE_TIEMPO:
                raise serializers.ValidationError('Cada toma va en una comida de la minuta o en otra hora.')
            if tiempo != 'otro':
                if tiempo in vistos:
                    raise serializers.ValidationError(f'{NOMBRE_TIEMPO[tiempo]} está repetida.')
                vistos.add(tiempo)
            scoops = toma.get('scoops')
            limpia = {
                'tiempo': tiempo,
                'scoops': None if scoops is None else self._medio(
                    scoops, 40, 'Los scoops van de medio en medio, hasta 40.'),
                # Otra toma no reemplaza una comida de la minuta: se suma a lo que ya se come.
                'reemplaza': {} if tiempo == 'otro' else self._reemplaza(toma.get('reemplaza') or {}),
            }
            hora, nota = toma.get('hora'), str(toma.get('nota') or '').strip()[:80]
            if hora:
                try:
                    limpia['hora'] = time.fromisoformat(str(hora)[:5]).isoformat('minutes')
                except ValueError:
                    raise serializers.ValidationError('La hora de la toma no es válida (por ejemplo, 16:30).')
            if tiempo == 'otro':
                if 'hora' not in limpia:
                    raise serializers.ValidationError('Otra toma necesita la hora a la que la tomas.')
                if limpia['hora'] in horas:
                    raise serializers.ValidationError(f'Ya tienes una toma a las {limpia["hora"]}.')
                horas.add(limpia['hora'])
            if nota:
                limpia['nota'] = nota
            limpias.append(limpia)
        # Primero las comidas de la minuta, en su orden; luego las otras, por hora.
        return sorted(limpias, key=lambda t: (1, t['hora']) if t['tiempo'] == 'otro' else (0, ORDEN_TIEMPO[t['tiempo']]))

    def validate(self, datos):
        """La porción es la del día: si se dice cuántos scoops lleva cada toma, entre todas
        suman la porción completa."""
        tomas = datos.get('tomas', getattr(self.instance, 'tomas', []))
        scoops_porcion = datos.get('scoops_porcion', getattr(self.instance, 'scoops_porcion', None))
        con_scoops = [t['scoops'] for t in tomas if t['scoops'] is not None]
        if con_scoops and scoops_porcion:
            if len(con_scoops) != len(tomas) or Decimal(str(sum(con_scoops))) != Decimal(scoops_porcion):
                raise serializers.ValidationError(
                    {'tomas': f'Las tomas deben sumar los {Decimal(scoops_porcion).normalize():f} scoops de la porción.'})
            datos['porciones_dia'] = Decimal(1)
        liquido = datos.get('liquido', getattr(self.instance, 'liquido', ''))
        if not liquido:
            datos['liquido_ml'] = None
        total = datos.get('liquido_ml', getattr(self.instance, 'liquido_ml', None))
        if liquido == 'leche':
            datos['leche_ml'] = total
        elif liquido == 'mezcla':
            leche = datos.get('leche_ml', getattr(self.instance, 'leche_ml', None))
            if not total or not leche:
                raise serializers.ValidationError({'leche_ml': 'Indica cuánto líquido lleva y cuánto de ese es leche.'})
            if leche >= total:
                raise serializers.ValidationError({'leche_ml': 'La leche tiene que ser menos que el líquido total; si es solo leche, elige "Leche".'})
        else:
            datos['leche_ml'] = None
        if liquido in ('agua', ''):
            datos['leche_nutricional'] = None
        return datos


class SuplementoEditarSerializer(SuplementoSerializer):
    class Meta(SuplementoSerializer.Meta):
        read_only_fields = SuplementoSerializer.Meta.read_only_fields + ['tipo']


class ContinuarSerializer(serializers.Serializer):
    dias = serializers.IntegerField(min_value=7, max_value=365)


class AlimentoIntercambioSerializer(serializers.ModelSerializer):
    class Meta:
        model  = AlimentoIntercambio
        fields = ['id', 'grupo', 'subgrupo', 'nombre', 'gramos', 'medida']


class MinutaSerializer(serializers.ModelSerializer):
    tiempos        = serializers.ListField(read_only=True)
    durante_el_dia = serializers.DictField(read_only=True)
    proteina_g_kg  = serializers.DecimalField(max_digits=3, decimal_places=1, coerce_to_string=False, read_only=True)
    tiene_archivo  = serializers.SerializerMethodField()

    class Meta:
        model  = Minuta
        fields = ['id', 'proceso', 'origen', 'porciones', 'tiempos', 'durante_el_dia', 'kcal', 'proteina_g_kg',
                  'menu_ejemplo', 'recomendaciones', 'tiene_archivo', 'fecha_creacion']
        read_only_fields = fields

    def get_tiene_archivo(self, minuta):
        return bool(minuta.archivo)

    def to_representation(self, minuta):
        datos = super().to_representation(minuta)
        datos['tiempos'] = minuta.tiempos()
        datos['durante_el_dia'] = minuta.durante_el_dia()
        return datos


class JSONTextoField(serializers.JSONField):
    """JSON que llega como objeto (cuerpo JSON) o como texto (multipart)."""

    def to_internal_value(self, data):
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except ValueError:
                self.fail('invalid')
        return super().to_internal_value(data)


class MinutaCrearSerializer(serializers.Serializer):
    """Llega como multipart cuando trae el original: los campos JSON vienen como texto."""
    TIPOS_ARCHIVO = ('application/pdf', 'image/jpeg', 'image/png', 'image/webp')
    MAX_BYTES = 10 * 1024 * 1024

    origen          = serializers.ChoiceField(choices=Minuta.ORIGENES)
    proceso         = serializers.IntegerField(required=False)
    porciones       = JSONTextoField()
    kcal            = serializers.IntegerField(min_value=800, max_value=8000, required=False, allow_null=True)
    proteina_g_kg   = serializers.DecimalField(max_digits=3, decimal_places=1, min_value=Decimal('0.5'),
                                               max_value=Decimal('4'), required=False, allow_null=True)
    menu_ejemplo    = JSONTextoField(required=False)
    recomendaciones = serializers.CharField(max_length=2000, required=False, allow_blank=True)
    archivo         = serializers.FileField(required=False)
    # Solo si ya había un plan: hasta cuándo va el nuevo (null = sin definir). Sin esta llave no se toca.
    fecha_fin_plan  = serializers.DateField(required=False, allow_null=True)

    def validate_archivo(self, archivo):
        if archivo.size > self.MAX_BYTES:
            raise serializers.ValidationError('El archivo pesa más de 10 MB.')
        if archivo.content_type not in self.TIPOS_ARCHIVO:
            raise serializers.ValidationError('Adjunta un PDF o una foto (JPG, PNG o WEBP).')
        return archivo

    def validate_menu_ejemplo(self, menu):
        if not isinstance(menu, dict) or any(t not in NOMBRE_TIEMPO or not isinstance(v, str) for t, v in menu.items()):
            raise serializers.ValidationError('El menú de ejemplo no tiene el formato esperado.')
        return {t: v[:1000] for t, v in menu.items()}


class SubirMinutaSerializer(serializers.Serializer):
    archivo = serializers.FileField()


class PreferenciasComidaSerializer(serializers.ModelSerializer):
    class Meta:
        model  = PreferenciasComida
        fields = ['por_fuera']

    def validate_por_fuera(self, por_fuera):
        opciones = dict(POR_FUERA)
        if not isinstance(por_fuera, dict) or any(t not in NOMBRE_TIEMPO or r not in opciones
                                                  for t, r in por_fuera.items()):
            raise serializers.ValidationError('Indica para cada comida si la haces por fuera entre semana o siempre.')
        return por_fuera


def cantidad_casera(alimento, porciones):
    if alimento.grupo == 'libres':
        return 'Al gusto'
    return cantidades.escalar(alimento.medida, porciones, alimento.gramos)


class ComponenteComidaSerializer(serializers.ModelSerializer):
    grupo     = serializers.CharField(source='alimento.grupo', read_only=True)
    alimento  = serializers.SerializerMethodField()
    porciones = serializers.DecimalField(max_digits=3, decimal_places=1, coerce_to_string=False, read_only=True)
    cantidad  = serializers.SerializerMethodField()
    gramos    = serializers.SerializerMethodField()

    class Meta:
        model  = ComponenteComida
        fields = ['id', 'grupo', 'alimento_id', 'alimento', 'porciones', 'cantidad', 'gramos']

    def get_alimento(self, c):
        return cantidades.nombre_visible(c.alimento)

    def get_cantidad(self, c):
        return cantidad_casera(c.alimento, c.porciones)

    def get_gramos(self, c):
        return cantidades.gramos(c.alimento.gramos, c.porciones)


class ComidaMenuSerializer(serializers.ModelSerializer):
    """Necesita el `contexto` del menú (minuta, suplementos) en el contexto del serializer."""
    tiempo_nombre = serializers.CharField(source='get_tiempo_display', read_only=True)
    componentes   = ComponenteComidaSerializer(many=True, read_only=True)
    suplementos   = serializers.SerializerMethodField()
    requerido     = serializers.SerializerMethodField()

    class Meta:
        model  = ComidaMenu
        fields = ['id', 'fecha', 'tiempo', 'tiempo_nombre', 'nombre', 'por_fuera', 'cambiada',
                  'componentes', 'suplementos', 'requerido']

    def get_suplementos(self, comida):
        return [{'id': s.id, 'nombre': s.nombre or s.get_tipo_display(), 'scoops': toma['scoops'],
                 'reemplaza': toma['reemplaza']}
                for s, toma in self.context['contexto'].tomas_en(comida.fecha, comida.tiempo)]

    def get_requerido(self, comida):
        """Lo que pide la minuta en esa comida, con un ejemplo para cuando se come por fuera."""
        contexto, ejemplos = self.context['contexto'], self.context['ejemplos']
        salida = []
        for grupo, porciones in contexto.requerido(comida.fecha, comida.tiempo).items():
            clave = (grupo, comida.tiempo)
            if clave not in ejemplos:
                opciones = self.context['elector'].opciones_para(grupo, comida.tiempo)
                ejemplos[clave] = opciones[0] if opciones else None
            ejemplo = ejemplos[clave]
            salida.append({
                'grupo': grupo, 'grupo_nombre': NOMBRE_GRUPO[grupo], 'porciones': float(porciones),
                'ejemplo': f'{cantidad_casera(ejemplo, porciones)} de {ejemplo.nombre.lower()}' if ejemplo else '',
            })
        return salida


class MenuSemanalSerializer(serializers.ModelSerializer):
    comidas        = serializers.SerializerMethodField()
    durante_el_dia = serializers.SerializerMethodField()

    class Meta:
        model  = MenuSemanal
        fields = ['id', 'semana', 'minuta', 'generado_con_ia', 'durante_el_dia', 'comidas']

    def get_comidas(self, menu):
        comidas = menu.comidas.prefetch_related('componentes__alimento')
        return ComidaMenuSerializer(sorted(comidas, key=lambda c: (c.fecha, list(NOMBRE_TIEMPO).index(c.tiempo))),
                                    many=True, context=self.context).data

    def get_durante_el_dia(self, menu):
        return [{'grupo': g, 'grupo_nombre': NOMBRE_GRUPO[g], 'porciones': p}
                for g, p in menu.minuta.durante_el_dia().items()]


class RegistroComidaSerializer(serializers.ModelSerializer):
    tiempo_nombre = serializers.CharField(source='get_tiempo_display', read_only=True)
    tiene_foto    = serializers.SerializerMethodField()

    class Meta:
        model  = RegistroComida
        fields = ['id', 'fecha', 'tiempo', 'tiempo_nombre', 'momento', 'grupos', 'nota', 'tiene_foto']
        read_only_fields = fields

    def get_tiene_foto(self, r):
        return bool(r.foto)


class RegistroComidaCrearSerializer(serializers.Serializer):
    """Lo que se manda al contar una comida (multipart, por la foto)."""
    fecha   = serializers.DateField(required=False)
    tiempo  = serializers.ChoiceField(choices=TIEMPOS)
    # {grupo: de 0 a 1}; en multipart llega como JSON en texto.
    avances = serializers.JSONField()
    nota    = serializers.CharField(max_length=300, required=False, allow_blank=True, default='')
    foto    = serializers.ImageField(required=False, allow_null=True)
    # Ids de los suplementos que se tomó en esta comida; en multipart llega como JSON en texto.
    tomas   = serializers.JSONField(required=False, default=list)

    def validate_tomas(self, tomas):
        if not isinstance(tomas, list) or not all(isinstance(i, int) for i in tomas):
            raise serializers.ValidationError('Indica qué tomaste.')
        return tomas

    def validate_avances(self, avances):
        if not isinstance(avances, dict):
            raise serializers.ValidationError('Indica cuánto comiste de cada grupo.')
        return avances


class IlustracionSerializer(serializers.ModelSerializer):
    peso_final = serializers.SerializerMethodField()

    class Meta:
        model  = Ilustracion
        fields = ['id', 'creada', 'peso_base', 'cambio_kg', 'peso_final', 'limitado', 'dias', 'foto_origen']
        read_only_fields = fields

    def get_peso_final(self, i):
        return round(i.peso_base + i.cambio_kg, 1)
