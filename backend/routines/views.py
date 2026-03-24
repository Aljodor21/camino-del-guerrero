import requests as req

from django.conf import settings
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


class EjercicioYoutubeSugerenciasView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request, pk):
        try:
            ejercicio = Ejercicio.objects.get(pk=pk)
        except Ejercicio.DoesNotExist:
            return Response({'detail': 'Ejercicio no encontrado.'}, status=status.HTTP_404_NOT_FOUND)

        api_key = settings.YOUTUBE_API_KEY
        if not api_key:
            return Response({'detail': 'YouTube API key no configurada.'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        query = ejercicio.busqueda_media or ejercicio.nombre
        try:
            resp = req.get(
                'https://www.googleapis.com/youtube/v3/search',
                params={
                    'part': 'snippet',
                    'type': 'video',
                    'maxResults': 6,
                    'q': query,
                    'key': api_key,
                    'relevanceLanguage': 'es',
                    'videoDuration': 'short',
                },
                timeout=10,
            )
            resp.raise_for_status()
            items = resp.json().get('items', [])
            sugerencias = [
                {
                    'video_id': item['id']['videoId'],
                    'titulo': item['snippet']['title'],
                    'canal': item['snippet']['channelTitle'],
                    'thumbnail': item['snippet']['thumbnails']['medium']['url'],
                    'url': f"https://www.youtube.com/watch?v={item['id']['videoId']}",
                }
                for item in items
            ]
            return Response({'query': query, 'sugerencias': sugerencias})
        except Exception as e:
            return Response({'detail': f'Error al consultar YouTube: {str(e)}'}, status=status.HTTP_502_BAD_GATEWAY)


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
