from rest_framework import serializers

from .models import DiaNutricional, PlanNutricional


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
