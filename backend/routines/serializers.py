from rest_framework import serializers

from .models import (DiaRutina, EjercicioDia, Ejercicio,
                     EjercicioImplemento, Implemento, Rutina, UsuarioImplemento)


class ImplementoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Implemento
        fields = ['id', 'nombre', 'descripcion', 'categoria', 'es_sin_implemento']


class UsuarioImplementoSerializer(serializers.ModelSerializer):
    implemento = ImplementoSerializer(read_only=True)
    implemento_id = serializers.PrimaryKeyRelatedField(
        queryset=Implemento.objects.all(), source='implemento', write_only=True
    )

    class Meta:
        model = UsuarioImplemento
        fields = ['id', 'implemento', 'implemento_id']


class EjercicioSerializer(serializers.ModelSerializer):
    implementos = ImplementoSerializer(many=True, read_only=True)

    class Meta:
        model = Ejercicio
        fields = ['id', 'nombre', 'descripcion', 'url_youtube', 'requiere_implemento', 'implementos']


class EjercicioVideoSerializer(serializers.ModelSerializer):
    """Solo para que el admin edite el video de un ejercicio."""
    class Meta:
        model = Ejercicio
        fields = ['id', 'url_youtube']


class EjercicioDiaSerializer(serializers.ModelSerializer):
    ejercicio = EjercicioSerializer(read_only=True)

    class Meta:
        model = EjercicioDia
        fields = ['id', 'ejercicio', 'series', 'repeticiones', 'duracion_segundos', 'orden']


class DiaRutinaSerializer(serializers.ModelSerializer):
    ejercicios = EjercicioDiaSerializer(many=True, read_only=True)
    dia_nombre = serializers.CharField(source='get_dia_semana_display', read_only=True)

    class Meta:
        model = DiaRutina
        fields = ['id', 'dia_semana', 'dia_nombre', 'ejercicios']


class RutinaSerializer(serializers.ModelSerializer):
    dias = DiaRutinaSerializer(many=True, read_only=True)

    class Meta:
        model = Rutina
        fields = ['id', 'nombre', 'descripcion', 'fecha_generacion', 'activa', 'dias']
