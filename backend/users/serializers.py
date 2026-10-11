from django.contrib.auth.password_validation import validate_password
from django.utils import timezone
from rest_framework import serializers

from core.exceptions import DatoInmutableError
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from progress.serializers import MedicionSerializer

from . import procesos

from .models import ConfiguracionEntrenamiento, Proceso, Rol, Sexo, Usuario


class RolSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Rol
        fields = ['id', 'nombre']


class SexoSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Sexo
        fields = ['id', 'nombre']


class RegistroSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])
    sexo     = serializers.PrimaryKeyRelatedField(queryset=Sexo.objects.all(), required=False, allow_null=True)

    class Meta:
        model  = Usuario
        fields = ['id', 'email', 'nombre', 'password', 'sexo', 'fecha_nacimiento']

    def create(self, validated_data):
        rol_usuario, _ = Rol.objects.get_or_create(nombre='usuario')
        user = Usuario.objects.create_user(
            username=validated_data['email'],
            email=validated_data['email'],
            nombre=validated_data['nombre'],
            password=validated_data['password'],
            rol=rol_usuario,
            sexo=validated_data.get('sexo'),
            fecha_nacimiento=validated_data.get('fecha_nacimiento'),
        )
        return user


class UsuarioSerializer(serializers.ModelSerializer):
    rol    = RolSerializer(read_only=True)
    sexo   = SexoSerializer(read_only=True)
    sexo_id = serializers.PrimaryKeyRelatedField(
        queryset=Sexo.objects.all(), source='sexo', required=False, allow_null=True, write_only=True
    )

    class Meta:
        model  = Usuario
        fields = ['id', 'email', 'nombre', 'rol', 'sexo', 'sexo_id', 'fecha_nacimiento', 'estatura',
                  'frecuencia_peso', 'nacionalidad', 'region', 'preferencias_alimentarias',
                  'implementos_adicionales', 'date_joined']

    # Lo que se dice al empezar no se cambia: solo lo mueve un administrador.
    DATOS_DE_INICIO = ('nombre', 'sexo', 'fecha_nacimiento', 'estatura', 'nacionalidad', 'region')

    def validate(self, attrs):
        if self.instance is not None and not self.context.get('es_admin'):
            cambiados = [campo for campo in self.DATOS_DE_INICIO
                         if campo in attrs and getattr(self.instance, campo) not in (None, '')
                         and attrs[campo] != getattr(self.instance, campo)]
            if cambiados:
                raise DatoInmutableError(
                    f'Tus datos de inicio no se pueden cambiar ({", ".join(cambiados)}). '
                    'Si hay un error, pídele al administrador que lo corrija.')
        return attrs


class CustomTokenSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        data['usuario'] = UsuarioSerializer(self.user).data
        return data


class ConfiguracionEntrenamientoSerializer(serializers.ModelSerializer):
    class Meta:
        model  = ConfiguracionEntrenamiento
        fields = ['nivel_actividad', 'dias_entrenamiento', 'duracion_sesion', 'enfoque_entrenamiento']


class ProcesoSerializer(serializers.ModelSerializer):
    """Lectura completa de un proceso."""
    objetivo_nombre  = serializers.CharField(source='get_objetivo_display', read_only=True)
    fase_nombre      = serializers.CharField(source='get_fase_display', read_only=True)
    estado           = serializers.CharField(read_only=True)
    medicion_inicial = MedicionSerializer(read_only=True)
    entrenamiento    = serializers.SerializerMethodField()
    plan_terminado   = serializers.SerializerMethodField()

    def get_plan_terminado(self, obj):
        """Llegó la fecha de control: toca preguntar si sigue o cambia."""
        return bool(obj.fecha_fin_plan and obj.fecha_fin_plan <= timezone.localdate())

    class Meta:
        model  = Proceso
        fields = ['id', 'objetivo', 'objetivo_nombre', 'fase', 'fase_nombre', 'peso_objetivo',
                  'incluye_alimentacion', 'incluye_entrenamiento', 'fecha_inicio', 'fecha_fin',
                  'fecha_fin_plan', 'plan_terminado', 'renovaciones', 'estado', 'medicion_inicial',
                  'entrenamiento', 'notas', 'fecha_creacion']

    def get_entrenamiento(self, obj):
        config = getattr(obj, 'entrenamiento', None)
        return ConfiguracionEntrenamientoSerializer(config).data if config else None


class ProcesoCrearSerializer(serializers.ModelSerializer):
    medicion_inicial = MedicionSerializer(required=False, allow_null=True)
    entrenamiento    = ConfiguracionEntrenamientoSerializer(required=False, allow_null=True)

    class Meta:
        model  = Proceso
        fields = ['objetivo', 'fase', 'peso_objetivo', 'incluye_alimentacion', 'incluye_entrenamiento',
                  'fecha_inicio', 'fecha_fin_plan', 'notas', 'medicion_inicial', 'entrenamiento']
        extra_kwargs = {
            'fecha_inicio':  {'required': True},
            'peso_objetivo': {'min_value': 20, 'max_value': 300},
        }

    def validate(self, attrs):
        if not (attrs.get('incluye_alimentacion', True) or attrs.get('incluye_entrenamiento', False)):
            raise serializers.ValidationError('Elige alimentación, entrenamiento o ambos.')
        return attrs

    def create(self, validated_data):
        medicion = validated_data.pop('medicion_inicial', None)
        entrenamiento = validated_data.pop('entrenamiento', None)
        return procesos.crear_proceso(self.context['request'].user, validated_data, medicion, entrenamiento)


class ProcesoActualizarSerializer(serializers.ModelSerializer):
    """Solo lo editable de un proceso. Los datos de inicio no aparecen aquí a propósito."""
    entrenamiento = ConfiguracionEntrenamientoSerializer(required=False)

    class Meta:
        model  = Proceso
        fields = ['peso_objetivo', 'fecha_fin_plan', 'notas', 'incluye_alimentacion', 'incluye_entrenamiento',
                  'entrenamiento']
        extra_kwargs = {'peso_objetivo': {'min_value': 20, 'max_value': 300}}

    def update(self, instance, validated_data):
        entrenamiento = validated_data.pop('entrenamiento', None)
        return procesos.actualizar_proceso(instance, validated_data, entrenamiento)
