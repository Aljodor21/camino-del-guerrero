from datetime import timedelta

from django.conf import settings
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework import generics, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from core.exceptions import ReglaNegocioError
from users.procesos import proceso_de_referencia

from . import notificaciones, push
from .models import Notificacion, Recordatorio, RegistroHabito, SuscripcionPush
from .serializers import (HabitosSerializer, NotificacionSerializer, RecordatorioSerializer,
                          RegistroHabitoSerializer, SuscripcionPushSerializer)


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


class HabitosView(generics.RetrieveUpdateAPIView):
    serializer_class = HabitosSerializer
    http_method_names = ['get', 'patch']

    def get_object(self):
        return notificaciones.habitos_de(self.request.user)

    def perform_update(self, serializer):
        serializer.save(usuario=self.request.user)


class NotificacionListView(generics.ListAPIView):
    """Los avisos pendientes: solo salen de aquí cuando se confirman."""
    serializer_class = NotificacionSerializer
    pagination_class = None

    def get_queryset(self):
        return notificaciones.pendientes(self.request.user)


class ConfirmarNotificacionView(APIView):
    def post(self, request, pk):
        n = get_object_or_404(Notificacion, pk=pk, usuario=request.user)
        notificaciones.confirmar(n)
        return Response(status=status.HTTP_204_NO_CONTENT)


class ConfirmarNotificacionFirmadaView(APIView):
    """El botón de la notificación del celular: la firma reemplaza la sesión."""
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        token = request.data.get('firma')
        if not isinstance(token, str):
            raise ReglaNegocioError('Falta la firma del aviso.')
        notificaciones.confirmar(notificaciones.desde_firma(token))
        return Response(status=status.HTTP_204_NO_CONTENT)


class HoyView(APIView):
    def get(self, request):
        return Response(notificaciones.resumen_de_hoy(request.user))


class RegistroHabitoListView(generics.ListAPIView):
    serializer_class = RegistroHabitoSerializer

    def get_queryset(self):
        desde = parse_date(self.request.query_params.get('desde') or '') or (
            timezone.localdate() - timedelta(days=30))
        registros = RegistroHabito.objects.filter(usuario=self.request.user, fecha__gte=desde)
        if tipo := self.request.query_params.get('tipo'):
            registros = registros.filter(tipo=tipo)
        return registros


class RegistrarAguaView(APIView):
    def post(self, request):
        registro = notificaciones.registrar_agua(request.user)
        return Response(RegistroHabitoSerializer(registro).data, status=status.HTTP_201_CREATED)


class PushView(APIView):
    """GET: la llave pública (null si el servidor no manda al celular). POST/DELETE: suscribirse."""

    def get(self, request):
        return Response({'clave': settings.VAPID_PUBLIC_KEY if push.configurado() else None})

    def post(self, request):
        datos = SuscripcionPushSerializer(data=request.data)
        datos.is_valid(raise_exception=True)
        d = datos.validated_data
        SuscripcionPush.objects.update_or_create(
            endpoint=d['endpoint'],
            defaults={'usuario': request.user, 'p256dh': d['keys']['p256dh'], 'auth': d['keys']['auth']})
        return Response(status=status.HTTP_204_NO_CONTENT)

    def delete(self, request):
        SuscripcionPush.objects.filter(usuario=request.user, endpoint=request.data.get('endpoint')).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
