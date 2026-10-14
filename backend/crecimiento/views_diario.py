"""La API del diario de gastos: todo cuelga del proyecto (`/diario/<proyecto>/…`)."""
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.exceptions import ReglaNegocioError

from . import diario
from .models import CLASES_GASTO, GastoHormiga, GastoNoMensual, Proyecto
from .serializers import _calcular_avance


def _diario(request, pk):
    return get_object_or_404(Proyecto, pk=pk, tipo='diario_gastos', proceso__area__usuario=request.user)


def _responder(proyecto, mes, codigo=status.HTTP_200_OK):
    _calcular_avance(proyecto)
    return Response(diario.estado_del_mes(proyecto, mes), status=codigo)


class MesView(APIView):
    """GET: todo el diario de un mes (`?mes=2026-10`). PUT: guarda la relación de gastos de ese mes."""

    def get(self, request, pk):
        return _responder(_diario(request, pk), diario.leer_mes(request.query_params.get('mes')))

    def put(self, request, pk):
        proyecto = _diario(request, pk)
        mes = diario.leer_mes(request.query_params.get('mes'))
        rubros = request.data.get('rubros')
        if not isinstance(rubros, list):
            raise ReglaNegocioError('Manda la lista de gastos del mes.')
        diario.guardar_rubros(proyecto, mes, rubros)
        return _responder(proyecto, mes)


class GastoSerializer(serializers.Serializer):
    fecha       = serializers.DateField(required=False)
    valor       = serializers.IntegerField(min_value=1, max_value=10**12)
    descripcion = serializers.CharField(max_length=120)
    categoria   = serializers.ChoiceField(choices=[c for c, _, _ in diario.CATEGORIAS])
    clase       = serializers.ChoiceField(choices=CLASES_GASTO)


class GastosView(APIView):
    """Anotar un gasto de verdad (el diario sincero)."""

    def post(self, request, pk):
        proyecto = _diario(request, pk)
        datos = GastoSerializer(data=request.data)
        datos.is_valid(raise_exception=True)
        d = datos.validated_data
        fecha = d.get('fecha') or timezone.localdate()
        diario.anotar_gasto(proyecto, fecha, d['valor'], d['descripcion'], d['categoria'], d['clase'])
        return _responder(proyecto, diario.mes_de(fecha), status.HTTP_201_CREATED)


class GastoView(APIView):
    def delete(self, request, pk, gasto):
        proyecto = _diario(request, pk)
        g = get_object_or_404(proyecto.gastos, pk=gasto)
        mes = diario.mes_de(g.fecha)
        diario.borrar_gasto(g)
        return _responder(proyecto, mes)


class SinGastoView(APIView):
    """«Hoy no gasté» (o un día de la última semana)."""

    def post(self, request, pk):
        proyecto = _diario(request, pk)
        fecha = parse_date(str(request.data.get('fecha') or '')) or timezone.localdate()
        diario.marcar_sin_gasto(proyecto, fecha)
        return _responder(proyecto, diario.mes_de(fecha), status.HTTP_201_CREATED)


class NoMensualSerializer(serializers.ModelSerializer):
    class Meta:
        model  = GastoNoMensual
        fields = ['nombre', 'valor', 'periodicidad', 'mes_pago', 'clase']
        extra_kwargs = {'valor': {'min_value': 1, 'max_value': 10**12},
                        'mes_pago': {'min_value': 1, 'max_value': 12}}


class HormigaSerializer(serializers.ModelSerializer):
    class Meta:
        model  = GastoHormiga
        fields = ['nombre', 'valor_dia', 'dias_mes', 'clase']
        extra_kwargs = {'valor_dia': {'min_value': 1, 'max_value': 10**9},
                        'dias_mes': {'min_value': 1, 'max_value': 31}}


def _lista_view(relacion, serializer):
    """POST para crear; PATCH y DELETE con su id. Responde el diario del mes (`?mes=`)."""

    class Lista(APIView):
        def post(self, request, pk, item=None):
            proyecto = _diario(request, pk)
            datos = serializer(data=request.data)
            datos.is_valid(raise_exception=True)
            datos.save(proyecto=proyecto)
            return _responder(proyecto, diario.leer_mes(request.query_params.get('mes')), status.HTTP_201_CREATED)

        def patch(self, request, pk, item=None):
            proyecto = _diario(request, pk)
            datos = serializer(get_object_or_404(getattr(proyecto, relacion), pk=item), data=request.data,
                               partial=True)
            datos.is_valid(raise_exception=True)
            datos.save()
            return _responder(proyecto, diario.leer_mes(request.query_params.get('mes')))

        def delete(self, request, pk, item=None):
            proyecto = _diario(request, pk)
            get_object_or_404(getattr(proyecto, relacion), pk=item).delete()
            return _responder(proyecto, diario.leer_mes(request.query_params.get('mes')))

    return Lista


NoMensualesView = _lista_view('no_mensuales', NoMensualSerializer)
HormigaView = _lista_view('hormiga', HormigaSerializer)
