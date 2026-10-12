from django.db.models import ProtectedError
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from .fotos import agregar_foto, eliminar_foto
from .models import FotoProgreso, Medicion, RegistroEntrenamiento
from .serializers import (FotoProgresoSerializer, FotoSubirSerializer, MedicionSerializer,
                          RegistroEntrenamientoSerializer)


class MedicionListCreateView(generics.ListCreateAPIView):
    serializer_class = MedicionSerializer

    def get_queryset(self):
        return (Medicion.objects.filter(usuario=self.request.user)
                .select_related('proceso_iniciado').prefetch_related('fotos'))

    def perform_create(self, serializer):
        talla = serializer.validated_data.get('talla_cm') or self.request.user.estatura
        serializer.save(usuario=self.request.user, talla_cm=talla)


class MedicionDetailView(generics.RetrieveDestroyAPIView):
    """Las mediciones no se editan. Se pueden borrar, salvo la inicial de un proceso."""
    serializer_class = MedicionSerializer

    def get_queryset(self):
        return Medicion.objects.filter(usuario=self.request.user)

    def destroy(self, request, *args, **kwargs):
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            return Response(
                {'detail': 'Es la medición inicial de un proceso y no se puede eliminar.'},
                status=status.HTTP_409_CONFLICT,
            )


class MedicionFotosView(APIView):
    """Agrega una foto (una por pose) a una medición del usuario."""
    parser_classes = [MultiPartParser]

    def post(self, request, pk):
        medicion = get_object_or_404(
            Medicion.objects.select_related('proceso_iniciado'), pk=pk, usuario=request.user)
        datos = FotoSubirSerializer(data=request.data)
        datos.is_valid(raise_exception=True)
        foto = agregar_foto(medicion, datos.validated_data['pose'], datos.validated_data['imagen'])
        return Response(FotoProgresoSerializer(foto).data, status=status.HTTP_201_CREATED)


class FotoProgresoView(APIView):
    """Entrega el archivo de la foto solo a su dueño (?tamano=mini para la miniatura)."""

    def _foto(self, request, pk):
        return get_object_or_404(
            FotoProgreso.objects.select_related('medicion__proceso_iniciado'),
            pk=pk, medicion__usuario=request.user)

    def get(self, request, pk):
        foto = self._foto(request, pk)
        archivo = foto.miniatura if request.query_params.get('tamano') == 'mini' else foto.imagen
        respuesta = FileResponse(archivo.open('rb'), content_type='image/jpeg')
        respuesta['Cache-Control'] = 'private, max-age=31536000, immutable'
        return respuesta

    def delete(self, request, pk):
        eliminar_foto(self._foto(request, pk))
        return Response(status=status.HTTP_204_NO_CONTENT)


class RegistroEntrenamientoView(generics.ListCreateAPIView):
    serializer_class = RegistroEntrenamientoSerializer

    def get_queryset(self):
        return RegistroEntrenamiento.objects.filter(usuario=self.request.user).order_by('-fecha', '-id')

    def perform_create(self, serializer):
        serializer.save(usuario=self.request.user)


class RegistroEntrenamientoDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = RegistroEntrenamientoSerializer

    def get_queryset(self):
        return RegistroEntrenamiento.objects.filter(usuario=self.request.user)
