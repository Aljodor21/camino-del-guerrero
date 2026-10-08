from django.urls import path

from .views import (GenerarRutinaView, ItemMercadoToggleView, ListaMercadoView,
                    MiPlanNutricionalView, RechazarComidaView, SuplementoAccionView,
                    SuplementoDetailView, SuplementoListCreateView)

urlpatterns = [
    path('mi-plan/',          MiPlanNutricionalView.as_view(), name='mi-plan-nutricional'),
    path('mi-plan/dias/<int:pk>/rechazar/', RechazarComidaView.as_view(), name='rechazar-comida'),
    path('generar-rutina/',   GenerarRutinaView.as_view(),     name='generar-rutina'),
    path('lista-mercado/',    ListaMercadoView.as_view(),      name='lista-mercado'),
    path('lista-mercado/items/<int:pk>/toggle/', ItemMercadoToggleView.as_view(), name='item-mercado-toggle'),
    path('suplementos/',          SuplementoListCreateView.as_view(), name='suplementos'),
    path('suplementos/<int:pk>/', SuplementoDetailView.as_view(),     name='suplemento-detail'),
    path('suplementos/<int:pk>/<slug:accion>/', SuplementoAccionView.as_view(), name='suplemento-accion'),
]
