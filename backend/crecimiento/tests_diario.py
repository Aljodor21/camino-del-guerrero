from contextlib import contextmanager
from datetime import datetime, time, timedelta
from unittest import mock

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from agenda import notificaciones
from agenda.models import Notificacion
from users.models import Usuario

from . import diario
from .models import Proyecto

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
        self.url = reverse('diario', args=[self.proyecto.id])

    def guardar(self, rubros):
        r = self.client.put(self.url, {'rubros': rubros}, format='json')
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        return r.data

    def anotar(self, **extra):
        datos = {'valor': 9000, 'descripcion': 'Tinto y pastel', 'categoria': 'entretenimiento',
                 'clase': 'emocional', **extra}
        return self.client.post(reverse('diario-gastos', args=[self.proyecto.id]), datos, format='json')

    def test_empieza_con_la_lista_del_libro(self):
        d = self.client.get(self.url).data
        self.assertFalse(d['guardados'])
        nombres = {r['nombre']: r['frecuencia'] for r in d['rubros']}
        self.assertEqual((nombres['Arriendo'], nombres['SOAT']), ('mensual', 'anual'))
        self.assertEqual([c['id'] for c in d['categorias']][:3], ['hogar', 'transporte', 'salud'])

    def test_todo_se_suma_en_un_solo_gasto_mensual(self):
        d = self.guardar([
            {'categoria': 'hogar', 'nombre': 'Arriendo', 'valor': 1200000, 'cerebral': 1200000},
            # Mixto: una parte cerebral y otra emocional.
            {'categoria': 'estilo_vida', 'nombre': 'Ropa', 'valor': 200000, 'cerebral': 50000},
            # Anual: se divide entre 12 y se suma al mes.
            {'categoria': 'transporte', 'nombre': 'SOAT', 'frecuencia': 'anual', 'valor': 550000,
             'cerebral': 550000, 'mes_pago': 3},
            # Dos veces al año: dos pagos entre 12.
            {'categoria': 'hogar', 'nombre': 'Prima', 'frecuencia': 'semestral', 'valor': 850000, 'cerebral': 850000},
            # Hormiga: el valor del día por los días del mes.
            {'categoria': 'entretenimiento', 'nombre': 'Café y snack', 'frecuencia': 'hormiga', 'valor': 9000},
        ])
        r = {x['nombre']: x for x in d['rubros']}
        self.assertEqual((r['SOAT']['mensual'], r['SOAT']['al_anio']), (45834, 550000))
        self.assertEqual((r['Prima']['mensual'], r['Prima']['al_anio']), (141667, 1700000))
        self.assertEqual((r['Café y snack']['mensual'], r['Café y snack']['al_anio']), (270000, 3240000))
        self.assertEqual(r['Ropa']['emocional'], 150000)
        self.assertIn('meses_faltan', r['SOAT'])
        plan = d['resumen']['plan']
        self.assertEqual(plan['total'], 1200000 + 200000 + 45834 + 141667 + 270000)
        self.assertEqual(plan['emocional'], 150000 + 270000)
        self.assertEqual(d['resumen']['por_frecuencia']['anual'], 45834)
        # Lo cerebral no pasa del valor, y la frecuencia es una de las cuatro.
        for malo in ({'categoria': 'hogar', 'nombre': 'Gas', 'valor': 10, 'cerebral': 20},
                     {'categoria': 'hogar', 'nombre': 'Gas', 'valor': 10, 'frecuencia': 'cada rato'},
                     {'categoria': 'nada', 'nombre': 'Gas', 'valor': 10}):
            self.assertEqual(self.client.put(self.url, {'rubros': [malo]}, format='json').status_code, 400, malo)

    def test_meses_que_faltan_para_el_pago(self):
        self.assertEqual(diario.meses_que_faltan(3, 'anual', 10), 5)
        self.assertEqual(diario.meses_que_faltan(3, 'anual', 3), 0)
        self.assertEqual(diario.meses_que_faltan(6, 'semestral', 10), 2)

    def test_el_registro_es_sincero_y_cuenta_los_dias_al_dia(self):
        self.assertEqual(self.anotar().status_code, status.HTTP_201_CREATED)
        d = self.anotar(valor=120000, descripcion='Mercado', categoria='hogar', clase='cerebral').data
        self.assertEqual((d['resumen']['anotado']['total'], d['resumen']['anotado']['emocional']), (129000, 9000))
        self.assertTrue(d['hoy_al_dia'])
        self.assertEqual(d['resumen']['dias_al_dia'], 1)
        gasto = d['registro'][0]
        self.assertTrue(gasto['se_puede_borrar'])
        with el_dia(HOY() + timedelta(days=1)):
            self.assertEqual(self.client.delete(reverse('diario-gasto', args=[self.proyecto.id, gasto['id']]))
                             .status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.client.delete(reverse('diario-gasto', args=[self.proyecto.id, gasto['id']]))
                         .status_code, status.HTTP_200_OK)
        self.assertEqual(self.anotar(fecha=(HOY() + timedelta(days=1)).isoformat()).status_code, 400)
        self.assertEqual(self.anotar(fecha=(HOY() - timedelta(days=8)).isoformat()).status_code, 400)
        self.assertEqual(self.anotar(fecha=(HOY() - timedelta(days=1)).isoformat()).status_code, 201)
        self.assertEqual(self.client.post(reverse('diario-sin-gasto', args=[self.proyecto.id]),
                                          {'fecha': (HOY() - timedelta(days=2)).isoformat()}, format='json').status_code, 201)
        self.assertEqual(self.anotar(descripcion=' ').status_code, 400)
        self.assertEqual(self.anotar(clase='').status_code, 400)
        self.assertIn('anotados', self.client.get(reverse('crecimiento-proyecto', args=[self.proyecto.id]))
                      .data['resumen'])

    def test_hoy_no_gaste_y_luego_un_gasto_manda_el_gasto(self):
        sin = reverse('diario-sin-gasto', args=[self.proyecto.id])
        self.assertEqual(self.client.post(sin, {}, format='json').status_code, status.HTTP_201_CREATED)
        self.assertTrue(self.client.get(self.url).data['hoy_al_dia'])
        self.anotar()
        self.assertFalse(self.proyecto.dias_sin_gasto.exists())
        self.assertEqual(self.client.post(sin, {}, format='json').status_code, status.HTTP_400_BAD_REQUEST)

    def test_el_aviso_de_la_noche_llega_a_la_bandeja_y_hoy_no_gaste_lo_confirma(self):
        notificaciones.generar(self.usuario, timezone.make_aware(datetime.combine(HOY(), time(20, 30))))
        n = Notificacion.objects.get(tipo='crecimiento', datos__aviso='dia')
        self.assertEqual((n.titulo, notificaciones.accion_de(n)), ('¿En qué gastaste hoy?', 'Hoy no gasté'))
        self.assertEqual(notificaciones.url_de(n), f'/crecimiento?proyecto={self.proyecto.id}')
        self.assertEqual(self.client.post(reverse('aviso-confirmar', args=[n.id])).status_code,
                         status.HTTP_204_NO_CONTENT)
        self.assertTrue(self.proyecto.dias_sin_gasto.filter(fecha=HOY()).exists())

    def test_el_aviso_se_va_solo_si_anota_un_gasto_y_no_sale_si_ya_esta_al_dia(self):
        notificaciones.generar(self.usuario, timezone.make_aware(datetime.combine(HOY(), time(20, 30))))
        self.anotar()
        notificaciones.resolver_automaticas(self.usuario)
        self.assertEqual(Notificacion.objects.get(datos__aviso='dia').resolucion, 'automatica')
        Notificacion.objects.all().delete()
        notificaciones.generar(self.usuario, timezone.make_aware(datetime.combine(HOY(), time(21, 0))))
        self.assertFalse(Notificacion.objects.filter(datos__aviso='dia').exists())

    def test_sin_avisos_si_la_persona_los_apaga_en_el_proyecto(self):
        r = self.client.patch(reverse('crecimiento-proyecto', args=[self.proyecto.id]),
                              {'datos': {'avisar': False, 'hora_aviso': '21:00'}}, format='json')
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        notificaciones.generar(self.usuario, timezone.make_aware(datetime.combine(HOY(), time(22, 0))))
        self.assertFalse(Notificacion.objects.filter(datos__aviso='dia').exists())
        self.assertEqual(self.client.patch(reverse('crecimiento-proyecto', args=[self.proyecto.id]),
                                           {'datos': {'hora_aviso': 'tarde'}}, format='json').status_code, 400)

    def test_lo_de_otra_persona_no_se_toca(self):
        otro = Usuario.objects.create_user(username='z@x.co', email='z@x.co', nombre='Z', password='clave-segura-123')
        self.client.force_authenticate(otro)
        self.assertEqual(self.client.get(self.url).status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(self.anotar().status_code, status.HTTP_404_NOT_FOUND)
