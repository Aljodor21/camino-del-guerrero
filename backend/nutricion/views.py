from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.ai_service import AIService
from routines.models import (DiaRutina, EjercicioDia, Ejercicio,
                              EjercicioImplemento, Rutina)

from .models import DiaNutricional, PlanNutricional
from .serializers import PlanNutricionalSerializer


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
            return Response({'detail': f'Error al generar el plan: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


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
                    ejercicio = Ejercicio.objects.create(
                        nombre=ej_data['nombre'],
                        descripcion=ej_data.get('descripcion', ''),
                        requiere_implemento=ej_data.get('requiere_implemento', True),
                    )
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
            return Response({'detail': f'Error al generar la rutina: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
