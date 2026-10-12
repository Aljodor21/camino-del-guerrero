from django.contrib import admin
from django.urls import include, path

from .app_movil import DescargarApk, UltimaVersionApk

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/app/version/', UltimaVersionApk.as_view(), name='app-version'),
    path('api/app/descargar/', DescargarApk.as_view(), name='app-descargar'),
    path('api/usuarios/', include('users.urls')),
    path('api/rutinas/', include('routines.urls')),
    path('api/progreso/', include('progress.urls')),
    path('api/nutricion/', include('nutricion.urls')),
    path('api/agenda/', include('agenda.urls')),
]
