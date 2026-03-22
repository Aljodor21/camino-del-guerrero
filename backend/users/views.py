from rest_framework import generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from .models import ObjetivoUsuario
from .serializers import (CustomTokenSerializer, ObjetivoUsuarioSerializer,
                           RegistroSerializer, UsuarioSerializer)


class RegistroView(generics.CreateAPIView):
    serializer_class = RegistroSerializer
    permission_classes = [permissions.AllowAny]


class LoginView(TokenObtainPairView):
    serializer_class = CustomTokenSerializer


class PerfilView(APIView):
    def get(self, request):
        return Response(UsuarioSerializer(request.user).data)


class ObjetivoUsuarioView(generics.ListCreateAPIView):
    serializer_class = ObjetivoUsuarioSerializer

    def get_queryset(self):
        return ObjetivoUsuario.objects.filter(usuario=self.request.user)

    def perform_create(self, serializer):
        ObjetivoUsuario.objects.filter(usuario=self.request.user).update(activo=False)
        serializer.save(usuario=self.request.user)
