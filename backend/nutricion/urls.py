from django.urls import path

from .views import GenerarRutinaView, MiPlanNutricionalView

urlpatterns = [
    path('mi-plan/', MiPlanNutricionalView.as_view(), name='mi-plan-nutricional'),
    path('generar-rutina/', GenerarRutinaView.as_view(), name='generar-rutina'),
]
