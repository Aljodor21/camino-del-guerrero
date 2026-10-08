from decimal import Decimal

from rest_framework import serializers

from .models import DiaNutricional, ItemMercado, ListaMercado, PlanNutricional, Suplemento


class DiaNutricionalSerializer(serializers.ModelSerializer):
    dia_nombre = serializers.CharField(source='get_dia_semana_display', read_only=True)

    class Meta:
        model = DiaNutricional
        fields = ['id', 'dia_semana', 'dia_nombre', 'desayuno', 'almuerzo', 'cena', 'snacks', 'calorias_aprox']


class PlanNutricionalSerializer(serializers.ModelSerializer):
    dias = DiaNutricionalSerializer(many=True, read_only=True)

    class Meta:
        model = PlanNutricional
        fields = ['id', 'fecha_generacion', 'dias']


class ItemMercadoSerializer(serializers.ModelSerializer):
    categoria_nombre  = serializers.CharField(source='get_categoria_display', read_only=True)
    frecuencia_nombre = serializers.CharField(source='get_frecuencia_display', read_only=True)

    class Meta:
        model  = ItemMercado
        fields = ['id', 'nombre', 'cantidad', 'categoria', 'categoria_nombre',
                  'frecuencia', 'frecuencia_nombre', 'comprado']


class ListaMercadoSerializer(serializers.ModelSerializer):
    items = ItemMercadoSerializer(many=True, read_only=True)

    class Meta:
        model  = ListaMercado
        fields = ['id', 'fecha_generacion', 'items', 'consejos_compra', 'plan_preparacion',
                  'num_personas', 'items_ya_comprados']


class SuplementoSerializer(serializers.ModelSerializer):
    tipo_nombre  = serializers.CharField(source='get_tipo_display', read_only=True)
    fin_estimado = serializers.DateField(read_only=True)
    dias_envase  = serializers.IntegerField(read_only=True)
    se_acaba     = serializers.DateField(read_only=True)

    class Meta:
        model  = Suplemento
        fields = ['id', 'tipo', 'tipo_nombre', 'nombre', 'fecha_inicio', 'duracion_dias', 'duracion_confirmada',
                  'porciones_envase', 'porciones_dia', 'envase_desde', 'fecha_fin', 'fin_estimado',
                  'dias_envase', 'se_acaba', 'proceso']
        read_only_fields = ['fecha_inicio', 'envase_desde', 'fecha_fin', 'proceso']
        extra_kwargs = {
            'duracion_dias':    {'min_value': 1, 'max_value': 730},
            'porciones_envase': {'min_value': 1, 'max_value': 500},
            'porciones_dia':    {'min_value': Decimal('0.5'), 'max_value': 10, 'coerce_to_string': False},
        }

    def validate_nombre(self, nombre):
        return nombre.strip()


class SuplementoEditarSerializer(SuplementoSerializer):
    class Meta(SuplementoSerializer.Meta):
        read_only_fields = SuplementoSerializer.Meta.read_only_fields + ['tipo']


class ContinuarSerializer(serializers.Serializer):
    dias = serializers.IntegerField(min_value=7, max_value=365)
