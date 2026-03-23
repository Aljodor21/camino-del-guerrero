from django.urls import path

from .views import GenerarRutinaView, ItemMercadoToggleView, ListaMercadoView, MiPlanNutricionalView

urlpatterns = [
    path('mi-plan/',          MiPlanNutricionalView.as_view(), name='mi-plan-nutricional'),
    path('generar-rutina/',   GenerarRutinaView.as_view(),     name='generar-rutina'),
    path('lista-mercado/',    ListaMercadoView.as_view(),      name='lista-mercado'),
    path('lista-mercado/items/<int:pk>/toggle/', ItemMercadoToggleView.as_view(), name='item-mercado-toggle'),
]
