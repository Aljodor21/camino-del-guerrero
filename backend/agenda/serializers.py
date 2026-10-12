from datetime import timedelta

from django.utils import timezone
from rest_framework import serializers

from . import notificaciones
from .models import Habitos, Notificacion, Recordatorio, RegistroHabito

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
        # Se marca como hecho cuando llega su fecha, no antes.
        if attrs.get('completado'):
            fecha = attrs.get('fecha') or getattr(self.instance, 'fecha', None)
            if fecha and fecha > timezone.localdate():
                raise serializers.ValidationError('Todavía no llega la fecha: se puede marcar como hecho ese día.')
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


class HabitosSerializer(serializers.ModelSerializer):
    vasos_meta = serializers.SerializerMethodField()

    class Meta:
        model  = Habitos
        fields = ['agua_ml', 'vaso_ml', 'vasos_meta', 'hora_levantarse', 'hora_dormir', 'hora_entreno', 'avisos_apagados']
        extra_kwargs = {'agua_ml': {'min_value': 250, 'max_value': 8000},
                        'vaso_ml': {'min_value': 50, 'max_value': 1500}}

    def get_vasos_meta(self, habitos):
        return notificaciones.vasos_meta(habitos)

    def validate_avisos_apagados(self, apagados):
        tipos = dict(Notificacion.TIPOS)
        if not isinstance(apagados, list) or any(t not in tipos for t in apagados):
            raise serializers.ValidationError('Tipo de aviso desconocido.')
        return sorted(set(apagados))

    def validate(self, datos):
        levantarse = datos.get('hora_levantarse', getattr(self.instance, 'hora_levantarse', None))
        dormir = datos.get('hora_dormir', getattr(self.instance, 'hora_dormir', None))
        if levantarse and dormir and levantarse == dormir:
            raise serializers.ValidationError({'hora_dormir': 'No puede ser la misma hora en que te levantas.'})
        return datos


class NotificacionSerializer(serializers.ModelSerializer):
    accion = serializers.SerializerMethodField()

    class Meta:
        model  = Notificacion
        fields = ['id', 'tipo', 'fecha', 'programada_para', 'titulo', 'cuerpo', 'accion', 'suplemento',
                  'recordatorio', 'datos']
        read_only_fields = fields

    def get_accion(self, n):
        return notificaciones.accion_de(n)


class RegistroHabitoSerializer(serializers.ModelSerializer):
    class Meta:
        model  = RegistroHabito
        fields = ['id', 'tipo', 'fecha', 'momento', 'cantidad', 'ml', 'suplemento', 'tiempo']
        read_only_fields = fields


class SuscripcionPushSerializer(serializers.Serializer):
    endpoint = serializers.URLField(max_length=600)
    keys     = serializers.DictField(child=serializers.CharField(max_length=200))

    def validate_endpoint(self, endpoint):
        if not endpoint.startswith('https://'):
            raise serializers.ValidationError('La suscripción debe ser https.')
        return endpoint

    def validate_keys(self, keys):
        if not keys.get('p256dh') or not keys.get('auth'):
            raise serializers.ValidationError('Faltan las llaves de la suscripción.')
        return keys
