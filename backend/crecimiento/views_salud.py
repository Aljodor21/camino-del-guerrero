"""La API de Salud (protocolo Fadiman y otros suplementos): todo cuelga del proyecto (`/salud/<proyecto>/…`) y cada
respuesta trae el estado entero."""
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from . import salud
from .models import Proyecto
from .serializers import _calcular_avance


def _proyecto(request, pk):
    return get_object_or_404(Proyecto, pk=pk, tipo__in=('fadiman', 'otros_suplementos'),
                             proceso__area__usuario=request.user)


def _responder(proyecto, codigo=status.HTTP_200_OK):
    _calcular_avance(proyecto)
    return Response(salud.estado(proyecto), status=codigo)


class TomaSerializer(serializers.Serializer):
    fecha    = serializers.DateField(required=False)
    clase    = serializers.ChoiceField(choices=['dosis', 'observacion'], default='dosis')
    nombre   = serializers.CharField(max_length=60, required=False, allow_blank=True)
    cantidad = serializers.CharField(max_length=40, required=False, allow_blank=True)
    animo    = serializers.IntegerField(required=False, allow_null=True)
    energia  = serializers.IntegerField(required=False, allow_null=True)
    nota     = serializers.CharField(max_length=300, required=False, allow_blank=True)
    plan     = serializers.CharField(max_length=20, required=False, allow_blank=True)


class SaludView(APIView):
    def get(self, request, pk):
        return _responder(_proyecto(request, pk))


class TomasView(APIView):
    """Anotar una toma (o, en el protocolo, cómo se sintió)."""

    def post(self, request, pk):
        proyecto = _proyecto(request, pk)
        datos = TomaSerializer(data=request.data)
        datos.is_valid(raise_exception=True)
        d = datos.validated_data
        salud.anotar(proyecto, d.pop('fecha', None) or timezone.localdate(), **d)
        return _responder(proyecto, status.HTTP_201_CREATED)


class TomaView(APIView):
    def delete(self, request, pk, toma):
        proyecto = _proyecto(request, pk)
        salud.borrar(get_object_or_404(proyecto.tomas_salud, pk=toma))
        return _responder(proyecto)
