from django.urls import path

from .views import (AreaDetailView, AreaListCreateView, NotaDetailView, NotaListCreateView, ProcesoDetailView,
                    ProcesoListCreateView, ProyectoDetailView, ProyectoListCreateView, ResumenView)

urlpatterns = [
    path('areas/', AreaListCreateView.as_view(), name='crecimiento-areas'),
    path('areas/<int:pk>/', AreaDetailView.as_view(), name='crecimiento-area'),
    path('procesos/', ProcesoListCreateView.as_view(), name='crecimiento-procesos'),
    path('procesos/<int:pk>/', ProcesoDetailView.as_view(), name='crecimiento-proceso'),
    path('proyectos/', ProyectoListCreateView.as_view(), name='crecimiento-proyectos'),
    path('proyectos/<int:pk>/', ProyectoDetailView.as_view(), name='crecimiento-proyecto'),
    path('notas/', NotaListCreateView.as_view(), name='crecimiento-notas'),
    path('notas/<int:pk>/', NotaDetailView.as_view(), name='crecimiento-nota'),
    path('resumen/', ResumenView.as_view(), name='crecimiento-resumen'),
]
