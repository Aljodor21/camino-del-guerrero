from django.utils import timezone
from rest_framework import serializers

from .fotos import admite_fotos, limite_fotos
from .models import FotoProgreso, Medicion, RegistroEntrenamiento

PERIMETROS = ('cintura_cm', 'abdomen_cm', 'cadera_cm', 'brazo_cm', 'muslo_cm', 'pierna_cm')
PLIEGUES = (
    'pliegue_triceps_mm', 'pliegue_biceps_mm', 'pliegue_subescapular_mm', 'pliegue_supraespinal_mm',
    'pliegue_abdominal_mm', 'pliegue_muslo_mm', 'pliegue_pierna_mm', 'pliegue_cresta_iliaca_mm',
)


class FotoProgresoSerializer(serializers.ModelSerializer):
    class Meta:
        model  = FotoProgreso
        fields = ['id', 'pose', 'ancho', 'alto']


class FotoSubirSerializer(serializers.Serializer):
    pose   = serializers.ChoiceField(choices=FotoProgreso.POSES)
    imagen = serializers.FileField()


class MedicionSerializer(serializers.ModelSerializer):
    imc          = serializers.FloatField(read_only=True)
    es_inicial   = serializers.SerializerMethodField()
    fotos        = FotoProgresoSerializer(many=True, read_only=True)
    admite_fotos = serializers.SerializerMethodField()
    fotos_hasta  = serializers.SerializerMethodField()

    class Meta:
        model  = Medicion
        fields = ['id', 'fecha', 'origen', 'peso_kg', 'talla_cm', *PERIMETROS, *PLIEGUES,
                  'nota', 'imc', 'es_inicial', 'fotos', 'admite_fotos', 'fotos_hasta']
        extra_kwargs = {
            'fecha':    {'required': False},
            'peso_kg':  {'min_value': 20, 'max_value': 300},
            'talla_cm': {'min_value': 100, 'max_value': 250},
            **{c: {'min_value': 10, 'max_value': 250} for c in PERIMETROS},
            **{c: {'min_value': 1, 'max_value': 80} for c in PLIEGUES},
        }

    def get_es_inicial(self, obj):
        return hasattr(obj, 'proceso_iniciado')

    def get_admite_fotos(self, obj):
        return admite_fotos(obj)

    def get_fotos_hasta(self, obj):
        return limite_fotos(obj)

    def validate_fecha(self, fecha):
        if fecha > timezone.localdate():
            raise serializers.ValidationError('La fecha no puede estar en el futuro.')
        return fecha


class RegistroEntrenamientoSerializer(serializers.ModelSerializer):
    dia_nombre = serializers.SerializerMethodField()

    def get_dia_nombre(self, obj):
        return obj.dia_rutina.get_dia_semana_display() if obj.dia_rutina else None

    class Meta:
        model  = RegistroEntrenamiento
        fields = ['id', 'dia_rutina', 'dia_nombre', 'fecha', 'duracion_segundos', 'ejercicios_completados', 'notas']
        read_only_fields = ['fecha']
