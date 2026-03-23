from django.urls import path
from .views import RegistroEntrenamientoDetailView, RegistroEntrenamientoView, RegistroPesoView

urlpatterns = [
    path('peso/', RegistroPesoView.as_view(), name='registro-peso'),
    path('entrenamiento/', RegistroEntrenamientoView.as_view(), name='registro-entrenamiento'),
    path('entrenamiento/<int:pk>/', RegistroEntrenamientoDetailView.as_view(), name='registro-entrenamiento-detail'),
]
