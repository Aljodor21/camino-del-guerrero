from django.contrib import admin

from .models import Evento


@admin.register(Evento)
class EventoAdmin(admin.ModelAdmin):
    list_display = ('momento', 'correo', 'metodo', 'camino', 'estado', 'cliente', 'dispositivo')
    list_filter = ('tipo', 'cliente', 'estado')
    search_fields = ('correo', 'camino', 'dispositivo')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
