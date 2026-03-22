from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/usuarios/', include('users.urls')),
    path('api/rutinas/', include('routines.urls')),
    path('api/progreso/', include('progress.urls')),
    path('api/nutricion/', include('nutricion.urls')),
]
