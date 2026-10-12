from django.urls import path

from .views import EventosView, PantallaView, ResumenView

urlpatterns = [
    path('pantalla/', PantallaView.as_view(), name='auditoria-pantalla'),
    path('eventos/', EventosView.as_view(), name='auditoria-eventos'),
    path('resumen/', ResumenView.as_view(), name='auditoria-resumen'),
]
