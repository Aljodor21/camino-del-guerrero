import mimetypes
from datetime import timedelta

from django.db import transaction
from django.db.models import F
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework import generics, status
from rest_framework.parsers import JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from agenda import notificaciones
from core.ai_service import AIService
from core.exceptions import ReglaNegocioError
from users.models import Proceso
from users.procesos import proceso_de_referencia
from routines.models import (DiaRutina, EjercicioDia, Ejercicio,
                              EjercicioImplemento, Rutina)

from . import calculadora, cantidades, comidas, lector_minuta, menus, ilustracion, mercado, minutas, proyeccion, suplementos
from .models import (AlimentoIntercambio, ComidaMenu, Ilustracion, ItemMercado, ItemRecurrente, ListaMercado, Minuta,
                     PreferenciasComida, RegistroComida, Suplemento)
from .grupos import NOMBRE_GRUPO, NOMBRE_TIEMPO
from .serializers import (AlimentoIntercambioSerializer, ContinuarSerializer, IlustracionSerializer, ItemMercadoSerializer,
                          cantidad_casera,
                          ListaMercadoSerializer, MenuSemanalSerializer, MinutaCrearSerializer, MinutaSerializer,
                          PreferenciasComidaSerializer, RegistroComidaCrearSerializer, RegistroComidaSerializer,
                          SubirMinutaSerializer,
                          SuplementoEditarSerializer, SuplementoSerializer)


class ListaMercadoView(APIView):
    def get(self, request):
        try:
            lista = ListaMercado.objects.get(usuario=request.user)
            return Response(ListaMercadoSerializer(lista).data)
        except ListaMercado.DoesNotExist:
            return Response({'detail': 'No tienes lista de mercado generada.'}, status=status.HTTP_404_NOT_FOUND)

    def post(self, request):
        if not minutas.vigente_de(request.user):
            raise ReglaNegocioError('Primero arma tu plan de comida.')
        menu = request.user.menus.filter(semana=minutas.lunes(timezone.localdate())).first()
        if menu is None:
            raise ReglaNegocioError('Primero arma el menú de esta semana.')

        anterior = ListaMercado.objects.filter(usuario=request.user).first()
        default_personas = anterior.num_personas if anterior else 1
        try:
            num_personas = int(request.data.get('num_personas', default_personas))
        except (TypeError, ValueError):
            num_personas = default_personas
        num_personas = max(1, min(num_personas, 20))

        periodo = request.data.get('periodo', 'semana')
        if periodo not in mercado.DIAS_POR_PERIODO:
            raise ReglaNegocioError('El periodo es una semana, 15 días o un mes.')

        hoy = timezone.localdate()
        ya_comprados = []
        if periodo in mercado.VENTANA_YA_COMPRADO:
            limite = hoy - timedelta(days=mercado.VENTANA_YA_COMPRADO[periodo])
            ya_comprados = list(ItemRecurrente.objects.filter(usuario=request.user, ultima_compra__gte=limite))
        siguiente = request.user.menus.filter(semana=menu.semana + timedelta(days=7)).first()

        data = mercado.armar(menu, siguiente, num_personas, periodo, {r.nombre for r in ya_comprados})
        leche = menus.leche_para_proteina(menu, num_personas)
        if leche:
            categorias = data['categorias']
            lacteos = next((c for c in categorias if c['categoria'] == 'lacteos'), None)
            if lacteos is None:
                lacteos = {'categoria': 'lacteos', 'items': []}
                categorias.append(lacteos)
            lacteos['items'].append(menus.item_leche(leche))
        with transaction.atomic():
            ListaMercado.objects.filter(usuario=request.user).delete()
            lista = ListaMercado.objects.create(
                usuario=request.user, menu=menu, consejos_compra=data['consejos_compra'],
                num_personas=num_personas, periodo=periodo,
                items_ya_comprados=[{'nombre': r.nombre, 'ultima_compra': r.ultima_compra.isoformat()}
                                    for r in ya_comprados],
            )
            ItemMercado.objects.bulk_create(
                ItemMercado(lista=lista, nombre=item['nombre'], cantidad=item['cantidad'],
                            categoria=cat['categoria'], frecuencia=item['frecuencia'])
                for cat in data['categorias'] for item in cat['items'])
        return Response(ListaMercadoSerializer(lista).data, status=status.HTTP_201_CREATED)


class ItemMercadoToggleView(APIView):
    def patch(self, request, pk):
        try:
            item = ItemMercado.objects.get(pk=pk, lista__usuario=request.user)
        except ItemMercado.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        item.comprado = not item.comprado
        item.save(update_fields=['comprado'])

        if item.frecuencia in ('quincenal', 'mensual'):
            if item.comprado:
                ItemRecurrente.objects.update_or_create(
                    usuario=request.user, nombre=item.nombre,
                    defaults={'ultima_compra': timezone.localdate()},
                )
            else:
                ItemRecurrente.objects.filter(usuario=request.user, nombre=item.nombre).delete()

        return Response(ItemMercadoSerializer(item).data)


class GenerarRutinaView(APIView):
    def post(self, request):
        implementos = request.user.implementos.select_related('implemento').all()
        proceso = proceso_de_referencia(request.user)
        if not proceso or not proceso.incluye_entrenamiento or not hasattr(proceso, 'entrenamiento'):
            return Response({'detail': 'Tu proceso no incluye entrenamiento.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            ai = AIService()
            data = ai.generar_rutina(request.user, implementos, proceso)

            Rutina.objects.filter(usuario=request.user).delete()
            rutina = Rutina.objects.create(
                usuario=request.user,
                nombre=data['nombre'],
                descripcion=data.get('descripcion', ''),
            )

            for dia_data in data['dias']:
                dia = DiaRutina.objects.create(rutina=rutina, dia_semana=dia_data['dia_semana'])
                for idx, ej_data in enumerate(dia_data['ejercicios']):
                    ejercicio, created = Ejercicio.objects.get_or_create(
                        nombre=ej_data['nombre'],
                        defaults={
                            'descripcion': ej_data.get('descripcion', ''),
                            'requiere_implemento': ej_data.get('requiere_implemento', True),
                            'busqueda_media': ej_data.get('busqueda_media', ''),
                        }
                    )
                    if not created:
                        update_fields = []
                        if ej_data.get('descripcion') and not ejercicio.descripcion:
                            ejercicio.descripcion = ej_data['descripcion']
                            update_fields.append('descripcion')
                        if ej_data.get('busqueda_media') and not ejercicio.busqueda_media:
                            ejercicio.busqueda_media = ej_data['busqueda_media']
                            update_fields.append('busqueda_media')
                        if update_fields:
                            ejercicio.save(update_fields=update_fields)
                    EjercicioDia.objects.create(
                        dia=dia,
                        ejercicio=ejercicio,
                        series=ej_data.get('series'),
                        repeticiones=ej_data.get('repeticiones'),
                        duracion_segundos=ej_data.get('duracion_segundos'),
                        orden=ej_data.get('orden', idx),
                    )

            from routines.serializers import RutinaSerializer
            return Response(RutinaSerializer(rutina).data, status=status.HTTP_201_CREATED)
        except Exception as e:
            import traceback; traceback.print_exc()
            return Response({'detail': f'Error al generar la rutina: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SuplementoListCreateView(generics.ListCreateAPIView):
    """Suplementos del proceso vigente: activos primero y luego los que ya terminaron."""
    serializer_class = SuplementoSerializer

    def get_queryset(self):
        proceso = proceso_de_referencia(self.request.user)
        return (Suplemento.objects.filter(usuario=self.request.user, proceso=proceso)
                .select_related('proceso').order_by(F('fecha_fin').desc(nulls_first=True), 'fecha_inicio', 'id'))

    def create(self, request, *args, **kwargs):
        # Al crear un proceso programado, sus suplementos van a él y no al que sigue en curso.
        if request.data.get('proceso'):
            proceso = get_object_or_404(Proceso, pk=request.data['proceso'], usuario=request.user)
        else:
            proceso = proceso_de_referencia(request.user)
        if not proceso:
            raise ReglaNegocioError('Primero crea tu proceso.')
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        suplemento = suplementos.crear_suplemento(proceso, serializer.validated_data)
        return Response(SuplementoSerializer(suplemento).data, status=status.HTTP_201_CREATED)


class SuplementoDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = SuplementoEditarSerializer
    http_method_names = ['get', 'patch', 'delete']

    def get_queryset(self):
        return Suplemento.objects.filter(usuario=self.request.user).select_related('proceso')

    def update(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_object(), data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        suplemento = suplementos.actualizar_suplemento(serializer.instance, serializer.validated_data)
        return Response(SuplementoSerializer(suplemento).data)

    def perform_destroy(self, instance):
        suplementos.eliminar(instance)


class SuplementoAccionView(APIView):
    """Acciones del día a día: abrí un envase nuevo, sigo con él, lo dejé o lo cambié por otro."""

    def post(self, request, pk, accion):
        suplemento = get_object_or_404(Suplemento.objects.select_related('proceso'), pk=pk, usuario=request.user)
        if accion == 'abrir-envase':
            resultado = suplementos.abrir_envase(suplemento)
        elif accion == 'continuar':
            datos = ContinuarSerializer(data=request.data)
            datos.is_valid(raise_exception=True)
            resultado = suplementos.continuar(suplemento, datos.validated_data['dias'])
        elif accion == 'terminar':
            resultado = suplementos.terminar(suplemento)
        elif accion == 'reemplazar':
            datos = SuplementoEditarSerializer(data=request.data)
            datos.is_valid(raise_exception=True)
            resultado = suplementos.reemplazar(suplemento, datos.validated_data)
            return Response(SuplementoSerializer(resultado).data, status=status.HTTP_201_CREATED)
        else:
            return Response(status=status.HTTP_404_NOT_FOUND)
        return Response(SuplementoSerializer(resultado).data)


class IntercambiosView(generics.ListAPIView):
    """La lista de intercambios de la nutricionista."""
    serializer_class = AlimentoIntercambioSerializer
    queryset = AlimentoIntercambio.objects.all()


class IntercambiosCsvView(APIView):
    """La lista de intercambios como tabla (CSV para Excel): sirve para verla y como formato para
    proponer una lista distinta."""

    def get(self, request):
        import csv
        from django.http import HttpResponse
        respuesta = HttpResponse(content_type='text/csv; charset=utf-8')
        respuesta['Content-Disposition'] = 'attachment; filename="lista-de-intercambios.csv"'
        respuesta.write('\ufeff')  # para que Excel lea bien las tildes
        escritor = csv.writer(respuesta, delimiter=';')
        escritor.writerow(['grupo', 'subgrupo', 'alimento', 'gramos_de_una_porcion', 'medida_casera_de_una_porcion'])
        for a in AlimentoIntercambio.objects.all():
            escritor.writerow([a.grupo, a.subgrupo, a.nombre, a.gramos if a.gramos is not None else '', a.medida])
        return respuesta


class MinutaListCreateView(APIView):
    """Minutas del proceso (la primera es la vigente) y guardar una nueva."""
    parser_classes = [MultiPartParser, JSONParser]

    def get(self, request):
        proceso = proceso_de_referencia(request.user)
        lista = proceso.minutas.all() if proceso else Minuta.objects.none()
        return Response(MinutaSerializer(lista, many=True).data)

    def post(self, request):
        datos = MinutaCrearSerializer(data=request.data)
        datos.is_valid(raise_exception=True)
        datos = dict(datos.validated_data)
        minuta = minutas.crear(request.user, datos, datos.pop('archivo', None))
        return Response(MinutaSerializer(minuta).data, status=status.HTTP_201_CREATED)


class MinutaDetailView(generics.RetrieveAPIView):
    serializer_class = MinutaSerializer

    def get_queryset(self):
        return Minuta.objects.filter(usuario=self.request.user)


class LeerPdfView(APIView):
    """Lee la minuta de un PDF que la app reconoce (como el de Comfama) para llenar la plantilla.
    No guarda nada: el usuario revisa la tabla y la guarda."""
    parser_classes = [MultiPartParser]

    def post(self, request):
        datos = SubirMinutaSerializer(data=request.data)
        datos.is_valid(raise_exception=True)
        leido = lector_minuta.leer(datos.validated_data['archivo'])
        leido['proteina_g_kg'] = float(leido['proteina_g_kg']) if leido['proteina_g_kg'] else None
        return Response(leido)


class CalcularMinutaView(APIView):
    """Minuta calculada para quien no tiene nutricionista. No guarda nada."""

    def post(self, request):
        proceso = minutas.proceso_con_alimentacion(request.user, request.data.get('proceso'))
        propuesta = calculadora.calcular(request.user, proceso)
        propuesta['proteina_g_kg'] = float(propuesta['proteina_g_kg'])
        return Response(propuesta)


class MinutaArchivoView(APIView):
    """El original (PDF o foto), solo para su dueño."""

    def get(self, request, pk):
        minuta = get_object_or_404(Minuta, pk=pk, usuario=request.user)
        if not minuta.archivo:
            return Response(status=status.HTTP_404_NOT_FOUND)
        tipo = mimetypes.guess_type(minuta.archivo.name)[0] or 'application/octet-stream'
        respuesta = FileResponse(minuta.archivo.open('rb'), content_type=tipo)
        respuesta['Cache-Control'] = 'private, max-age=3600'
        return respuesta


class PreferenciasComidaView(APIView):
    def get(self, request):
        preferencias, _ = PreferenciasComida.objects.get_or_create(usuario=request.user)
        return Response(PreferenciasComidaSerializer(preferencias).data)

    def patch(self, request):
        preferencias, _ = PreferenciasComida.objects.get_or_create(usuario=request.user)
        serializer = PreferenciasComidaSerializer(preferencias, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        menus.reajustar(request.user)
        return Response(serializer.data)


def _respuesta_menu(menu, status_code=status.HTTP_200_OK):
    contexto = menus.Contexto(menu.usuario, menu.minuta)
    datos = MenuSemanalSerializer(menu, context={
        'contexto': contexto, 'elector': menus.Elector(contexto, semilla=0), 'ejemplos': {},
    }).data
    return Response(datos, status=status_code)


def _semana(valor):
    """Lunes de la semana pedida (?semana=AAAA-MM-DD) o de la actual."""
    fecha = parse_date(valor) if valor else timezone.localdate()
    if fecha is None:
        raise ReglaNegocioError('La semana no es una fecha válida.')
    return minutas.lunes(fecha)


class MenuView(APIView):
    """El menú de una semana. Se arma con POST: esta semana o la siguiente."""

    def get(self, request):
        menu = request.user.menus.filter(semana=_semana(request.query_params.get('semana'))).first()
        if menu is None:
            return Response({'detail': 'Aún no hay menú para esa semana.'}, status=status.HTTP_404_NOT_FOUND)
        return _respuesta_menu(menu)

    def post(self, request):
        semana = _semana(request.data.get('semana'))
        actual = minutas.lunes(timezone.localdate())
        if semana not in (actual, actual + timedelta(days=7)):
            raise ReglaNegocioError('Solo se arma el menú de esta semana o de la siguiente.')
        return _respuesta_menu(menus.generar(request.user, semana), status.HTTP_201_CREATED)


def _comida(request, pk):
    return get_object_or_404(ComidaMenu.objects.select_related('menu__minuta__proceso', 'menu__usuario'),
                             pk=pk, menu__usuario=request.user)


class ComidaOpcionesView(APIView):
    """Intercambios de un alimento de la comida, en sus mismas porciones."""

    def get(self, request, pk):
        comida = _comida(request, pk)
        componente = get_object_or_404(comida.componentes.select_related('alimento'),
                                       pk=request.query_params.get('componente'))
        return Response([{
            'id': a.id, 'nombre': a.nombre, 'subgrupo': a.subgrupo,
            'cantidad': cantidad_casera(a, componente.porciones),
            'gramos': cantidades.gramos(a.gramos, componente.porciones),
        } for a in menus.opciones(componente)])


class ComidaAccionView(APIView):
    """'No puedo con esta comida': cambiar un alimento, pedir otra opción o comerla por fuera."""

    def post(self, request, pk, accion):
        comida = _comida(request, pk)
        if accion == 'cambiar':
            componente = get_object_or_404(comida.componentes.select_related('alimento'),
                                           pk=request.data.get('componente'))
            menus.cambiar_alimento(comida, componente, request.data.get('alimento'))
        elif accion == 'sugerir':
            motivo = request.data.get('motivo')
            if motivo not in menus.MOTIVOS:
                raise ReglaNegocioError('Cuéntanos por qué la cambias.')
            menus.sugerir(comida, motivo)
        elif accion == 'por-fuera':
            menus.marcar_por_fuera(comida, bool(request.data.get('por_fuera')))
        else:
            return Response(status=status.HTTP_404_NOT_FOUND)
        return _respuesta_menu(comida.menu)


def _fecha_de(texto, por_defecto):
    return (parse_date(texto) if texto else None) or por_defecto


class RegistroComidaListCreateView(APIView):
    """Contar lo que se comió en una comida (con foto y nota opcionales)."""
    parser_classes = [MultiPartParser, JSONParser]

    def get(self, request):
        hoy = timezone.localdate()
        desde = _fecha_de(request.query_params.get('desde'), hoy - timedelta(days=6))
        hasta = _fecha_de(request.query_params.get('hasta'), hoy)
        registros = RegistroComida.objects.filter(usuario=request.user, fecha__range=(desde, hasta))
        return Response(RegistroComidaSerializer(registros, many=True).data)

    def post(self, request):
        datos = RegistroComidaCrearSerializer(data=request.data)
        datos.is_valid(raise_exception=True)
        d = datos.validated_data
        fecha = d.get('fecha') or timezone.localdate()
        with transaction.atomic():
            registro = comidas.registrar(request.user, fecha, d['tiempo'], d['avances'],
                                         nota=d['nota'], archivo=d.get('foto'))
            notificaciones.registrar_tomas_de_comida(request.user, fecha, d['tiempo'], set(d['tomas']))
        notificaciones.resolver_automaticas(request.user)
        return Response(RegistroComidaSerializer(registro).data, status=status.HTTP_201_CREATED)


class RegistroComidaFotoView(APIView):
    """Entrega la foto solo a su dueño (?tamano=mini para la miniatura)."""

    def get(self, request, pk):
        registro = get_object_or_404(RegistroComida, pk=pk, usuario=request.user)
        archivo = registro.miniatura if request.query_params.get('tamano') == 'mini' else registro.foto
        if not archivo:
            return Response({'detail': 'Esta comida no tiene foto.'}, status=status.HTTP_404_NOT_FOUND)
        respuesta = FileResponse(archivo.open('rb'), content_type='image/jpeg')
        respuesta['Cache-Control'] = 'private, max-age=31536000, immutable'
        return respuesta


class PedidoComidaView(APIView):
    """Lo que la minuta pide en una comida, para saber qué preguntar al contarla."""

    def get(self, request):
        tiempo = request.query_params.get('tiempo', '')
        fecha = _fecha_de(request.query_params.get('fecha'), timezone.localdate())
        pedidos = comidas.pedido(request.user, fecha, tiempo)
        return Response({
            'fecha': fecha, 'tiempo': tiempo, 'tiempo_nombre': NOMBRE_TIEMPO.get(tiempo, tiempo),
            'grupos': [{'grupo': g, 'nombre': NOMBRE_GRUPO[g], 'porciones': float(p)} for g, p in pedidos.items()],
            'contada': RegistroComida.objects.filter(usuario=request.user, fecha=fecha, tiempo=tiempo).exists(),
            # Lo que se toma en esta comida (la proteína va aquí y no en un aviso aparte).
            'tomas': [{
                'suplemento': s.id, 'nombre': s.nombre_visible, 'scoops': toma.get('scoops'),
                'reemplaza': [{'grupo': g, 'nombre': NOMBRE_GRUPO[g], 'porciones': p}
                              for g, p in toma['reemplaza'].items()],
                'tomada': notificaciones.toma_registrada(request.user, fecha, s, tiempo),
            } for s, toma in comidas.tomas_de(request.user, fecha, tiempo)],
        })


class ProyeccionView(APIView):
    """Cuánto podría cambiar el peso hasta el próximo control, con todo lo que ya sabemos."""

    def get(self, request):
        return Response(proyeccion.proyectar(request.user, timezone.localdate()))


class IlustracionView(APIView):
    """Las ilustraciones del cambio estimado: lista y estado (GET) y generar una (POST)."""

    def get(self, request):
        return Response({
            'disponible': ilustracion.disponible(),
            'restantes_hoy': ilustracion.restantes_hoy(request.user),
            'ilustraciones': IlustracionSerializer(request.user.ilustraciones.all(), many=True).data,
        })

    def post(self, request):
        nueva = ilustracion.generar(request.user, request.data.get('consentimiento'))
        return Response(IlustracionSerializer(nueva).data, status=status.HTTP_201_CREATED)


class IlustracionImagenView(APIView):
    """La imagen es privada: solo su dueño la ve y la puede borrar."""

    def get(self, request, pk):
        obj = get_object_or_404(Ilustracion, pk=pk, usuario=request.user)
        respuesta = FileResponse(obj.imagen.open('rb'), content_type='image/jpeg')
        respuesta['Cache-Control'] = 'private, max-age=31536000, immutable'
        return respuesta

    def delete(self, request, pk):
        get_object_or_404(Ilustracion, pk=pk, usuario=request.user).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class CumplimientoView(APIView):
    """Cuánto de la minuta se cumplió: ?periodo=hoy|semana|mes (o desde y hasta)."""

    def get(self, request):
        hoy = timezone.localdate()
        periodo = request.query_params.get('periodo', 'semana')
        if request.query_params.get('desde'):
            desde = _fecha_de(request.query_params.get('desde'), hoy)
            hasta = _fecha_de(request.query_params.get('hasta'), hoy)
        else:
            desde = {'hoy': hoy, 'semana': minutas.lunes(hoy), 'mes': hoy.replace(day=1)}.get(periodo)
            if desde is None:
                raise ReglaNegocioError('El periodo es hoy, semana o mes.')
            hasta = hoy
        if desde > hasta:
            raise ReglaNegocioError('La fecha de inicio no puede ser después de la final.')
        return Response(comidas.cumplimiento(request.user, desde, hasta))


class SuplementoFotoView(APIView):
    """La foto del producto: solo su dueño la ve."""
    parser_classes = [MultiPartParser]

    def _suplemento(self, request, pk):
        return get_object_or_404(Suplemento.objects.select_related('proceso'), pk=pk, usuario=request.user)

    def get(self, request, pk):
        s = self._suplemento(request, pk)
        if not s.foto:
            return Response({'detail': 'Este suplemento no tiene foto.'}, status=status.HTTP_404_NOT_FOUND)
        respuesta = FileResponse(s.foto.open('rb'), content_type='image/jpeg')
        respuesta['Cache-Control'] = 'private, max-age=3600'
        return respuesta

    def post(self, request, pk):
        datos = SubirMinutaSerializer(data=request.data)
        datos.is_valid(raise_exception=True)
        s = suplementos.guardar_foto(self._suplemento(request, pk), datos.validated_data['archivo'])
        return Response(SuplementoSerializer(s).data)

    def delete(self, request, pk):
        return Response(SuplementoSerializer(suplementos.quitar_foto(self._suplemento(request, pk))).data)


class SuplementoLeerTablaView(APIView):
    """Lee la tabla nutricional de la etiqueta con IA y la propone; la persona la confirma."""

    def post(self, request, pk):
        s = get_object_or_404(Suplemento.objects.select_related('proceso'), pk=pk, usuario=request.user)
        return Response(suplementos.leer_tabla(s))


class SuplementoInfoView(APIView):
    """La foto o el PDF de la etiqueta del suplemento: solo su dueño lo ve."""
    parser_classes = [MultiPartParser]

    def _suplemento(self, request, pk):
        return get_object_or_404(Suplemento.objects.select_related('proceso'), pk=pk, usuario=request.user)

    def get(self, request, pk):
        s = self._suplemento(request, pk)
        if not s.info_archivo:
            return Response({'detail': 'Este suplemento no tiene archivo.'}, status=status.HTTP_404_NOT_FOUND)
        tipo = mimetypes.guess_type(s.info_archivo.name)[0] or 'application/octet-stream'
        respuesta = FileResponse(s.info_archivo.open('rb'), content_type=tipo)
        respuesta['Cache-Control'] = 'private, max-age=3600'
        return respuesta

    def post(self, request, pk):
        datos = SubirMinutaSerializer(data=request.data)
        datos.is_valid(raise_exception=True)
        s = suplementos.guardar_info_archivo(self._suplemento(request, pk), datos.validated_data['archivo'])
        return Response(SuplementoSerializer(s).data)

    def delete(self, request, pk):
        s = suplementos.quitar_info_archivo(self._suplemento(request, pk))
        return Response(SuplementoSerializer(s).data)
