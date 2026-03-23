from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import ObjetivoUsuario, Rol, Sexo, Usuario


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
    rol  = RolSerializer(read_only=True)
    sexo = SexoSerializer(read_only=True)

    class Meta:
        model  = Usuario
        fields = ['id', 'email', 'nombre', 'rol', 'sexo', 'fecha_nacimiento', 'estatura',
                  'frecuencia_peso', 'nacionalidad', 'preferencias_alimentarias', 'date_joined']


class CustomTokenSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        data['usuario'] = UsuarioSerializer(self.user).data
        return data


class ObjetivoUsuarioSerializer(serializers.ModelSerializer):
    class Meta:
        model  = ObjetivoUsuario
        fields = ['id', 'objetivo', 'peso_inicial', 'peso_objetivo',
                  'nivel_actividad', 'dias_entrenamiento', 'duracion_sesion',
                  'fecha_inicio', 'activo']
        read_only_fields = ['fecha_inicio', 'activo']
