from django.urls import path

from .views import (CapituloView, HitosVistosView, LogrosView, ConfirmarNotificacionFirmadaView, ConfirmarNotificacionView, CumplimientoView, HabitosView,
                    HoyView, NotificacionListView, ProximosAvisosView, PushCelularPruebaView, PushCelularView, PushView, RecordatorioDetailView,
                    RecordatorioListCreateView,
                    RegistrarAguaView, RegistroHabitoListView)

urlpatterns = [
    path('recordatorios/', RecordatorioListCreateView.as_view(), name='recordatorios'),
    path('recordatorios/<int:pk>/', RecordatorioDetailView.as_view(), name='recordatorio-detail'),
    path('habitos/', HabitosView.as_view(), name='habitos'),
    path('cumplimiento/', CumplimientoView.as_view(), name='cumplimiento-global'),
    path('hoy/', HoyView.as_view(), name='hoy'),
    path('logros/', LogrosView.as_view(), name='logros'),
    path('logros/vistos/', HitosVistosView.as_view(), name='logros-vistos'),
    path('capitulo/', CapituloView.as_view(), name='capitulo'),
    path('avisos/', NotificacionListView.as_view(), name='avisos'),
    path('avisos/proximos/', ProximosAvisosView.as_view(), name='avisos-proximos'),
    path('avisos/<int:pk>/confirmar/', ConfirmarNotificacionView.as_view(), name='aviso-confirmar'),
    path('avisos/confirmar-firmado/', ConfirmarNotificacionFirmadaView.as_view(), name='aviso-confirmar-firmado'),
    path('avisos/push/', PushView.as_view(), name='avisos-push'),
    path('push/celular/', PushCelularView.as_view(), name='push-celular'),
    path('push/celular/probar/', PushCelularPruebaView.as_view(), name='push-celular-probar'),
    path('registros/', RegistroHabitoListView.as_view(), name='registros-habito'),
    path('registros/agua/', RegistrarAguaView.as_view(), name='registrar-agua'),
]
