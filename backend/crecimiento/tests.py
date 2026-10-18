from datetime import date, datetime, time, timedelta
from unittest import mock

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from agenda import notificaciones
from agenda.models import Notificacion
from users.models import Usuario

from .creencias import LLAVES, rachas
from .models import Proyecto

HOY = timezone.localdate


class Base(APITestCase):
    def setUp(self):
        self.usuario = Usuario.objects.create_user(username='c@x.co', email='c@x.co', nombre='C',
                                                   password='clave-segura-123')
        Usuario.objects.filter(pk=self.usuario.pk).update(date_joined=timezone.now() - timedelta(days=2))
        self.usuario.refresh_from_db()
        self.otro = Usuario.objects.create_user(username='o@x.co', email='o@x.co', nombre='O',
                                                password='clave-segura-123')
        self.client.force_authenticate(self.usuario)

    def crear_area(self, nombre='Educación financiera'):
        r = self.client.post(reverse('crecimiento-areas'), {'nombre': nombre}, format='json')
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        return r.data

    def crear_proceso(self, area):
        r = self.client.post(reverse('crecimiento-procesos'), {'area': area['id'], 'programa': 'sana_tus_finanzas'},
                             format='json')
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        return r.data

    def proyecto(self, proceso, clave):
        return next(p for p in self.client.get(reverse('crecimiento-proyectos'), {'proceso': proceso['id']}).data
                    if p['clave'] == clave)


class CrecimientoTest(Base):
    def test_el_programa_del_catalogo_trae_su_fuente_y_sus_dos_actividades(self):
        programas = self.client.get(reverse('crecimiento-programas')).data
        self.assertEqual([p['id'] for p in programas], ['sana_tus_finanzas', 'salud_protocolo'])
        proceso = self.crear_proceso(self.crear_area())
        self.assertEqual((proceso['fuente_titulo'], proceso['autor'], proceso['proyectos']),
                         ('Sana tus finanzas, transforma tu vida', 'Jaime Jaramillo', 2))
        proyectos = self.client.get(reverse('crecimiento-proyectos'), {'proceso': proceso['id']}).data
        self.assertEqual([(p['clave'], p['tipo'], p['detalle']) for p in proyectos],
                         [('taller_creencias', 'taller_creencias', 'Capítulo 1'),
                          ('diario_gastos', 'diario_gastos', 'Capítulo 2 · Paso 1')])
        areas = self.client.get(reverse('crecimiento-areas')).data
        self.assertEqual(areas[0]['procesos'], 1)

    def test_solo_programas_del_catalogo_y_los_proyectos_no_se_crean_ni_se_borran_sueltos(self):
        area = self.crear_area()
        for datos in ({'area': area['id']}, {'area': area['id'], 'programa': 'nada'},
                      {'area': area['id'], 'titulo': 'Mío', 'fuente': 'libro'}):
            self.assertEqual(self.client.post(reverse('crecimiento-procesos'), datos, format='json').status_code,
                             status.HTTP_400_BAD_REQUEST, datos)
        proceso = self.crear_proceso(area)
        r = self.client.post(reverse('crecimiento-proyectos'), {'proceso': proceso['id'], 'titulo': 'X'},
                             format='json')
        self.assertEqual(r.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        taller = self.proyecto(proceso, 'taller_creencias')
        self.assertEqual(self.client.delete(reverse('crecimiento-proyecto', args=[taller['id']])).status_code,
                         status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_validaciones_de_area(self):
        self.crear_area()
        self.assertEqual(self.client.post(reverse('crecimiento-areas'), {'nombre': 'educación FINANCIERA'},
                                          format='json').status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.client.post(reverse('crecimiento-areas'), {'nombre': '  '}, format='json')
                         .status_code, status.HTTP_400_BAD_REQUEST)

    def test_lo_de_otra_persona_no_se_ve_ni_se_toca(self):
        area = self.crear_area()
        taller = self.proyecto(self.crear_proceso(area), 'taller_creencias')
        self.client.force_authenticate(self.otro)
        self.assertEqual(self.client.get(reverse('crecimiento-areas')).data, [])
        self.assertEqual(self.client.get(reverse('crecimiento-area', args=[area['id']])).status_code,
                         status.HTTP_404_NOT_FOUND)
        r = self.client.post(reverse('crecimiento-procesos'), {'area': area['id'], 'programa': 'sana_tus_finanzas'},
                             format='json')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        r = self.client.post(reverse('crecimiento-notas'), {'proyecto': taller['id'], 'texto': 'hola'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.client.post(reverse('crecimiento-accion', args=[taller['id'], 'leer'])).status_code,
                         status.HTTP_404_NOT_FOUND)

    def test_las_notas_de_un_proyecto(self):
        taller = self.proyecto(self.crear_proceso(self.crear_area()), 'taller_creencias')
        for texto in ('Primera', 'Segunda'):
            r = self.client.post(reverse('crecimiento-notas'), {'proyecto': taller['id'], 'texto': texto},
                                 format='json')
            self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        self.assertEqual([n['texto'] for n in self.client.get(reverse('crecimiento-notas'),
                                                              {'proyecto': taller['id']}).data], ['Segunda', 'Primera'])
        self.assertEqual(self.client.post(reverse('crecimiento-notas'), {'proyecto': taller['id'], 'texto': ' '},
                                          format='json').status_code, status.HTTP_400_BAD_REQUEST)

    def test_borrar_un_area_se_lleva_lo_que_tiene_dentro(self):
        area = self.crear_area()
        taller = self.proyecto(self.crear_proceso(area), 'taller_creencias')
        self.client.post(reverse('crecimiento-notas'), {'proyecto': taller['id'], 'texto': 'x'}, format='json')
        self.assertEqual(self.client.delete(reverse('crecimiento-area', args=[area['id']])).status_code,
                         status.HTTP_204_NO_CONTENT)
        self.assertFalse(Proyecto.objects.exists())


class TallerDeCreenciasTest(Base):
    def setUp(self):
        super().setUp()
        self.taller = self.proyecto(self.crear_proceso(self.crear_area()), 'taller_creencias')
        self.url = reverse('crecimiento-proyecto', args=[self.taller['id']])

    def guardar(self, datos):
        r = self.client.patch(self.url, {'datos': datos}, format='json')
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        return r.data

    def test_los_cuatro_pasos_suman_al_avance(self):
        todas_no = {k: 'no' for k in LLAVES}
        self.assertEqual(self.guardar({'ans': todas_no})['avance'], 100)
        ans = {**todas_no, 'a0': 'si', 'c1': 'si'}
        d = self.guardar({'ans': ans})
        self.assertEqual((d['avance'], d['resumen']), (25, 'Cuestionario: 16 de 16'))
        d = self.guardar({'ans': ans, 'ref': {'a0': {'a': 'A cobrar poco', 'b': 'Cobrar lo justo'}}})
        self.assertEqual(d['avance'], 38)
        d = self.guardar({'ans': ans, 'ref': {'a0': {'a': 'x', 'b': 'y'}, 'c1': {'a': 'x', 'b': 'y'}},
                          'pos': {'a0': 'Merezco una vida próspera.', 'c1': 'Ahorrar es pagarme primero a mí.'}})
        self.assertEqual((d['avance'], d['resumen']), (75, '2 creencias nuevas · 0 de 21 días seguidos'))
        # Lo que no es del cuestionario se ignora.
        d = self.guardar({'ans': {**ans, 'z9': 'si', 'a1': 'quizas'}, 'ref': d['datos']['ref'], 'pos': d['datos']['pos']})
        self.assertNotIn('z9', d['datos']['ans'])

    def test_los_21_dias_solo_los_marca_el_servidor_y_solo_hoy(self):
        ans = {k: 'no' for k in LLAVES} | {'a0': 'si'}
        accion = reverse('crecimiento-accion', args=[self.taller['id'], 'leer'])
        self.guardar({'ans': ans})
        # Sin creencias nuevas no hay nada que leer.
        self.assertEqual(self.client.post(accion).status_code, status.HTTP_400_BAD_REQUEST)
        self.guardar({'ans': ans, 'pos': {'a0': 'Merezco una vida próspera.'},
                      'dias': ['2026-01-01', '2026-01-02']})
        self.assertEqual(Proyecto.objects.get(pk=self.taller['id']).datos['dias'], [])
        r = self.client.post(accion)
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        self.assertEqual(r.data['datos']['dias'], [HOY().isoformat()])
        self.assertIn('1 de 21 días seguidos', r.data['resumen'])
        # Guardar el resto de respuestas no borra los días cumplidos.
        d = self.guardar({'ans': ans, 'pos': {'a0': 'Merezco una vida próspera y tranquila.'}})
        self.assertEqual(d['datos']['dias'], [HOY().isoformat()])
        self.assertEqual(self.client.post(reverse('crecimiento-accion', args=[self.taller['id'], 'otra'])).status_code,
                         status.HTTP_400_BAD_REQUEST)

    def test_rachas_de_dias_seguidos(self):
        hoy = date(2026, 10, 13)
        dias = [(hoy - timedelta(days=n)).isoformat() for n in (0, 1, 2, 5, 6)]
        self.assertEqual(rachas({'dias': dias}, hoy), (3, 3))
        self.assertEqual(rachas({'dias': dias}, hoy + timedelta(days=2)), (0, 3))

    def test_el_aviso_de_leerlas_llega_a_la_bandeja_y_ya_las_lei_lo_marca(self):
        ans = {k: 'no' for k in LLAVES} | {'a0': 'si'}
        self.guardar({'ans': ans, 'pos': {'a0': 'Merezco una vida próspera.'}, 'hora_aviso': '07:30'})
        notificaciones.generar(self.usuario, timezone.make_aware(datetime.combine(HOY(), time(9, 0))))
        n = Notificacion.objects.get(tipo='crecimiento', datos__aviso='leer')
        self.assertEqual((n.titulo, notificaciones.accion_de(n)), ('Lee tus creencias nuevas', 'Ya las leí'))
        self.assertEqual(self.client.post(reverse('aviso-confirmar', args=[n.id])).status_code,
                         status.HTTP_204_NO_CONTENT)
        self.assertEqual(Proyecto.objects.get(pk=self.taller['id']).datos['dias'], [HOY().isoformat()])
        Notificacion.objects.all().delete()
        notificaciones.generar(self.usuario, timezone.make_aware(datetime.combine(HOY(), time(10, 0))))
        self.assertFalse(Notificacion.objects.filter(datos__aviso='leer').exists())
