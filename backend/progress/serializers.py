from rest_framework import serializers
from .models import RegistroEntrenamiento, RegistroPeso


class RegistroPesoSerializer(serializers.ModelSerializer):
    class Meta:
        model  = RegistroPeso
        fields = ['id', 'peso_kg', 'fecha', 'nota']
        read_only_fields = ['fecha']


class RegistroEntrenamientoSerializer(serializers.ModelSerializer):
    dia_nombre = serializers.SerializerMethodField()

    def get_dia_nombre(self, obj):
        return obj.dia_rutina.get_dia_semana_display() if obj.dia_rutina else None

    class Meta:
        model  = RegistroEntrenamiento
        fields = ['id', 'dia_rutina', 'dia_nombre', 'fecha', 'duracion_segundos', 'ejercicios_completados', 'notas']
        read_only_fields = ['fecha']
