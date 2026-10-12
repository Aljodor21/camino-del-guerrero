from datetime import timedelta

from django.db.models import Avg, Count, Max, Q
from django.db.models.functions import TruncDate
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework import permissions, serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from core.exceptions import ReglaNegocioError
from users.views import EsAdmin

from .middleware import registrar
from .models import Evento

MAX_DIAS = 90
POR_PAGINA = 100


class EventoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Evento
        fields = ['id', 'usuario', 'correo', 'momento', 'tipo', 'metodo', 'ruta', 'camino', 'consulta',
                  'estado', 'duracion_ms', 'automatico', 'ip', 'cliente', 'version_app', 'sistema',
                  'dispositivo', 'navegador']
        read_only_fields = fields


def _rango(request, por_defecto=7):
    hoy = timezone.localdate()
    hasta = parse_date(request.query_params.get('hasta') or '') or hoy
    desde = parse_date(request.query_params.get('desde') or '') or hasta - timedelta(days=por_defecto - 1)
    if desde > hasta:
        raise ReglaNegocioError('La fecha inicial va antes de la final.')
    if (hasta - desde).days >= MAX_DIAS:
        raise ReglaNegocioError(f'Pide máximo {MAX_DIAS} días a la vez.')
    return desde, hasta


def _filtrar(request):
    desde, hasta = _rango(request)
    eventos = Evento.objects.filter(momento__date__range=(desde, hasta))
    p = request.query_params
    if usuario := p.get('usuario'):
        eventos = eventos.filter(usuario_id=usuario) if usuario.isdigit() else eventos.filter(
            correo__icontains=usuario)
    if cliente := p.get('cliente'):
        eventos = eventos.filter(cliente=cliente)
    if tipo := p.get('tipo'):
        eventos = eventos.filter(tipo=tipo)
    if dispositivo := p.get('dispositivo'):
        eventos = eventos.filter(dispositivo=dispositivo)
    if q := p.get('q'):
        eventos = eventos.filter(Q(camino__icontains=q) | Q(ruta__icontains=q) | Q(consulta__icontains=q))
    if p.get('errores') == '1':
        eventos = eventos.filter(estado__gte=400)
    if p.get('automaticos') != '1':
        eventos = eventos.filter(automatico=False)
    return eventos, desde, hasta


class PantallaView(APIView):
    """La app avisa qué pantalla abrió la persona (la ruta, sin lo que escribió en ella)."""

    def post(self, request):
        ruta = request.data.get('ruta')
        if not isinstance(ruta, str) or not ruta.startswith('/') or len(ruta) > 200:
            raise ReglaNegocioError('Falta la pantalla.')
        ruta = ruta.split('?')[0].split('#')[0]
        registrar(request._request, tipo='pantalla', metodo='VER', ruta=ruta, camino=ruta)
        return Response(status=204)


class EventosView(APIView):
    """Las huellas, de la más nueva a la más vieja. `antes` es el id con el que seguir."""
    permission_classes = [EsAdmin]

    def get(self, request):
        eventos, desde, hasta = _filtrar(request)
        if antes := request.query_params.get('antes'):
            if not antes.isdigit():
                raise ReglaNegocioError('El punto de partida no es válido.')
            eventos = eventos.filter(id__lt=int(antes))
        pagina = list(eventos[:POR_PAGINA + 1])
        hay_mas = len(pagina) > POR_PAGINA
        pagina = pagina[:POR_PAGINA]
        return Response({'desde': desde, 'hasta': hasta, 'resultados': EventoSerializer(pagina, many=True).data,
                         'siguiente': pagina[-1].id if hay_mas else None})


class ResumenView(APIView):
    """Cómo se está usando la app: quién, desde qué y qué se consulta."""
    permission_classes = [EsAdmin]

    def get(self, request):
        eventos, desde, hasta = _filtrar(request)
        api = eventos.filter(tipo='api')
        por_dia = (eventos.annotate(fecha=TruncDate('momento', tzinfo=timezone.get_current_timezone()))
                   .values('fecha').annotate(total=Count('id'), personas=Count('usuario', distinct=True))
                   .order_by('fecha'))
        por_dispositivo = (eventos.exclude(dispositivo='').values('cliente', 'sistema', 'dispositivo')
                           .annotate(total=Count('id'), personas=Count('usuario', distinct=True),
                                     ultima=Max('momento')).order_by('-total')[:20])
        por_persona = (eventos.exclude(usuario=None).values('usuario', 'correo')
                       .annotate(total=Count('id'), ultima=Max('momento')).order_by('-ultima')[:50])
        rutas = (api.values('metodo', 'ruta')
                 .annotate(total=Count('id'), errores=Count('id', filter=Q(estado__gte=400)),
                           ms=Avg('duracion_ms')).order_by('-total')[:25])
        pantallas = (eventos.filter(tipo='pantalla').values('ruta')
                     .annotate(total=Count('id')).order_by('-total')[:15])
        versiones = (eventos.filter(cliente='app').exclude(version_app='').values('version_app')
                     .annotate(personas=Count('usuario', distinct=True), total=Count('id')).order_by('-version_app'))
        return Response({
            'desde': desde, 'hasta': hasta,
            'total': eventos.count(),
            'personas': eventos.exclude(usuario=None).values('usuario').distinct().count(),
            'consultas': api.count(),
            'errores': api.filter(estado__gte=400).count(),
            'por_dia': list(por_dia),
            'por_cliente': list(eventos.exclude(cliente='').values('cliente').annotate(total=Count('id'))),
            'por_dispositivo': list(por_dispositivo),
            'por_persona': list(por_persona),
            'rutas': [{**r, 'ms': round(r['ms']) if r['ms'] is not None else None} for r in rutas],
            'pantallas': list(pantallas),
            'versiones_app': list(versiones),
        })
