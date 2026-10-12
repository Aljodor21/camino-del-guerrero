from django.utils.dateparse import parse_date
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError, InvalidToken

from core.exceptions import ReglaNegocioError
from progress.serializers import MedicionSerializer

from . import correos, procesos, recuperacion
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
        correos.enviar_bienvenida(user)
        refresh = RefreshToken.for_user(user)
        return Response({
            'access':   str(refresh.access_token),
            'refresh':  str(refresh),
            'usuario':  UsuarioSerializer(user).data,
        }, status=201)


class RecuperarClaveView(APIView):
    """Pide recuperar la clave: llega un correo con el usuario y un enlace. Siempre responde igual."""
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'recuperar'

    def post(self, request):
        email = request.data.get('email')
        if not isinstance(email, str) or '@' not in email:
            raise ReglaNegocioError('Escribe el correo con el que te registraste.')
        recuperacion.enviar(email, request.data.get('dispositivo'))
        return Response({'detail': 'Si ese correo tiene cuenta, te enviamos tu usuario y un enlace para crear una clave nueva.'})


class RestablecerClaveView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'recuperar'

    def post(self, request):
        datos = request.data
        recuperacion.restablecer(str(datos.get('token', '')), datos.get('dispositivo'),
                                 str(datos.get('password', '')))
        return Response({'detail': 'Listo, ya puedes entrar con tu clave nueva.'})


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
        """Un proceso programado detrás de uno en curso se cancela. Si es el único (en curso o
        programado), se borra todo lo de la persona menos sus datos personales."""
        if instance.estado == 'programado' and procesos.proceso_actual(instance.usuario):
            procesos.cancelar_programado(instance)
        else:
            procesos.reiniciar(instance.usuario)


class ProcesoQuitarModuloView(APIView):
    """Quita la alimentación o el entrenamiento y borra lo que se armó con él."""

    def post(self, request, pk):
        proceso = generics.get_object_or_404(Proceso, pk=pk, usuario=request.user)
        procesos.quitar_modulo(proceso, request.data.get('modulo'))
        proceso.refresh_from_db()
        return Response(ProcesoSerializer(proceso).data)


class ProcesoRenovarView(APIView):
    """Al llegar el control: seguir con el proceso en otro periodo (otra fecha o sin definir)."""

    def post(self, request, pk):
        proceso = generics.get_object_or_404(Proceso, pk=pk, usuario=request.user)
        valor = request.data.get('fecha_fin_plan')
        fecha = parse_date(valor) if valor else None
        if valor and fecha is None:
            raise ReglaNegocioError('La fecha no es válida.')
        proceso = procesos.renovar(proceso, fecha)
        return Response(ProcesoSerializer(proceso).data)


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


class AdminUsuarioDeleteView(generics.RetrieveUpdateDestroyAPIView):
    """El administrador es el único que corrige los datos de inicio de una persona."""
    permission_classes = [EsAdmin]
    serializer_class   = UsuarioSerializer
    http_method_names  = ['get', 'patch', 'delete']

    def get_serializer_context(self):
        return {**super().get_serializer_context(), 'es_admin': True}

    def get_queryset(self):
        return Usuario.objects.exclude(rol__nombre='admin')
