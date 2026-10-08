from django.urls import path
from .views import (FotoProgresoView, MedicionDetailView, MedicionFotosView, MedicionListCreateView,
                    RegistroEntrenamientoDetailView, RegistroEntrenamientoView)

urlpatterns = [
    path('mediciones/', MedicionListCreateView.as_view(), name='mediciones'),
    path('mediciones/<int:pk>/', MedicionDetailView.as_view(), name='medicion-detail'),
    path('mediciones/<int:pk>/fotos/', MedicionFotosView.as_view(), name='medicion-fotos'),
    path('fotos/<int:pk>/', FotoProgresoView.as_view(), name='foto-progreso'),
    path('entrenamiento/', RegistroEntrenamientoView.as_view(), name='registro-entrenamiento'),
    path('entrenamiento/<int:pk>/', RegistroEntrenamientoDetailView.as_view(), name='registro-entrenamiento-detail'),
]
