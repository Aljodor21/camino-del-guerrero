from django.urls import path

from .views import RecordatorioDetailView, RecordatorioListCreateView

urlpatterns = [
    path('recordatorios/', RecordatorioListCreateView.as_view(), name='recordatorios'),
    path('recordatorios/<int:pk>/', RecordatorioDetailView.as_view(), name='recordatorio-detail'),
]
