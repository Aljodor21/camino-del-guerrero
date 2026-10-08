from datetime import timedelta

from django.utils import timezone
from rest_framework import serializers

from .models import Recordatorio

MAX_DIAS_ADELANTE = 730


class RecordatorioSerializer(serializers.ModelSerializer):
    tipo_nombre = serializers.CharField(source='get_tipo_display', read_only=True)
    completado  = serializers.BooleanField(required=False, write_only=True)
    automatico  = serializers.BooleanField(read_only=True)

    class Meta:
        model  = Recordatorio
        fields = ['id', 'tipo', 'tipo_nombre', 'titulo', 'fecha', 'hora', 'nota', 'avisar_dias_antes',
                  'completado', 'completado_en', 'proceso', 'suplemento', 'motivo', 'automatico']
        read_only_fields = ['completado_en', 'proceso', 'suplemento', 'motivo']
        extra_kwargs = {'avisar_dias_antes': {'min_value': 0, 'max_value': 30}}

    def validate_titulo(self, titulo):
        titulo = titulo.strip()
        if not titulo:
            raise serializers.ValidationError('Escribe un título.')
        return titulo

    def validate_fecha(self, fecha):
        hoy = timezone.localdate()
        cambia = self.instance is None or self.instance.fecha != fecha
        if cambia and fecha < hoy:
            raise serializers.ValidationError('La fecha no puede estar en el pasado.')
        if fecha > hoy + timedelta(days=MAX_DIAS_ADELANTE):
            raise serializers.ValidationError('La fecha puede estar máximo a dos años.')
        return fecha

    def validate(self, attrs):
        # Los sugeridos se resuelven con las acciones de su suplemento, que los recalculan.
        if self.instance is not None and self.instance.automatico:
            raise serializers.ValidationError('Este recordatorio se resuelve desde su suplemento.')
        return attrs

    def _aplicar_completado(self, validated_data):
        completado = validated_data.pop('completado', None)
        if completado is not None:
            validated_data['completado_en'] = timezone.now() if completado else None
        return validated_data

    def create(self, validated_data):
        return super().create(self._aplicar_completado(validated_data))

    def update(self, instance, validated_data):
        return super().update(instance, self._aplicar_completado(validated_data))
