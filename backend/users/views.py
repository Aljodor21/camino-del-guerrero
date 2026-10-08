from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError, InvalidToken

from progress.serializers import MedicionSerializer

from . import procesos
from .models import Proceso, Sexo, Usuario
from .serializers import (CustomTokenSerializer, ProcesoActualizarSerializer,
                          ProcesoCrearSerializer, ProcesoSerializer,
                          RegistroSerializer, SexoSerializer, UsuarioSerializer)


class EsAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and
                    request.user.rol and request.user.rol.nombre == 'admin')


class RegistroView(generics.CreateAPIView):
    serializer_class   = RegistroSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        refresh = RefreshToken.for_user(user)
        return Response({
            'access':   str(refresh.access_token),
            'refresh':  str(refresh),
            'usuario':  UsuarioSerializer(user).data,
        }, status=201)


class LoginView(TokenObtainPairView):
    serializer_class = CustomTokenSerializer


class SafeTokenRefreshView(TokenRefreshView):
    """Devuelve 401 en vez de 500 cuando el usuario del token ya no existe."""
    def post(self, request, *args, **kwargs):
        try:
            return super().post(request, *args, **kwargs)
        except Exception:
            return Response({'detail': 'Token inválido o usuario no encontrado.'},
                            status=status.HTTP_401_UNAUTHORIZED)


class PerfilView(APIView):
    def get(self, request):
        return Response(UsuarioSerializer(request.user).data)

    def patch(self, request):
        serializer = UsuarioSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class ProcesoListCreateView(generics.ListCreateAPIView):
    """Historial de procesos del usuario y creación de uno nuevo."""

    def get_queryset(self):
        return (Proceso.objects.filter(usuario=self.request.user)
                .select_related('medicion_inicial', 'entrenamiento'))

    def get_serializer_class(self):
        return ProcesoCrearSerializer if self.request.method == 'POST' else ProcesoSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        proceso = serializer.save()
        return Response(ProcesoSerializer(proceso).data, status=status.HTTP_201_CREATED)


class ProcesoEstadoView(APIView):
    """El proceso en curso y el programado, si existen."""

    def get(self, request):
        actual = procesos.proceso_actual(request.user)
        programado = procesos.proceso_programado(request.user)
        return Response({
            'actual':     ProcesoSerializer(actual).data if actual else None,
            'programado': ProcesoSerializer(programado).data if programado else None,
        })


class ProcesoDetailView(generics.RetrieveUpdateDestroyAPIView):
    http_method_names = ['get', 'patch', 'delete']

    def get_queryset(self):
        return Proceso.objects.filter(usuario=self.request.user)

    def get_serializer_class(self):
        return ProcesoActualizarSerializer if self.request.method == 'PATCH' else ProcesoSerializer

    def update(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_object(), data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        proceso = serializer.save()
        return Response(ProcesoSerializer(proceso).data)

    def perform_destroy(self, instance):
        procesos.cancelar_programado(instance)


class ProcesoMedicionInicialView(APIView):
    """Registra la medición inicial de un proceso que inició sin ella (programado)."""

    def post(self, request, pk):
        proceso = generics.get_object_or_404(Proceso, pk=pk, usuario=request.user)
        serializer = MedicionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        proceso = procesos.registrar_medicion_inicial(proceso, serializer.validated_data)
        return Response(ProcesoSerializer(proceso).data, status=status.HTTP_201_CREATED)


class SexoListView(generics.ListAPIView):
    queryset           = Sexo.objects.all()
    serializer_class   = SexoSerializer
    permission_classes = [permissions.AllowAny]


class AdminUsuariosView(generics.ListAPIView):
    serializer_class   = UsuarioSerializer
    permission_classes = [EsAdmin]

    def get_queryset(self):
        return Usuario.objects.exclude(rol__nombre='admin').select_related('rol', 'sexo').order_by('-date_joined')


class AdminUsuarioDeleteView(generics.DestroyAPIView):
    permission_classes = [EsAdmin]

    def get_queryset(self):
        return Usuario.objects.exclude(rol__nombre='admin')
