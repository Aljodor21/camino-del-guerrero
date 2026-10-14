from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Area, Nota, Proceso, Proyecto
from .programas import PROGRAMAS
from core.exceptions import ReglaNegocioError

from .serializers import (AreaSerializer, NotaSerializer, ProcesoSerializer, ProyectoSerializer, _calcular_avance,
                          _promedio)
from .tipos import TIPOS


class AreaListCreateView(generics.ListCreateAPIView):
    serializer_class = AreaSerializer
    pagination_class = None

    def get_queryset(self):
        return Area.objects.filter(usuario=self.request.user).prefetch_related('procesos__proyectos')

    def perform_create(self, serializer):
        serializer.save(usuario=self.request.user)


class AreaDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = AreaSerializer
    http_method_names = ['get', 'patch', 'delete']

    def get_queryset(self):
        return Area.objects.filter(usuario=self.request.user)


class ProcesoListCreateView(generics.ListCreateAPIView):
    serializer_class = ProcesoSerializer
    pagination_class = None

    def get_queryset(self):
        procesos = Proceso.objects.filter(area__usuario=self.request.user).prefetch_related('proyectos')
        if area := self.request.query_params.get('area'):
            procesos = procesos.filter(area_id=area) if area.isdigit() else procesos.none()
        return procesos


class ProcesoDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ProcesoSerializer
    http_method_names = ['get', 'patch', 'delete']

    def get_queryset(self):
        return Proceso.objects.filter(area__usuario=self.request.user)


class ProyectoListView(generics.ListAPIView):
    """Los proyectos llegan con su programa: no se crean sueltos."""
    serializer_class = ProyectoSerializer
    pagination_class = None

    def get_queryset(self):
        proyectos = Proyecto.objects.filter(proceso__area__usuario=self.request.user)
        if proceso := self.request.query_params.get('proceso'):
            proyectos = proyectos.filter(proceso_id=proceso) if proceso.isdigit() else proyectos.none()
        return proyectos


class ProyectoDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = ProyectoSerializer
    http_method_names = ['get', 'patch']

    def get_queryset(self):
        return Proyecto.objects.filter(proceso__area__usuario=self.request.user)


class NotaListCreateView(generics.ListCreateAPIView):
    """Las notas de la persona. Con `proyecto`, `proceso` o `area` se filtran; sin nada, las más recientes
    (`limite`, hasta 50): es lo que la app principal puede traer."""
    serializer_class = NotaSerializer
    pagination_class = None

    def get_queryset(self):
        notas = Nota.objects.filter(proyecto__proceso__area__usuario=self.request.user).select_related('proyecto')
        for parametro, campo in (('proyecto', 'proyecto_id'), ('proceso', 'proyecto__proceso_id'),
                                 ('area', 'proyecto__proceso__area_id')):
            valor = self.request.query_params.get(parametro)
            if valor:
                notas = notas.filter(**{campo: valor}) if valor.isdigit() else notas.none()
        limite = self.request.query_params.get('limite') or '50'
        return notas[:min(int(limite), 50) if limite.isdigit() else 50]


class NotaDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = NotaSerializer
    http_method_names = ['get', 'patch', 'delete']

    def get_queryset(self):
        return Nota.objects.filter(proyecto__proceso__area__usuario=self.request.user)


class ResumenView(APIView):
    """Lo que la app principal puede traer de crecimiento: por área, su avance, sus procesos en curso con la
    frase de cada proyecto, y las últimas notas."""

    def get(self, request):
        areas = Area.objects.filter(usuario=request.user).prefetch_related('procesos__proyectos')
        datos = []
        for area in areas:
            procesos = [{
                'id': p.id, 'titulo': p.titulo, 'fuente': p.fuente, 'fuente_titulo': p.fuente_titulo,
                'autor': p.autor, 'estado': p.estado,
                'avance': _promedio(x.avance for x in p.proyectos.all()),
                'proyectos': [{'id': x.id, 'titulo': x.titulo, 'estado': x.estado, 'avance': x.avance,
                               'resumen': ProyectoSerializer(x, context={'request': request}).data['resumen']}
                              for x in p.proyectos.all()],
            } for p in area.procesos.all() if p.estado != 'terminado']
            datos.append({'id': area.id, 'nombre': area.nombre, 'icono': area.icono,
                          'avance': _promedio(x.avance for p in area.procesos.all() for x in p.proyectos.all()),
                          'procesos': procesos})
        notas = NotaSerializer(Nota.objects.filter(proyecto__proceso__area__usuario=request.user)
                               .select_related('proyecto')[:5], many=True, context={'request': request}).data
        return Response({'areas': datos, 'notas': notas})


class ProgramasView(APIView):
    """El catálogo: programas ya armados según una fuente, con sus proyectos."""

    def get(self, request):
        return Response([{
            'id': clave, 'titulo': p.titulo, 'fuente': p.fuente, 'fuente_titulo': p.fuente_titulo,
            'autor': p.autor, 'area': p.area, 'descripcion': p.descripcion,
            'proyectos': [{'clave': x.clave, 'titulo': x.titulo, 'detalle': x.detalle} for x in p.proyectos],
        } for clave, p in PROGRAMAS.items()])


class AccionProyectoView(APIView):
    """Una acción propia del tipo del proyecto (por ejemplo, «hoy ya las leí»)."""

    def post(self, request, pk, accion):
        proyecto = get_object_or_404(Proyecto, pk=pk, proceso__area__usuario=request.user)
        hacer = TIPOS[proyecto.tipo].acciones.get(accion) if proyecto.tipo in TIPOS else None
        if hacer is None:
            raise ReglaNegocioError('Ese proyecto no tiene esa acción.')
        hacer(proyecto, timezone.localdate())
        _calcular_avance(proyecto)
        return Response(ProyectoSerializer(proyecto, context={'request': request}).data)
