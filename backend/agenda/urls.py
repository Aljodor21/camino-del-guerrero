from django.urls import path

from .views import (SugerenciasView, HorarioDiaView, RegistrarDormirView, RegistrarLevantarView, SuenoView, CapituloView, HitosVistosView, LogrosView, ConfirmarNotificacionFirmadaView, ConfirmarNotificacionView, CumplimientoView, HabitosView,
                    HoyView, NotificacionListView, ProximosAvisosView, PushCelularPruebaView, PushCelularView, PushView, RecordatorioDetailView,
                    RecordatorioListCreateView,
                    RegistrarAguaView, RegistroHabitoListView)

urlpatterns = [
    path('recordatorios/', RecordatorioListCreateView.as_view(), name='recordatorios'),
    path('recordatorios/<int:pk>/', RecordatorioDetailView.as_view(), name='recordatorio-detail'),
    path('habitos/', HabitosView.as_view(), name='habitos'),
    path('cumplimiento/', CumplimientoView.as_view(), name='cumplimiento-global'),
    path('hoy/', HoyView.as_view(), name='hoy'),
    path('horario/<str:fecha>/', HorarioDiaView.as_view(), name='horario-dia'),
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
    path('registros/levantar/', RegistrarLevantarView.as_view(), name='registrar-levantar'),
    path('registros/dormir/', RegistrarDormirView.as_view(), name='registrar-dormir'),
    path('sueno/', SuenoView.as_view(), name='sueno'),
    path('sugerencias/', SugerenciasView.as_view(), name='sugerencias'),
]
