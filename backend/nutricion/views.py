from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.ai_service import AIService
from routines.models import (DiaRutina, EjercicioDia, Ejercicio,
                              EjercicioImplemento, Rutina)

from .models import DiaNutricional, ItemMercado, ListaMercado, PlanNutricional
from .serializers import ItemMercadoSerializer, ListaMercadoSerializer, PlanNutricionalSerializer


class MiPlanNutricionalView(APIView):
    def get(self, request):
        try:
            plan = PlanNutricional.objects.get(usuario=request.user)
            return Response(PlanNutricionalSerializer(plan).data)
        except PlanNutricional.DoesNotExist:
            return Response({'detail': 'No tienes plan nutricional generado aún.'}, status=status.HTTP_404_NOT_FOUND)

    def post(self, request):
        objetivo = request.user.objetivos.filter(activo=True).first()
        if not objetivo:
            return Response({'detail': 'Debes completar el onboarding primero.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            ai = AIService()
            data = ai.generar_plan_nutricional(request.user, objetivo)

            PlanNutricional.objects.filter(usuario=request.user).delete()
            plan = PlanNutricional.objects.create(usuario=request.user, objetivo=objetivo)

            for dia_data in data['dias']:
                DiaNutricional.objects.create(plan=plan, **dia_data)

            return Response(PlanNutricionalSerializer(plan).data, status=status.HTTP_201_CREATED)
        except Exception as e:
            import traceback; traceback.print_exc()
            return Response({'detail': f'Error al generar el plan: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


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
        try:
            ai   = AIService()
            data = ai.generar_lista_mercado(plan)
            ListaMercado.objects.filter(usuario=request.user).delete()
            lista = ListaMercado.objects.create(
                usuario=request.user,
                plan=plan,
                consejos_compra=data.get('consejos_compra', []),
                plan_preparacion=data.get('plan_preparacion', []),
            )
            for cat in data.get('categorias', []):
                for item in cat.get('items', []):
                    ItemMercado.objects.create(
                        lista=lista,
                        nombre=item['nombre'],
                        cantidad=item.get('cantidad', ''),
                        categoria=cat['categoria'],
                    )
            return Response(ListaMercadoSerializer(lista).data, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({'detail': f'Error al generar la lista: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ItemMercadoToggleView(APIView):
    def patch(self, request, pk):
        try:
            item = ItemMercado.objects.get(pk=pk, lista__usuario=request.user)
        except ItemMercado.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        item.comprado = not item.comprado
        item.save(update_fields=['comprado'])
        return Response(ItemMercadoSerializer(item).data)


class GenerarRutinaView(APIView):
    def post(self, request):
        implementos = request.user.implementos.select_related('implemento').all()
        objetivo = request.user.objetivos.filter(activo=True).first()
        if not objetivo:
            return Response({'detail': 'Debes completar el onboarding primero.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            ai = AIService()
            data = ai.generar_rutina(request.user, implementos, objetivo)

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
