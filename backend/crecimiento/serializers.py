from django.utils import timezone
from rest_framework import serializers

from core.exceptions import ReglaNegocioError

from .models import Area, Nota, Proceso, Proyecto
from .tipos import TIPOS


class AreaSerializer(serializers.ModelSerializer):
    procesos = serializers.IntegerField(source='procesos.count', read_only=True)
    avance   = serializers.SerializerMethodField()

    class Meta:
        model  = Area
        fields = ['id', 'nombre', 'icono', 'orden', 'procesos', 'avance']
        read_only_fields = ['procesos', 'avance']

    def validate_nombre(self, nombre):
        nombre = nombre.strip()
        if not nombre:
            raise serializers.ValidationError('Escribe un nombre.')
        existe = Area.objects.filter(usuario=self.context['request'].user, nombre__iexact=nombre)
        if self.instance:
            existe = existe.exclude(pk=self.instance.pk)
        if existe.exists():
            raise serializers.ValidationError('Ya tienes un área con ese nombre.')
        return nombre

    def get_avance(self, area):
        return _promedio(p.avance for proceso in area.procesos.all() for p in proceso.proyectos.all())


class ProcesoSerializer(serializers.ModelSerializer):
    proyectos = serializers.IntegerField(source='proyectos.count', read_only=True)
    avance    = serializers.SerializerMethodField()

    class Meta:
        model  = Proceso
        fields = ['id', 'area', 'titulo', 'fuente', 'fuente_titulo', 'autor', 'nota', 'estado',
                  'fecha_inicio', 'fecha_fin', 'proyectos', 'avance']
        read_only_fields = ['proyectos', 'avance']

    def validate_area(self, area):
        if area.usuario_id != self.context['request'].user.id:
            raise serializers.ValidationError('Esa área no existe.')
        if self.instance and self.instance.area_id != area.id:
            raise serializers.ValidationError('Un proceso no cambia de área.')
        return area

    def validate_titulo(self, titulo):
        titulo = titulo.strip()
        if not titulo:
            raise serializers.ValidationError('Escribe un título.')
        return titulo

    def validate(self, attrs):
        inicio = attrs.get('fecha_inicio') or getattr(self.instance, 'fecha_inicio', None)
        fin = attrs.get('fecha_fin', getattr(self.instance, 'fecha_fin', None))
        if inicio and fin and fin < inicio:
            raise serializers.ValidationError('El final no puede ir antes del inicio.')
        return attrs

    def get_avance(self, proceso):
        return _promedio(p.avance for p in proceso.proyectos.all())


class ProyectoSerializer(serializers.ModelSerializer):
    tipo_nombre = serializers.SerializerMethodField()
    resumen     = serializers.SerializerMethodField()
    notas       = serializers.IntegerField(source='notas.count', read_only=True)

    class Meta:
        model  = Proyecto
        fields = ['id', 'proceso', 'tipo', 'tipo_nombre', 'titulo', 'detalle', 'orden', 'estado', 'avance',
                  'datos', 'resumen', 'notas', 'actualizado']
        read_only_fields = ['tipo_nombre', 'resumen', 'notas', 'actualizado']
        extra_kwargs = {'avance': {'min_value': 0, 'max_value': 100}}

    def validate_proceso(self, proceso):
        if proceso.area.usuario_id != self.context['request'].user.id:
            raise serializers.ValidationError('Ese proceso no existe.')
        if self.instance and self.instance.proceso_id != proceso.id:
            raise serializers.ValidationError('Un proyecto no cambia de proceso.')
        return proceso

    def validate_tipo(self, tipo):
        if tipo not in TIPOS:
            raise serializers.ValidationError('Ese tipo de proyecto no existe.')
        if self.instance and self.instance.tipo != tipo:
            raise serializers.ValidationError('Un proyecto no cambia de tipo.')
        return tipo

    def validate_titulo(self, titulo):
        titulo = titulo.strip()
        if not titulo:
            raise serializers.ValidationError('Escribe un título.')
        return titulo

    def validate(self, attrs):
        tipo = attrs.get('tipo') or getattr(self.instance, 'tipo', 'libre')
        if 'datos' in attrs:
            try:
                attrs['datos'] = TIPOS[tipo].valida(attrs['datos'])
            except ReglaNegocioError as e:
                raise serializers.ValidationError({'datos': str(e)})
        # El avance sale de lo que hizo la persona; un tipo sin cálculo propio deja que ella lo marque.
        avance = attrs.get('avance', getattr(self.instance, 'avance', 0))
        datos = attrs.get('datos', getattr(self.instance, 'datos', {}))
        if tipo != 'libre':
            avance = TIPOS[tipo].avance(datos)
        attrs['avance'] = avance
        if attrs.get('estado') is None and not self.instance:
            attrs['estado'] = 'terminado' if avance >= 100 else 'en_curso' if avance else 'por_empezar'
        attrs['actualizado'] = timezone.now()
        return attrs

    def get_tipo_nombre(self, proyecto):
        return TIPOS[proyecto.tipo].nombre if proyecto.tipo in TIPOS else proyecto.tipo

    def get_resumen(self, proyecto):
        return TIPOS[proyecto.tipo].resumen(proyecto.datos) if proyecto.tipo in TIPOS else ''


class NotaSerializer(serializers.ModelSerializer):
    proyecto_titulo = serializers.CharField(source='proyecto.titulo', read_only=True)

    class Meta:
        model  = Nota
        fields = ['id', 'proyecto', 'proyecto_titulo', 'titulo', 'texto', 'fecha']
        read_only_fields = ['proyecto_titulo', 'fecha']

    def validate_proyecto(self, proyecto):
        if proyecto.proceso.area.usuario_id != self.context['request'].user.id:
            raise serializers.ValidationError('Ese proyecto no existe.')
        if self.instance and self.instance.proyecto_id != proyecto.id:
            raise serializers.ValidationError('Una nota no cambia de proyecto.')
        return proyecto

    def validate_texto(self, texto):
        texto = texto.strip()
        if not texto:
            raise serializers.ValidationError('Escribe la nota.')
        return texto


def _promedio(valores):
    valores = list(valores)
    return round(sum(valores) / len(valores)) if valores else 0
