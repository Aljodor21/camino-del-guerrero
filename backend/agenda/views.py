from datetime import timedelta

from django.conf import settings
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework import generics, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from auditoria.middleware import datos_del_cliente
from core.exceptions import ReglaNegocioError
from users.procesos import proceso_de_referencia

from . import cumplimiento, fcm, horarios, logros, notificaciones, push, sueno, sugerencias_de_horas
from .models import HorarioDia, Notificacion, Recordatorio, RegistroHabito, SuscripcionPush, TokenCelular
from .serializers import (HabitosSerializer, HorarioDiaSerializer, NotificacionSerializer, RecordatorioSerializer,
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
        # «Esta y las siguientes»: lo que se repitió junto, desde esta fecha en adelante.
        if instance.serie and self.request.query_params.get('siguientes') == '1':
            Recordatorio.objects.filter(usuario=instance.usuario, serie=instance.serie,
                                        fecha__gte=instance.fecha).delete()
            return
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


class ProximosAvisosView(APIView):
    """Lo que viene en los próximos días (máx. 14), para programarlo en el celular."""

    def get(self, request):
        dias = request.query_params.get('dias') or '7'
        if not dias.isdigit() or not 1 <= int(dias) <= 14:
            raise ReglaNegocioError('Pide entre 1 y 14 días.')
        return Response(notificaciones.proximos(request.user, int(dias)))


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


class CumplimientoView(APIView):
    """Cumplimiento global entre dos fechas (por defecto, hoy)."""

    def get(self, request):
        hoy = timezone.localdate()
        hasta = parse_date(request.query_params.get('hasta') or '') or hoy
        desde = parse_date(request.query_params.get('desde') or '') or hasta
        if desde > hasta:
            raise ReglaNegocioError('La fecha inicial va antes de la final.')
        return Response(cumplimiento.calcular(request.user, desde, hasta))


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
        return Response({'clave': settings.VAPID_PUBLIC_KEY if push.configurado() else None,
                         'en_la_app': push.tiene_la_app(request.user)})

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


class PushCelularView(APIView):
    """La app instalada. GET: si el servidor manda por Firebase. POST/DELETE: registrar o quitar este celular."""

    def get(self, request):
        return Response({'disponible': fcm.configurado()})

    def post(self, request):
        token = request.data.get('token')
        if not isinstance(token, str) or not 20 <= len(token) <= 400:
            raise ReglaNegocioError('Falta el identificador de este celular.')
        cliente = datos_del_cliente(request._request)
        TokenCelular.objects.update_or_create(
            token=token, defaults={'usuario': request.user, 'dispositivo': cliente['dispositivo'],
                                   'version_app': cliente['version_app'], 'ultimo_uso': timezone.now(),
                                   'con_botones': request.data.get('botones') is True})
        return Response(status=status.HTTP_204_NO_CONTENT)

    def delete(self, request):
        TokenCelular.objects.filter(usuario=request.user, token=request.data.get('token')).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class PushCelularPruebaView(APIView):
    """Manda una notificación de prueba a los celulares de la persona."""

    def post(self, request):
        if not fcm.configurado():
            raise ReglaNegocioError('El servidor aún no tiene activado Firebase.')
        if not request.user.tokens_celular.exists():
            raise ReglaNegocioError('Este celular aún no está registrado. Activa las notificaciones primero.')
        return Response({'enviadas': fcm.enviar_prueba(request.user)})


class LogrosView(APIView):
    """La racha, los hitos y cuáles son nuevos."""

    def get(self, request):
        return Response(logros.logros(request.user))


class HitosVistosView(APIView):
    """La persona ya vio celebrar estos hitos."""

    def post(self, request):
        claves = request.data.get('ids')
        if not isinstance(claves, list) or len(claves) > 60 or not all(isinstance(c, str) for c in claves):
            raise ReglaNegocioError('Indica qué hitos viste.')
        return Response({'vistos': logros.marcar_vistos(request.user, claves)})


class CapituloView(APIView):
    """La semana (de lunes a domingo): `lunes` o, si no, la semana de hoy."""

    def get(self, request):
        lunes = parse_date(request.query_params.get('lunes') or '') or logros.lunes_de(timezone.localdate())
        return Response(logros.capitulo(request.user, lunes))


class RegistrarLevantarView(APIView):
    """«Me levanté»: anota la hora de ahora (desde 2 h antes hasta 2 h después de la prevista). Solo si no se
    anotó a tiempo se acepta `hora`, una vez: es la única vez que se dice una hora."""

    def post(self, request):
        registro = notificaciones.registrar_levantar(request.user, request.data.get('hora'))
        return Response(RegistroHabitoSerializer(registro).data, status=status.HTTP_201_CREATED)


class RegistrarDormirView(APIView):
    """«Me acosté»: anota la hora sin esperar el aviso."""

    def post(self, request):
        registro = notificaciones.registrar_dormir(request.user)
        return Response(RegistroHabitoSerializer(registro).data, status=status.HTTP_201_CREATED)


class IniciarSiestaView(APIView):
    def post(self, request):
        registro = notificaciones.iniciar_siesta(request.user)
        return Response(RegistroHabitoSerializer(registro).data, status=status.HTTP_201_CREATED)


class TerminarSiestaView(APIView):
    def post(self, request):
        registro = notificaciones.terminar_siesta(request.user, request.data.get('hora'))
        return Response(RegistroHabitoSerializer(registro).data, status=status.HTTP_201_CREATED)


class SuenoView(APIView):
    """Cuánto se durmió entre dos fechas (por defecto, los últimos 7 días)."""

    def get(self, request):
        hasta = parse_date(request.query_params.get('hasta') or '') or timezone.localdate()
        desde = parse_date(request.query_params.get('desde') or '') or hasta - timedelta(days=6)
        if desde > hasta or (hasta - desde).days > 92:
            raise ReglaNegocioError('Pide un periodo válido de hasta un trimestre.')
        return Response(sueno.resumen(request.user, desde, hasta))


class HorarioDiaView(APIView):
    """Las horas de levantarse y acostarse de un solo día («mañana me levanto a las 5»)."""

    def _respuesta(self, usuario, fecha):
        horas = horarios.horas_de(notificaciones.habitos_de(usuario), fecha)
        return {'fecha': fecha, 'levantarse': horas['levantarse'], 'dormir': horas['dormir'],
                'personalizado': horas['personalizado']}

    def put(self, request, fecha):
        dia = parse_date(fecha)
        hoy = timezone.localdate()
        if dia is None or not hoy - timedelta(days=7) <= dia <= hoy + timedelta(days=60):
            raise ReglaNegocioError('Esa fecha no se puede cambiar: elige entre la última semana y los próximos dos meses.')
        datos = HorarioDiaSerializer(data=request.data)
        datos.is_valid(raise_exception=True)
        valores = datos.validated_data
        if not valores.get('hora_levantarse') and not valores.get('hora_dormir'):
            HorarioDia.objects.filter(usuario=request.user, fecha=dia).delete()
        else:
            HorarioDia.objects.update_or_create(usuario=request.user, fecha=dia, defaults={
                'hora_levantarse': valores.get('hora_levantarse'), 'hora_dormir': valores.get('hora_dormir')})
        return Response(self._respuesta(request.user, dia))

    def delete(self, request, fecha):
        dia = parse_date(fecha)
        if dia is None:
            raise ReglaNegocioError('Fecha no válida.')
        HorarioDia.objects.filter(usuario=request.user, fecha=dia).delete()
        return Response(self._respuesta(request.user, dia))


class SugerenciasView(APIView):
    """Horas que podrían ajustarse según cómo usa la persona la app (solo propone; ella decide)."""

    def get(self, request):
        return Response(sugerencias_de_horas.de_horas(request.user))
