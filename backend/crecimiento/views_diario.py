"""La API del diario de gastos: todo cuelga del proyecto (`/diario/<proyecto>/…`) y cada respuesta trae el diario
entero."""
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.exceptions import ReglaNegocioError

from . import diario, tarjetas
from .models import CLASES_GASTO, Proyecto
from .serializers import _calcular_avance


def _diario(request, pk):
    return get_object_or_404(Proyecto, pk=pk, tipo='diario_gastos', proceso__area__usuario=request.user)


def _responder(proyecto, codigo=status.HTTP_200_OK):
    _calcular_avance(proyecto)
    return Response(diario.estado(proyecto), status=codigo)


class DiarioView(APIView):
    """GET: todo el diario. PUT: guarda la lista de gastos (`{rubros: [...]}`)."""

    def get(self, request, pk):
        return _responder(_diario(request, pk))

    def put(self, request, pk):
        proyecto = _diario(request, pk)
        rubros = request.data.get('rubros')
        if not isinstance(rubros, list):
            raise ReglaNegocioError('Manda la lista de gastos.')
        diario.guardar_rubros(proyecto, rubros)
        return _responder(proyecto)


class GastoSerializer(serializers.Serializer):
    fecha       = serializers.DateField(required=False)
    valor       = serializers.IntegerField(min_value=1, max_value=10**12)
    descripcion = serializers.CharField(max_length=120)
    categoria   = serializers.ChoiceField(choices=[c for c, _, _ in diario.CATEGORIAS])
    clase       = serializers.ChoiceField(choices=CLASES_GASTO)
    tarjeta     = serializers.IntegerField(required=False, allow_null=True)
    cuotas      = serializers.IntegerField(required=False, allow_null=True)


class GastosView(APIView):
    """Anotar un gasto de verdad (el registro sincero)."""

    def post(self, request, pk):
        proyecto = _diario(request, pk)
        datos = GastoSerializer(data=request.data)
        datos.is_valid(raise_exception=True)
        d = datos.validated_data
        diario.anotar_gasto(proyecto, d.get('fecha') or timezone.localdate(), d['valor'], d['descripcion'],
                            d['categoria'], d['clase'], d.get('tarjeta'), d.get('cuotas'))
        return _responder(proyecto, status.HTTP_201_CREATED)


class GastoView(APIView):
    """PATCH: lo pasa a otra categoría (`{categoria}`). DELETE: lo borra (solo el mismo día)."""

    def patch(self, request, pk, gasto):
        proyecto = _diario(request, pk)
        diario.cambiar_categoria(get_object_or_404(proyecto.gastos, pk=gasto), request.data.get('categoria'))
        return _responder(proyecto)

    def delete(self, request, pk, gasto):
        proyecto = _diario(request, pk)
        diario.borrar_gasto(get_object_or_404(proyecto.gastos, pk=gasto))
        return _responder(proyecto)


class SinGastoView(APIView):
    """«Hoy no gasté» (o un día de la última semana)."""

    def post(self, request, pk):
        proyecto = _diario(request, pk)
        diario.marcar_sin_gasto(proyecto, parse_date(str(request.data.get('fecha') or '')) or timezone.localdate())
        return _responder(proyecto, status.HTTP_201_CREATED)


class TarjetasView(APIView):
    """Agregar una tarjeta de crédito (`{nombre, ultimos, cupo, dia_corte, dia_pago, avisar}`)."""

    def post(self, request, pk):
        proyecto = _diario(request, pk)
        tarjetas.agregar(proyecto, request.data)
        return _responder(proyecto, status.HTTP_201_CREATED)


class TarjetaView(APIView):
    """PATCH: cambia sus datos. DELETE: la quita (si ya tiene compras, se retira y su historial queda)."""

    def _tarjeta(self, proyecto, tarjeta):
        return get_object_or_404(proyecto.tarjetas, pk=tarjeta, activa=True)

    def patch(self, request, pk, tarjeta):
        proyecto = _diario(request, pk)
        tarjetas.cambiar(self._tarjeta(proyecto, tarjeta), request.data)
        return _responder(proyecto)

    def delete(self, request, pk, tarjeta):
        proyecto = _diario(request, pk)
        tarjetas.quitar(self._tarjeta(proyecto, tarjeta))
        return _responder(proyecto)
