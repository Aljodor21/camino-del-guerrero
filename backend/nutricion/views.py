from datetime import timedelta

from django.db.models import F
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.ai_service import AIService
from core.exceptions import ReglaNegocioError
from users.models import Proceso
from users.procesos import proceso_de_referencia
from routines.models import (DiaRutina, EjercicioDia, Ejercicio,
                              EjercicioImplemento, Rutina)

from . import suplementos
from .models import DiaNutricional, ItemMercado, ItemRecurrente, ListaMercado, PlanNutricional, Suplemento
from .serializers import (ContinuarSerializer, ItemMercadoSerializer, ListaMercadoSerializer,
                          PlanNutricionalSerializer, SuplementoEditarSerializer, SuplementoSerializer)


class MiPlanNutricionalView(APIView):
    def get(self, request):
        try:
            plan = PlanNutricional.objects.get(usuario=request.user)
            return Response(PlanNutricionalSerializer(plan).data)
        except PlanNutricional.DoesNotExist:
            return Response({'detail': 'No tienes plan nutricional generado aún.'}, status=status.HTTP_404_NOT_FOUND)

    def post(self, request):
        proceso = proceso_de_referencia(request.user)
        if not proceso or not proceso.incluye_alimentacion:
            return Response({'detail': 'Tu proceso no incluye alimentación.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            ai = AIService()
            data = ai.generar_plan_nutricional(request.user, proceso)

            PlanNutricional.objects.filter(usuario=request.user).delete()
            # La lista de mercado se armó a partir del plan anterior — al
            # quedar huérfana (plan=null por el SET_NULL) mostraría ingredientes
            # de un plan que ya no existe, así que la borramos también.
            ListaMercado.objects.filter(usuario=request.user).delete()
            plan = PlanNutricional.objects.create(usuario=request.user, proceso=proceso)

            for dia_data in data['dias']:
                DiaNutricional.objects.create(plan=plan, **dia_data)

            return Response(PlanNutricionalSerializer(plan).data, status=status.HTTP_201_CREATED)
        except Exception as e:
            import traceback; traceback.print_exc()
            return Response({'detail': f'Error al generar el plan: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class RechazarComidaView(APIView):
    CAMPOS_VALIDOS = ('desayuno', 'almuerzo', 'cena', 'snacks')

    def post(self, request, pk):
        try:
            dia = DiaNutricional.objects.select_related('plan').get(pk=pk, plan__usuario=request.user)
        except DiaNutricional.DoesNotExist:
            return Response({'detail': 'Día no encontrado.'}, status=status.HTTP_404_NOT_FOUND)

        campo = request.data.get('campo')
        if campo not in self.CAMPOS_VALIDOS:
            return Response({'detail': 'Campo inválido.'}, status=status.HTTP_400_BAD_REQUEST)

        proceso = proceso_de_referencia(request.user)
        if not proceso or not proceso.incluye_alimentacion:
            return Response({'detail': 'Tu proceso no incluye alimentación.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            ai = AIService()
            data = ai.ajustar_plan_nutricional(request.user, proceso, dia.plan, dia, campo)

            plan = dia.plan
            plan.dias.all().delete()
            for dia_data in data['dias']:
                DiaNutricional.objects.create(plan=plan, **dia_data)
            # El ajuste cambió ingredientes del plan — la lista de mercado
            # vieja quedaría desactualizada, así que se borra también.
            ListaMercado.objects.filter(usuario=request.user).delete()

            return Response(PlanNutricionalSerializer(plan).data)
        except Exception as e:
            import traceback; traceback.print_exc()
            return Response({'detail': f'Error al ajustar el plan: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ListaMercadoView(APIView):
    def get(self, request):
        try:
            lista = ListaMercado.objects.get(usuario=request.user)
            return Response(ListaMercadoSerializer(lista).data)
        except ListaMercado.DoesNotExist:
            return Response({'detail': 'No tienes lista de mercado generada.'}, status=status.HTTP_404_NOT_FOUND)

    def post(self, request):
        try:
            plan = PlanNutricional.objects.get(usuario=request.user)
        except PlanNutricional.DoesNotExist:
            return Response({'detail': 'Genera tu plan nutricional primero.'}, status=status.HTTP_400_BAD_REQUEST)

        anterior = ListaMercado.objects.filter(usuario=request.user).first()
        default_personas = anterior.num_personas if anterior else 1
        try:
            num_personas = int(request.data.get('num_personas', default_personas))
        except (TypeError, ValueError):
            num_personas = default_personas
        num_personas = max(1, min(num_personas, 20))

        hoy = timezone.localdate()
        limite = hoy - timedelta(days=13)
        recurrentes = ItemRecurrente.objects.filter(usuario=request.user, ultima_compra__gte=limite)
        excluir = [r.nombre for r in recurrentes]
        items_ya_comprados = [
            {'nombre': r.nombre, 'ultima_compra': r.ultima_compra.isoformat()}
            for r in recurrentes
        ]

        try:
            ai   = AIService()
            data = ai.generar_lista_mercado(plan, num_personas, excluir=excluir)
            ListaMercado.objects.filter(usuario=request.user).delete()
            lista = ListaMercado.objects.create(
                usuario=request.user,
                plan=plan,
                consejos_compra=data.get('consejos_compra', []),
                plan_preparacion=data.get('plan_preparacion', []),
                num_personas=num_personas,
                items_ya_comprados=items_ya_comprados,
            )
            for cat in data.get('categorias', []):
                for item in cat.get('items', []):
                    ItemMercado.objects.create(
                        lista=lista,
                        nombre=item['nombre'],
                        cantidad=item.get('cantidad', ''),
                        categoria=cat['categoria'],
                        frecuencia=item.get('frecuencia', 'semanal'),
                    )
            return Response(ListaMercadoSerializer(lista).data, status=status.HTTP_201_CREATED)
        except Exception as e:
            import traceback; traceback.print_exc()
            return Response({'detail': f'Error al generar la lista: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ItemMercadoToggleView(APIView):
    def patch(self, request, pk):
        try:
            item = ItemMercado.objects.get(pk=pk, lista__usuario=request.user)
        except ItemMercado.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        item.comprado = not item.comprado
        item.save(update_fields=['comprado'])

        if item.frecuencia == 'quincenal':
            if item.comprado:
                ItemRecurrente.objects.update_or_create(
                    usuario=request.user, nombre=item.nombre,
                    defaults={'ultima_compra': timezone.localdate()},
                )
            else:
                ItemRecurrente.objects.filter(usuario=request.user, nombre=item.nombre).delete()

        return Response(ItemMercadoSerializer(item).data)


class GenerarRutinaView(APIView):
    def post(self, request):
        implementos = request.user.implementos.select_related('implemento').all()
        proceso = proceso_de_referencia(request.user)
        if not proceso or not proceso.incluye_entrenamiento or not hasattr(proceso, 'entrenamiento'):
            return Response({'detail': 'Tu proceso no incluye entrenamiento.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            ai = AIService()
            data = ai.generar_rutina(request.user, implementos, proceso)

            Rutina.objects.filter(usuario=request.user).delete()
            rutina = Rutina.objects.create(
                usuario=request.user,
                nombre=data['nombre'],
                descripcion=data.get('descripcion', ''),
            )

            for dia_data in data['dias']:
                dia = DiaRutina.objects.create(rutina=rutina, dia_semana=dia_data['dia_semana'])
                for idx, ej_data in enumerate(dia_data['ejercicios']):
                    ejercicio, created = Ejercicio.objects.get_or_create(
                        nombre=ej_data['nombre'],
                        defaults={
                            'descripcion': ej_data.get('descripcion', ''),
                            'requiere_implemento': ej_data.get('requiere_implemento', True),
                            'busqueda_media': ej_data.get('busqueda_media', ''),
                        }
                    )
                    if not created:
                        update_fields = []
                        if ej_data.get('descripcion') and not ejercicio.descripcion:
                            ejercicio.descripcion = ej_data['descripcion']
                            update_fields.append('descripcion')
                        if ej_data.get('busqueda_media') and not ejercicio.busqueda_media:
                            ejercicio.busqueda_media = ej_data['busqueda_media']
                            update_fields.append('busqueda_media')
                        if update_fields:
                            ejercicio.save(update_fields=update_fields)
                    EjercicioDia.objects.create(
                        dia=dia,
                        ejercicio=ejercicio,
                        series=ej_data.get('series'),
                        repeticiones=ej_data.get('repeticiones'),
                        duracion_segundos=ej_data.get('duracion_segundos'),
                        orden=ej_data.get('orden', idx),
                    )

            from routines.serializers import RutinaSerializer
            return Response(RutinaSerializer(rutina).data, status=status.HTTP_201_CREATED)
        except Exception as e:
            import traceback; traceback.print_exc()
            return Response({'detail': f'Error al generar la rutina: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SuplementoListCreateView(generics.ListCreateAPIView):
    """Suplementos del proceso vigente: activos primero y luego los que ya terminaron."""
    serializer_class = SuplementoSerializer

    def get_queryset(self):
        proceso = proceso_de_referencia(self.request.user)
        return (Suplemento.objects.filter(usuario=self.request.user, proceso=proceso)
                .select_related('proceso').order_by(F('fecha_fin').desc(nulls_first=True), 'fecha_inicio', 'id'))

    def create(self, request, *args, **kwargs):
        # Al crear un proceso programado, sus suplementos van a él y no al que sigue en curso.
        if request.data.get('proceso'):
            proceso = get_object_or_404(Proceso, pk=request.data['proceso'], usuario=request.user)
        else:
            proceso = proceso_de_referencia(request.user)
        if not proceso:
            raise ReglaNegocioError('Primero crea tu proceso.')
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        suplemento = suplementos.crear_suplemento(proceso, serializer.validated_data)
        return Response(SuplementoSerializer(suplemento).data, status=status.HTTP_201_CREATED)


class SuplementoDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = SuplementoEditarSerializer
    http_method_names = ['get', 'patch', 'delete']

    def get_queryset(self):
        return Suplemento.objects.filter(usuario=self.request.user).select_related('proceso')

    def update(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_object(), data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        suplemento = suplementos.actualizar_suplemento(serializer.instance, serializer.validated_data)
        return Response(SuplementoSerializer(suplemento).data)


class SuplementoAccionView(APIView):
    """Acciones del día a día: abrí un envase nuevo, sigo con él, lo dejé o lo cambié por otro."""

    def post(self, request, pk, accion):
        suplemento = get_object_or_404(Suplemento.objects.select_related('proceso'), pk=pk, usuario=request.user)
        if accion == 'abrir-envase':
            resultado = suplementos.abrir_envase(suplemento)
        elif accion == 'continuar':
            datos = ContinuarSerializer(data=request.data)
            datos.is_valid(raise_exception=True)
            resultado = suplementos.continuar(suplemento, datos.validated_data['dias'])
        elif accion == 'terminar':
            resultado = suplementos.terminar(suplemento)
        elif accion == 'reemplazar':
            datos = SuplementoEditarSerializer(data=request.data)
            datos.is_valid(raise_exception=True)
            resultado = suplementos.reemplazar(suplemento, datos.validated_data)
            return Response(SuplementoSerializer(resultado).data, status=status.HTTP_201_CREATED)
        else:
            return Response(status=status.HTTP_404_NOT_FOUND)
        return Response(SuplementoSerializer(resultado).data)
