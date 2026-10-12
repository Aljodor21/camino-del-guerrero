from django.urls import path

from .views import (ConfirmarNotificacionFirmadaView, ConfirmarNotificacionView, CumplimientoView, HabitosView, HoyView,
                    NotificacionListView, PushView, RecordatorioDetailView, RecordatorioListCreateView,
                    RegistrarAguaView, RegistroHabitoListView)

urlpatterns = [
    path('recordatorios/', RecordatorioListCreateView.as_view(), name='recordatorios'),
    path('recordatorios/<int:pk>/', RecordatorioDetailView.as_view(), name='recordatorio-detail'),
    path('habitos/', HabitosView.as_view(), name='habitos'),
    path('cumplimiento/', CumplimientoView.as_view(), name='cumplimiento-global'),
    path('hoy/', HoyView.as_view(), name='hoy'),
    path('avisos/', NotificacionListView.as_view(), name='avisos'),
    path('avisos/<int:pk>/confirmar/', ConfirmarNotificacionView.as_view(), name='aviso-confirmar'),
    path('avisos/confirmar-firmado/', ConfirmarNotificacionFirmadaView.as_view(), name='aviso-confirmar-firmado'),
    path('avisos/push/', PushView.as_view(), name='avisos-push'),
    path('registros/', RegistroHabitoListView.as_view(), name='registros-habito'),
    path('registros/agua/', RegistrarAguaView.as_view(), name='registrar-agua'),
]
