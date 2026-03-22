from django.urls import path

from .views import (EjercicioVideoUpdateView, ImplementoDetailView,
                    ImplementoListCreateView, MisImplementosDeleteView,
                    MisImplementosView, MiRutinaView)

urlpatterns = [
    path('implementos/', ImplementoListCreateView.as_view(), name='implementos'),
    path('implementos/<int:pk>/', ImplementoDetailView.as_view(), name='implemento-detail'),
    path('mis-implementos/', MisImplementosView.as_view(), name='mis-implementos'),
    path('mis-implementos/<int:pk>/', MisImplementosDeleteView.as_view(), name='mis-implementos-delete'),
    path('ejercicios/<int:pk>/video/', EjercicioVideoUpdateView.as_view(), name='ejercicio-video'),
    path('mi-rutina/', MiRutinaView.as_view(), name='mi-rutina'),
]
