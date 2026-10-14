from contextlib import contextmanager
from datetime import date, datetime, time, timedelta
from unittest import mock

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from agenda import notificaciones
from agenda.models import Notificacion
from users.models import Usuario

from . import diario
from .models import GastoNoMensual, Proyecto

HOY = timezone.localdate


@contextmanager
def el_dia(dia, hora=12):
    with mock.patch('django.utils.timezone.now',
                    return_value=timezone.make_aware(datetime.combine(dia, time(hora, 0)))):
        yield


class DiarioTest(APITestCase):
    def setUp(self):
        self.usuario = Usuario.objects.create_user(username='d@x.co', email='d@x.co', nombre='D',
                                                   password='clave-segura-123')
        # Los avisos solo salen desde que la persona se registró.
        Usuario.objects.filter(pk=self.usuario.pk).update(date_joined=timezone.now() - timedelta(days=2))
        self.usuario.refresh_from_db()
        self.client.force_authenticate(self.usuario)
        area = self.client.post(reverse('crecimiento-areas'), {'nombre': 'Educación financiera'}, format='json').data
        proceso = self.client.post(reverse('crecimiento-procesos'),
                                   {'area': area['id'], 'programa': 'sana_tus_finanzas'}, format='json').data
        self.proyecto = Proyecto.objects.get(proceso_id=proceso['id'], clave='diario_gastos')
        self.url = reverse('diario-mes', args=[self.proyecto.id])

    def mes(self, mes=None):
        r = self.client.get(self.url, {'mes': mes} if mes else {})
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        return r.data

    def anotar(self, **extra):
        datos = {'valor': 9000, 'descripcion': 'Tinto y pastel', 'categoria': 'entretenimiento',
                 'clase': 'emocional', **extra}
        return self.client.post(reverse('diario-gastos', args=[self.proyecto.id]), datos, format='json')

    def test_la_relacion_del_mes_empieza_con_la_lista_del_libro_y_el_siguiente_copia_la_anterior(self):
        d = self.mes('2026-10')
        self.assertEqual(d['rubros_de'], 'plantilla')
        self.assertIn('Arriendo', [r['nombre'] for r in d['rubros']])
        self.assertEqual([c['id'] for c in d['categorias']][:3], ['hogar', 'transporte', 'salud'])
        rubros = [{'categoria': 'hogar', 'nombre': 'Arriendo', 'valor': 1200000, 'cerebral': 1200000},
                  {'categoria': 'estilo_vida', 'nombre': 'Ropa para mí', 'valor': 200000, 'cerebral': 50000}]
        r = self.client.put(self.url + '?mes=2026-10', {'rubros': rubros}, format='json')
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        rel = r.data['resumen']['relacion']
        self.assertEqual((rel['total'], rel['cerebral'], rel['emocional']), (1400000, 1250000, 150000))
        nov = self.mes('2026-11')
        self.assertEqual((nov['rubros_de'], len(nov['rubros'])), ('2026-10', 2))
        # Lo cerebral no pasa del valor.
        malo = [{'categoria': 'hogar', 'nombre': 'Gas', 'valor': 10, 'cerebral': 20}]
        self.assertEqual(self.client.put(self.url + '?mes=2026-10', {'rubros': malo}, format='json').status_code,
                         status.HTTP_400_BAD_REQUEST)

    def test_un_gasto_anual_se_divide_entre_12_y_entre_los_meses_que_faltan(self):
        r = self.client.post(reverse('diario-no-mensuales', args=[self.proyecto.id]) + '?mes=2026-10',
                             {'nombre': 'SOAT', 'valor': 550000, 'periodicidad': 'anual', 'mes_pago': 3},
                             format='json')
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        soat = r.data['no_mensuales'][0]
        # Octubre → marzo: faltan 5 meses (oct, nov, dic, ene, feb).
        self.assertEqual((soat['total_anual'], soat['mensual'], soat['meses_faltan'], soat['ahorro_hasta_pago']),
                         (550000, 45834, 5, 110000))
        r = self.client.post(reverse('diario-no-mensuales', args=[self.proyecto.id]) + '?mes=2026-10',
                             {'nombre': 'Prima', 'valor': 850000, 'periodicidad': 'semestral', 'mes_pago': 6},
                             format='json')
        prima = next(n for n in r.data['no_mensuales'] if n['nombre'] == 'Prima')
        # Junio y diciembre: el total del año es dos pagos; el próximo, en diciembre (faltan 2).
        self.assertEqual((prima['total_anual'], prima['mensual'], prima['meses_faltan']), (1700000, 141667, 2))
        self.assertEqual(r.data['resumen']['provision']['mensual'], 45834 + 141667)
        g = GastoNoMensual.objects.get(nombre='SOAT')
        self.assertEqual(diario.meses_que_faltan(g, date(2026, 3, 1)), 0)

    def test_un_gasto_hormiga_por_30_dias_y_por_12_meses(self):
        r = self.client.post(reverse('diario-hormigas', args=[self.proyecto.id]),
                             {'nombre': 'Café y snack', 'valor_dia': 9000}, format='json')
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        h = r.data['hormiga'][0]
        self.assertEqual((h['mensual'], h['anual'], h['clase']), (270000, 3240000, 'emocional'))
        r = self.client.patch(reverse('diario-hormiga', args=[self.proyecto.id, h['id']]),
                              {'dias_mes': 20}, format='json')
        self.assertEqual(r.data['hormiga'][0]['mensual'], 180000)

    def test_el_registro_es_sincero_y_cuenta_los_dias_al_dia(self):
        self.assertEqual(self.anotar().status_code, status.HTTP_201_CREATED)
        r = self.anotar(valor=120000, descripcion='Mercado', categoria='hogar', clase='cerebral')
        d = r.data
        self.assertEqual((d['resumen']['anotado']['total'], d['resumen']['anotado']['emocional']), (129000, 9000))
        self.assertTrue(d['hoy_al_dia'])
        self.assertEqual(d['resumen']['dias_al_dia'], 1)
        # Mañana ya no se puede borrar; hoy sí (por si fue un error).
        gasto = d['registro'][0]
        self.assertTrue(gasto['se_puede_borrar'])
        with el_dia(HOY() + timedelta(days=1)):
            self.assertEqual(self.client.delete(reverse('diario-gasto', args=[self.proyecto.id, gasto['id']]))
                             .status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.client.delete(reverse('diario-gasto', args=[self.proyecto.id, gasto['id']]))
                         .status_code, status.HTTP_200_OK)
        # Validaciones: futuro, muy atrás, sin descripción, sin clase.
        self.assertEqual(self.anotar(fecha=(HOY() + timedelta(days=1)).isoformat()).status_code, 400)
        self.assertEqual(self.anotar(fecha=(HOY() - timedelta(days=8)).isoformat()).status_code, 400)
        self.assertEqual(self.anotar(descripcion=' ').status_code, 400)
        self.assertEqual(self.anotar(clase='').status_code, 400)
        self.proyecto.refresh_from_db()
        self.assertIn('anotados', self.client.get(reverse('crecimiento-proyecto', args=[self.proyecto.id]))
                      .data['resumen'])

    def test_hoy_no_gaste_y_luego_un_gasto_manda_el_gasto(self):
        sin = reverse('diario-sin-gasto', args=[self.proyecto.id])
        self.assertEqual(self.client.post(sin, {}, format='json').status_code, status.HTTP_201_CREATED)
        self.assertTrue(self.mes()['hoy_al_dia'])
        self.anotar()
        d = self.mes()
        self.assertEqual(d['sin_gasto'], [])
        self.assertEqual(self.client.post(sin, {}, format='json').status_code, status.HTTP_400_BAD_REQUEST)

    def test_el_aviso_de_la_noche_llega_a_la_bandeja_y_hoy_no_gaste_lo_confirma(self):
        hoy = HOY()
        notificaciones.generar(self.usuario, timezone.make_aware(datetime.combine(hoy, time(20, 30))))
        n = Notificacion.objects.get(tipo='crecimiento')
        self.assertEqual((n.titulo, notificaciones.accion_de(n)), ('¿En qué gastaste hoy?', 'Hoy no gasté'))
        self.assertEqual(notificaciones.url_de(n), f'/crecimiento?proyecto={self.proyecto.id}')
        r = self.client.post(reverse('aviso-confirmar', args=[n.id]))
        self.assertEqual(r.status_code, status.HTTP_204_NO_CONTENT)
        self.assertTrue(self.proyecto.dias_sin_gasto.filter(fecha=hoy).exists())

    def test_el_aviso_se_va_solo_si_anota_un_gasto_y_no_sale_si_ya_esta_al_dia(self):
        hoy = HOY()
        notificaciones.generar(self.usuario, timezone.make_aware(datetime.combine(hoy, time(20, 30))))
        self.anotar()
        notificaciones.resolver_automaticas(self.usuario)
        self.assertEqual(Notificacion.objects.get(tipo='crecimiento').resolucion, 'automatica')
        Notificacion.objects.all().delete()
        notificaciones.generar(self.usuario, timezone.make_aware(datetime.combine(hoy, time(21, 0))))
        self.assertFalse(Notificacion.objects.filter(tipo='crecimiento').exists())

    def test_sin_avisos_si_la_persona_los_apaga_en_el_proyecto(self):
        r = self.client.patch(reverse('crecimiento-proyecto', args=[self.proyecto.id]),
                              {'datos': {'avisar': False, 'hora_aviso': '21:00'}}, format='json')
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        notificaciones.generar(self.usuario, timezone.make_aware(datetime.combine(HOY(), time(22, 0))))
        self.assertFalse(Notificacion.objects.filter(tipo='crecimiento').exists())
        self.assertEqual(self.client.patch(reverse('crecimiento-proyecto', args=[self.proyecto.id]),
                                           {'datos': {'hora_aviso': 'tarde'}}, format='json').status_code, 400)

    def test_lo_de_otra_persona_no_se_toca(self):
        otro = Usuario.objects.create_user(username='z@x.co', email='z@x.co', nombre='Z', password='clave-segura-123')
        self.client.force_authenticate(otro)
        self.assertEqual(self.client.get(self.url).status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(self.anotar().status_code, status.HTTP_404_NOT_FOUND)
