from rest_framework import generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken

from .models import ObjetivoUsuario, Sexo
from .serializers import (CustomTokenSerializer, ObjetivoUsuarioSerializer,
                           RegistroSerializer, SexoSerializer, UsuarioSerializer)


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


class PerfilView(APIView):
    def get(self, request):
        return Response(UsuarioSerializer(request.user).data)

    def patch(self, request):
        serializer = UsuarioSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class ObjetivoUsuarioView(generics.ListCreateAPIView):
    serializer_class = ObjetivoUsuarioSerializer

    def get_queryset(self):
        return ObjetivoUsuario.objects.filter(usuario=self.request.user)

    def perform_create(self, serializer):
        ObjetivoUsuario.objects.filter(usuario=self.request.user).update(activo=False)
        serializer.save(usuario=self.request.user)


class SexoListView(generics.ListAPIView):
    queryset           = Sexo.objects.all()
    serializer_class   = SexoSerializer
    permission_classes = [permissions.AllowAny]
