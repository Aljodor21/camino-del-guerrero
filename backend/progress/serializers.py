from rest_framework import serializers

from .models import RegistroEntrenamiento, RegistroPeso


class RegistroPesoSerializer(serializers.ModelSerializer):
    class Meta:
        model = RegistroPeso
        fields = ['id', 'peso_kg', 'fecha', 'nota']
        read_only_fields = ['fecha']


class RegistroEntrenamientoSerializer(serializers.ModelSerializer):
    class Meta:
        model = RegistroEntrenamiento
        fields = ['id', 'rutina', 'fecha', 'rounds', 'duracion_minutos', 'notas']
        read_only_fields = ['fecha']
