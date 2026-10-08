from rest_framework import generics

from core.exceptions import ReglaNegocioError
from users.procesos import proceso_de_referencia

from .models import Recordatorio
from .serializers import RecordatorioSerializer


class RecordatorioListCreateView(generics.ListCreateAPIView):
    serializer_class = RecordatorioSerializer

    def get_queryset(self):
        return Recordatorio.objects.filter(usuario=self.request.user)

    def perform_create(self, serializer):
        usuario = self.request.user
        serializer.save(usuario=usuario, proceso=proceso_de_referencia(usuario))


class RecordatorioDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = RecordatorioSerializer
    http_method_names = ['get', 'patch', 'delete']

    def get_queryset(self):
        return Recordatorio.objects.filter(usuario=self.request.user)

    def perform_destroy(self, instance):
        if instance.automatico:
            raise ReglaNegocioError('Este recordatorio lo maneja la app según tu suplemento.')
        instance.delete()
