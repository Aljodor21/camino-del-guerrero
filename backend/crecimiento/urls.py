from django.urls import path

from . import views_diario as diario

from .views import (AreaDetailView, AreaListCreateView, NotaDetailView, NotaListCreateView, ProcesoDetailView,
                    ProcesoListCreateView, ProyectoDetailView, ProyectoListCreateView, ProgramasView, ResumenView)

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
    path('programas/', ProgramasView.as_view(), name='crecimiento-programas'),
    path('diario/<int:pk>/', diario.MesView.as_view(), name='diario-mes'),
    path('diario/<int:pk>/gastos/', diario.GastosView.as_view(), name='diario-gastos'),
    path('diario/<int:pk>/gastos/<int:gasto>/', diario.GastoView.as_view(), name='diario-gasto'),
    path('diario/<int:pk>/sin-gasto/', diario.SinGastoView.as_view(), name='diario-sin-gasto'),
    path('diario/<int:pk>/no-mensuales/', diario.NoMensualesView.as_view(), name='diario-no-mensuales'),
    path('diario/<int:pk>/no-mensuales/<int:item>/', diario.NoMensualesView.as_view(), name='diario-no-mensual'),
    path('diario/<int:pk>/hormiga/', diario.HormigaView.as_view(), name='diario-hormigas'),
    path('diario/<int:pk>/hormiga/<int:item>/', diario.HormigaView.as_view(), name='diario-hormiga'),
]
