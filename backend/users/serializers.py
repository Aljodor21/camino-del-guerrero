from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import ObjetivoUsuario, Rol, Usuario


class RolSerializer(serializers.ModelSerializer):
    class Meta:
        model = Rol
        fields = ['id', 'nombre', 'descripcion']


class RegistroSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])

    class Meta:
        model = Usuario
        fields = ['id', 'email', 'nombre', 'password']

    def create(self, validated_data):
        rol_usuario, _ = Rol.objects.get_or_create(nombre='usuario')
        user = Usuario.objects.create_user(
            username=validated_data['email'],
            email=validated_data['email'],
            nombre=validated_data['nombre'],
            password=validated_data['password'],
            rol=rol_usuario,
        )
        return user


class UsuarioSerializer(serializers.ModelSerializer):
    rol = RolSerializer(read_only=True)

    class Meta:
        model = Usuario
        fields = ['id', 'email', 'nombre', 'rol', 'frecuencia_peso', 'date_joined']


class CustomTokenSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        data['usuario'] = UsuarioSerializer(self.user).data
        return data


class ObjetivoUsuarioSerializer(serializers.ModelSerializer):
    class Meta:
        model = ObjetivoUsuario
        fields = ['id', 'objetivo', 'peso_inicial', 'peso_objetivo', 'fecha_inicio', 'activo']
        read_only_fields = ['fecha_inicio', 'activo']
