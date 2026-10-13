import calendar
import uuid
from datetime import date, timedelta

from django.utils import timezone
from rest_framework import serializers

from nutricion import minutas
from nutricion.grupos import HORA_TIEMPO, NOMBRE_TIEMPO

from . import horarios, notificaciones
from .models import Habitos, Notificacion, Recordatorio, RegistroHabito

MAX_DIAS_ADELANTE = 730
MAX_REPETICIONES = 60
REPETICIONES = [('dia', 'Cada día'), ('semana', 'Cada semana'), ('mes', 'Cada mes')]


def _repetida(inicio, cada, n):
    """La fecha de la repetición número `n` (0 es la primera): cada día, semana o mes (el 31 cae a fin de mes)."""
    if cada == 'dia':
        return inicio + timedelta(days=n)
    if cada == 'semana':
        return inicio + timedelta(weeks=n)
    mes = inicio.month - 1 + n
    anio, mes = inicio.year + mes // 12, mes % 12 + 1
    return date(anio, mes, min(inicio.day, calendar.monthrange(anio, mes)[1]))


class RecordatorioSerializer(serializers.ModelSerializer):
    tipo_nombre = serializers.CharField(source='get_tipo_display', read_only=True)
    completado  = serializers.BooleanField(required=False, write_only=True)
    automatico  = serializers.BooleanField(read_only=True)
    # Solo al crear: repetirlo cada día, semana o mes, `veces` veces en total (con la primera).
    repetir     = serializers.ChoiceField(choices=REPETICIONES, required=False, write_only=True)
    veces       = serializers.IntegerField(min_value=2, max_value=MAX_REPETICIONES, required=False, write_only=True)

    class Meta:
        model  = Recordatorio
        fields = ['id', 'tipo', 'tipo_nombre', 'titulo', 'fecha', 'hora', 'nota', 'avisar_dias_antes',
                  'completado', 'completado_en', 'proceso', 'suplemento', 'motivo', 'automatico', 'serie',
                  'repetir', 'veces']
        read_only_fields = ['completado_en', 'proceso', 'suplemento', 'motivo', 'serie']
        extra_kwargs = {'avisar_dias_antes': {'min_value': 0, 'max_value': 30}}

    def validate_titulo(self, titulo):
        titulo = titulo.strip()
        if not titulo:
            raise serializers.ValidationError('Escribe un título.')
        return titulo

    def validate_fecha(self, fecha):
        hoy = timezone.localdate()
        cambia = self.instance is None or self.instance.fecha != fecha
        if cambia and fecha < hoy:
            raise serializers.ValidationError('La fecha no puede estar en el pasado.')
        if fecha > hoy + timedelta(days=MAX_DIAS_ADELANTE):
            raise serializers.ValidationError('La fecha puede estar máximo a dos años.')
        return fecha

    def validate(self, attrs):
        # Los sugeridos se resuelven con las acciones de su suplemento, que los recalculan.
        if self.instance is not None and self.instance.automatico:
            raise serializers.ValidationError('Este recordatorio se resuelve desde su suplemento.')
        if bool(attrs.get('repetir')) != bool(attrs.get('veces')):
            raise serializers.ValidationError('Para repetirlo di cada cuánto y cuántas veces.')
        if attrs.get('repetir') and self.instance is not None:
            raise serializers.ValidationError('Solo se puede repetir al crearlo.')
        if attrs.get('repetir') and (_repetida(attrs['fecha'], attrs['repetir'], attrs['veces'] - 1)
                                     > timezone.localdate() + timedelta(days=MAX_DIAS_ADELANTE)):
            raise serializers.ValidationError('La última repetición puede estar máximo a dos años.')
        # Se marca como hecho cuando llega su fecha, no antes.
        if attrs.get('completado'):
            fecha = attrs.get('fecha') or getattr(self.instance, 'fecha', None)
            if fecha and fecha > timezone.localdate():
                raise serializers.ValidationError('Todavía no llega la fecha: se puede marcar como hecho ese día.')
        return attrs

    def _aplicar_completado(self, validated_data):
        completado = validated_data.pop('completado', None)
        if completado is not None:
            validated_data['completado_en'] = timezone.now() if completado else None
        return validated_data

    def create(self, validated_data):
        cada, veces = validated_data.pop('repetir', None), validated_data.pop('veces', None)
        validated_data = self._aplicar_completado(validated_data)
        if not cada:
            return super().create(validated_data)
        # Cada repetición es un recordatorio con su propia fecha; juntos comparten la serie.
        validated_data['serie'] = uuid.uuid4()
        primero = None
        for n in range(veces):
            r = super().create({**validated_data, 'fecha': _repetida(validated_data['fecha'], cada, n)}
                               if n else validated_data)
            primero = primero or r
        return primero

    def update(self, instance, validated_data):
        return super().update(instance, self._aplicar_completado(validated_data))


def _hora_texto(valor, campo):
    hora = horarios.a_hora(valor)
    if hora is None:
        raise serializers.ValidationError(f'«{campo}» no es una hora válida (ej. 06:30).')
    return hora.isoformat('minutes')


class HabitosSerializer(serializers.ModelSerializer):
    vasos_meta = serializers.SerializerMethodField()
    tiempos_comida = serializers.SerializerMethodField()

    class Meta:
        model  = Habitos
        fields = ['agua_ml', 'vaso_ml', 'vasos_meta', 'hora_levantarse', 'hora_dormir', 'hora_entreno',
                  'avisos_apagados', 'horas_semana', 'horas_comida', 'horas_agua', 'tiempos_comida']
        extra_kwargs = {'agua_ml': {'min_value': 250, 'max_value': 8000},
                        'vaso_ml': {'min_value': 50, 'max_value': 1500}}

    def get_vasos_meta(self, habitos):
        return notificaciones.vasos_meta(habitos)

    def get_tiempos_comida(self, habitos):
        """Las comidas de su plan (solo las que tiene) con la hora a la que come cada una: la suya o, si
        no puso una, la que sale de repartirlas entre levantarse y acostarse."""
        minuta = minutas.vigente_de(habitos.usuario) if habitos.usuario_id else None
        tiempos = list(minuta.tiempos()) if minuta else []
        hoy = timezone.localdate()
        efectivas = horarios.horas_de_comidas(habitos, hoy, tiempos)
        repartidas = horarios.horas_de_comidas(habitos, hoy, tiempos, propias=False)
        return [{'tiempo': t, 'nombre': NOMBRE_TIEMPO[t], 'hora': efectivas[t].isoformat('minutes'),
                 'referencia': repartidas[t].isoformat('minutes'),
                 'personalizada': t in (habitos.horas_comida or {})}
                for t in tiempos]

    def validate_horas_semana(self, valor):
        if not isinstance(valor, dict):
            raise serializers.ValidationError('Formato no válido.')
        limpio = {}
        for dia, horas in valor.items():
            if dia not in {'1', '2', '3', '4', '5', '6', '7'} or not isinstance(horas, dict):
                raise serializers.ValidationError('Día de la semana no válido.')
            entrada = {}
            for clave in ('levantarse', 'dormir'):
                if horas.get(clave):
                    entrada[clave] = _hora_texto(horas[clave], clave)
            if entrada.get('levantarse') and entrada.get('levantarse') == entrada.get('dormir'):
                raise serializers.ValidationError('Levantarte y acostarte no pueden ser a la misma hora.')
            if entrada:
                limpio[dia] = entrada
        # Una hora por día es todo o nada: si no, unos días mandarían una hora y otros otra.
        if limpio and not all(set(limpio.get(str(d), {})) == {'levantarse', 'dormir'} for d in range(1, 8)):
            raise serializers.ValidationError(
                'Con una hora distinta por día, llena levantarse y acostarse de los siete días.')
        return limpio

    def validate_horas_agua(self, valor):
        if not isinstance(valor, dict):
            raise serializers.ValidationError('Formato no válido.')
        limpio = {clave: _hora_texto(valor[clave], clave) for clave in ('inicio', 'fin') if valor.get(clave)}
        if len(limpio) == 2 and limpio['inicio'] >= limpio['fin']:
            raise serializers.ValidationError('El agua debe empezar antes de la hora en que termina.')
        return limpio

    def validate_horas_comida(self, valor):
        if not isinstance(valor, dict):
            raise serializers.ValidationError('Formato no válido.')
        limpio = {}
        for tiempo, hora in valor.items():
            if tiempo not in HORA_TIEMPO:
                raise serializers.ValidationError('Esa comida no existe.')
            if hora:
                limpio[tiempo] = _hora_texto(hora, tiempo)
        return limpio

    def validate_avisos_apagados(self, apagados):
        tipos = dict(Notificacion.TIPOS)
        if not isinstance(apagados, list) or any(t not in tipos for t in apagados):
            raise serializers.ValidationError('Tipo de aviso desconocido.')
        return sorted(set(apagados))

    def validate(self, datos):
        levantarse = datos.get('hora_levantarse', getattr(self.instance, 'hora_levantarse', None))
        dormir = datos.get('hora_dormir', getattr(self.instance, 'hora_dormir', None))
        if levantarse and dormir and levantarse == dormir:
            raise serializers.ValidationError({'hora_dormir': 'No puede ser la misma hora en que te levantas.'})
        return datos


class HorarioDiaSerializer(serializers.Serializer):
    """Las horas de un solo día. Vacío = usar la de siempre."""
    hora_levantarse = serializers.TimeField(allow_null=True, required=False)
    hora_dormir     = serializers.TimeField(allow_null=True, required=False)

    def validate(self, datos):
        if datos.get('hora_levantarse') and datos.get('hora_levantarse') == datos.get('hora_dormir'):
            raise serializers.ValidationError('Levantarte y acostarte no pueden ser a la misma hora.')
        return datos


class NotificacionSerializer(serializers.ModelSerializer):
    accion = serializers.SerializerMethodField()
    cuerpo = serializers.SerializerMethodField()

    class Meta:
        model  = Notificacion
        fields = ['id', 'tipo', 'fecha', 'programada_para', 'titulo', 'cuerpo', 'accion', 'suplemento',
                  'recordatorio', 'datos']
        read_only_fields = fields

    def get_accion(self, n):
        return notificaciones.accion_de(n)

    def get_cuerpo(self, n):
        return notificaciones.cuerpo_de(n)


class RegistroHabitoSerializer(serializers.ModelSerializer):
    class Meta:
        model  = RegistroHabito
        fields = ['id', 'tipo', 'fecha', 'momento', 'cantidad', 'ml', 'suplemento', 'tiempo']
        read_only_fields = fields


class SuscripcionPushSerializer(serializers.Serializer):
    endpoint = serializers.URLField(max_length=600)
    keys     = serializers.DictField(child=serializers.CharField(max_length=200))

    def validate_endpoint(self, endpoint):
        if not endpoint.startswith('https://'):
            raise serializers.ValidationError('La suscripción debe ser https.')
        return endpoint

    def validate_keys(self, keys):
        if not keys.get('p256dh') or not keys.get('auth'):
            raise serializers.ValidationError('Faltan las llaves de la suscripción.')
        return keys
