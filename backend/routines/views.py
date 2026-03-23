from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Ejercicio, Implemento, Recomendacion, Rutina, UsuarioImplemento
from .serializers import (EjercicioSerializer, EjercicioVideoSerializer,
                           ImplementoSerializer, RecomendacionSerializer,
                           RutinaSerializer, UsuarioImplementoSerializer)


class IsAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.rol and request.user.rol.nombre == 'admin')


class ImplementoListCreateView(generics.ListCreateAPIView):
    queryset = Implemento.objects.all()
    serializer_class = ImplementoSerializer

    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsAdmin()]
        return [permissions.IsAuthenticated()]


class ImplementoDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Implemento.objects.all()
    serializer_class = ImplementoSerializer
    permission_classes = [IsAdmin]


class MisImplementosView(generics.ListCreateAPIView):
    serializer_class = UsuarioImplementoSerializer

    def get_queryset(self):
        return UsuarioImplemento.objects.filter(usuario=self.request.user)

    def perform_create(self, serializer):
        serializer.save(usuario=self.request.user)


class MisImplementosDeleteView(generics.DestroyAPIView):
    serializer_class = UsuarioImplementoSerializer

    def get_queryset(self):
        return UsuarioImplemento.objects.filter(usuario=self.request.user)


class EjercicioListView(generics.ListAPIView):
    queryset = Ejercicio.objects.prefetch_related('implementos').all()
    serializer_class = EjercicioSerializer
    permission_classes = [IsAdmin]


class EjercicioVideoUpdateView(generics.UpdateAPIView):
    queryset = Ejercicio.objects.all()
    serializer_class = EjercicioVideoSerializer
    permission_classes = [IsAdmin]
    http_method_names = ['patch']


class RecomendacionListView(generics.ListAPIView):
    """Usuarios autenticados — solo las activas."""
    serializer_class = RecomendacionSerializer
    queryset = Recomendacion.objects.filter(activa=True)


class RecomendacionAdminListCreateView(generics.ListCreateAPIView):
    """Admin — lista todas (activas e inactivas) y crea nuevas."""
    serializer_class = RecomendacionSerializer
    permission_classes = [IsAdmin]
    queryset = Recomendacion.objects.all()


class RecomendacionAdminDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Admin — edita y elimina."""
    serializer_class = RecomendacionSerializer
    permission_classes = [IsAdmin]
    queryset = Recomendacion.objects.all()


class MiRutinaView(APIView):
    def get(self, request):
        try:
            rutina = Rutina.objects.get(usuario=request.user)
            return Response(RutinaSerializer(rutina).data)
        except Rutina.DoesNotExist:
            return Response({'detail': 'No tienes rutina generada aún.'}, status=status.HTTP_404_NOT_FOUND)
