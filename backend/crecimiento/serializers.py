from django.utils import timezone
from rest_framework import serializers

from core.exceptions import ReglaNegocioError

from .models import Area, Nota, Proceso, Proyecto
from .programas import PROGRAMAS
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
        return _promedio(p for proceso in area.procesos.all() for p in proceso.proyectos.all())


class ProcesoSerializer(serializers.ModelSerializer):
    proyectos = serializers.IntegerField(source='proyectos.count', read_only=True)
    avance    = serializers.SerializerMethodField()

    class Meta:
        model  = Proceso
        fields = ['id', 'area', 'titulo', 'fuente', 'fuente_titulo', 'autor', 'nota', 'estado', 'programa',
                  'fecha_inicio', 'fecha_fin', 'proyectos', 'avance']
        read_only_fields = ['proyectos', 'avance']
        extra_kwargs = {'titulo': {'required': False}}

    def validate_programa(self, programa):
        if self.instance and programa != self.instance.programa:
            raise serializers.ValidationError('Un proceso no cambia de programa.')
        if programa and programa not in PROGRAMAS:
            raise serializers.ValidationError('Ese programa no existe.')
        return programa

    def create(self, validated_data):
        # Un programa del catálogo trae su fuente y sus proyectos ya puestos.
        programa = PROGRAMAS.get(validated_data.get('programa') or '')
        if programa:
            for campo in ('titulo', 'fuente', 'fuente_titulo', 'autor'):
                validated_data.setdefault(campo, getattr(programa, campo))
        if not programa:
            raise serializers.ValidationError({'programa': 'Elige un programa del catálogo.'})
        proceso = super().create(validated_data)
        if programa:
            for i, base in enumerate(programa.proyectos):
                proyecto = Proyecto.objects.create(proceso=proceso, tipo=base.tipo, clave=base.clave,
                                                   titulo=base.titulo, detalle=base.detalle, orden=i,
                                                   datos=TIPOS[base.tipo].valida({}))
                _calcular_avance(proyecto)
        return proceso

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
        return _promedio(proceso.proyectos.all())


class ProyectoSerializer(serializers.ModelSerializer):
    tipo_nombre = serializers.SerializerMethodField()
    resumen     = serializers.SerializerMethodField()
    calcula_avance = serializers.SerializerMethodField()
    con_avance  = serializers.SerializerMethodField()
    notas       = serializers.IntegerField(source='notas.count', read_only=True)

    class Meta:
        model  = Proyecto
        fields = ['id', 'proceso', 'tipo', 'tipo_nombre', 'clave', 'titulo', 'detalle', 'orden', 'estado', 'avance',
                  'calcula_avance', 'con_avance', 'datos', 'resumen', 'notas', 'creado', 'actualizado']
        read_only_fields = ['tipo_nombre', 'clave', 'calcula_avance', 'con_avance', 'resumen', 'notas', 'creado',
                            'actualizado']
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
        if 'datos' in attrs or not self.instance:
            try:
                datos = TIPOS[tipo].valida(attrs.get('datos', {}))
            except ReglaNegocioError as e:
                raise serializers.ValidationError({'datos': str(e)})
            # Lo que solo cambia el servidor (lo cumplido) se queda como estaba.
            for llave in TIPOS[tipo].del_servidor:
                datos.pop(llave, None)
                if self.instance and llave in self.instance.datos:
                    datos[llave] = self.instance.datos[llave]
            attrs['datos'] = datos
        # Si el tipo calcula su avance, sale de lo que hizo la persona y no se manda a mano.
        if TIPOS[tipo].avance is not None:
            attrs.pop('avance', None)
            attrs.pop('estado', None)
        attrs['actualizado'] = timezone.now()
        return attrs

    def create(self, validated_data):
        proyecto = super().create(validated_data)
        if 'estado' not in validated_data:
            avance = proyecto.avance
            proyecto.estado = 'terminado' if avance >= 100 else 'en_curso' if avance else 'por_empezar'
            proyecto.save(update_fields=['estado'])
        return _calcular_avance(proyecto)

    def update(self, instance, validated_data):
        return _calcular_avance(super().update(instance, validated_data))

    def get_calcula_avance(self, proyecto):
        return proyecto.tipo in TIPOS and TIPOS[proyecto.tipo].avance is not None

    def get_con_avance(self, proyecto):
        return _con_avance(proyecto)

    def get_tipo_nombre(self, proyecto):
        return TIPOS[proyecto.tipo].nombre if proyecto.tipo in TIPOS else proyecto.tipo

    def get_resumen(self, proyecto):
        return TIPOS[proyecto.tipo].resumen(proyecto) if proyecto.tipo in TIPOS else ''


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


def _calcular_avance(proyecto):
    """Si el tipo calcula su avance, se pone al día (y el estado con él)."""
    calculo = TIPOS[proyecto.tipo].avance if proyecto.tipo in TIPOS else None
    if calculo is not None:
        avance = max(0, min(100, int(calculo(proyecto))))
        estado = 'terminado' if avance >= 100 else 'en_curso' if avance else 'por_empezar'
        if (avance, estado) != (proyecto.avance, proyecto.estado):
            proyecto.avance, proyecto.estado = avance, estado
            proyecto.save(update_fields=['avance', 'estado'])
    return proyecto


def _con_avance(proyecto):
    return proyecto.tipo not in TIPOS or TIPOS[proyecto.tipo].con_avance


def _promedio(proyectos):
    """El avance promedio de unos proyectos, sin los que no tienen un porcentaje con sentido."""
    valores = [p.avance for p in proyectos if _con_avance(p)]
    return round(sum(valores) / len(valores)) if valores else 0
