from rest_framework import generics

from .models import RegistroEntrenamiento, RegistroPeso
from .serializers import RegistroEntrenamientoSerializer, RegistroPesoSerializer


class RegistroPesoView(generics.ListCreateAPIView):
    serializer_class = RegistroPesoSerializer

    def get_queryset(self):
        return RegistroPeso.objects.filter(usuario=self.request.user)

    def perform_create(self, serializer):
        serializer.save(usuario=self.request.user)


class RegistroEntrenamientoView(generics.ListCreateAPIView):
    serializer_class = RegistroEntrenamientoSerializer

    def get_queryset(self):
        return RegistroEntrenamiento.objects.filter(usuario=self.request.user)

    def perform_create(self, serializer):
        serializer.save(usuario=self.request.user)


class RegistroEntrenamientoDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = RegistroEntrenamientoSerializer

    def get_queryset(self):
        return RegistroEntrenamiento.objects.filter(usuario=self.request.user)
