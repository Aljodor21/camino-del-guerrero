from datetime import date, timedelta

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from users.models import Usuario

from . import salud
from .models import Proyecto

HOY = timezone.localdate


class SaludTest(APITestCase):
    def setUp(self):
        self.usuario = Usuario.objects.create_user(username='s@x.co', email='s@x.co', nombre='S',
                                                   password='clave-segura-123')
        Usuario.objects.filter(pk=self.usuario.pk).update(date_joined=timezone.now() - timedelta(days=30))
        self.usuario.refresh_from_db()
        self.client.force_authenticate(self.usuario)
        area = self.client.post(reverse('crecimiento-areas'), {'nombre': 'Salud'}, format='json').data
        proceso = self.client.post(reverse('crecimiento-procesos'),
                                   {'area': area['id'], 'programa': 'salud_protocolo'}, format='json').data
        self.fadiman = Proyecto.objects.get(proceso_id=proceso['id'], clave='fadiman')
        self.otros = Proyecto.objects.get(proceso_id=proceso['id'], clave='otros_suplementos')

    def ajustar(self, **datos):
        r = self.client.patch(reverse('crecimiento-proyecto', args=[self.fadiman.id]), {'datos': datos},
                              format='json')
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        self.fadiman.refresh_from_db()

    def anotar(self, proyecto, **datos):
        return self.client.post(reverse('salud-tomas', args=[proyecto.id]), datos, format='json')

    def test_el_programa_trae_los_dos_proyectos(self):
        self.assertEqual((self.fadiman.tipo, self.otros.tipo), ('fadiman', 'otros_suplementos'))

    def test_el_ciclo_de_cuatro_dias_y_el_descanso(self):
        datos = {'inicio': '2026-01-01', 'semanas_ciclo': 4, 'semanas_descanso': 2}
        dias = [salud.dia_del_protocolo(datos, date(2026, 1, 1) + timedelta(days=n)) for n in range(5)]
        self.assertEqual([d['dia'] for d in dias], [1, 2, 3, 4, 1])
        self.assertEqual(salud.dia_del_protocolo(datos, date(2026, 1, 28))['fase'], 'ciclo')
        self.assertEqual(salud.dia_del_protocolo(datos, date(2026, 1, 29))['fase'], 'descanso')
        vuelta2 = salud.dia_del_protocolo(datos, date(2026, 1, 1) + timedelta(days=42))
        self.assertEqual((vuelta2['fase'], vuelta2['dia'], vuelta2['vuelta']), ('ciclo', 1, 2))
        self.assertEqual(salud.dia_del_protocolo(datos, date(2025, 12, 31))['fase'], 'sin_empezar')

    def test_los_ajustes_tienen_rangos(self):
        for malo in ({'semanas_ciclo': 3}, {'semanas_ciclo': 9}, {'semanas_descanso': 1},
                     {'semanas_descanso': 5}, {'inicio': '2020-01-01'}, {'inicio': 'mañana'}):
            r = self.client.patch(reverse('crecimiento-proyecto', args=[self.fadiman.id]), {'datos': malo},
                                  format='json')
            self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST, malo)

    def test_toma_del_protocolo_en_dia_uno_y_una_por_dia(self):
        self.ajustar(inicio=HOY().isoformat(), sustancia='Mi sustancia', dosis='0.1 g')
        r = self.anotar(self.fadiman)
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        toma = r.data['tomas'][0]
        self.assertEqual((toma['nombre'], toma['cantidad'], toma['fuera_de_protocolo']),
                         ('Mi sustancia', '0.1 g', False))
        self.assertTrue(r.data['toma_hoy'])
        self.assertEqual(self.anotar(self.fadiman).status_code, status.HTTP_400_BAD_REQUEST)

    def test_una_toma_en_otro_dia_se_anota_marcada(self):
        self.ajustar(inicio=(HOY() - timedelta(days=1)).isoformat(), sustancia='X', dosis='1')
        toma = self.anotar(self.fadiman).data['tomas'][0]
        self.assertTrue(toma['fuera_de_protocolo'])

    def test_observacion_en_dia_de_transicion(self):
        self.ajustar(inicio=(HOY() - timedelta(days=1)).isoformat())
        self.assertEqual(self.anotar(self.fadiman, clase='observacion').status_code, 400)
        self.assertEqual(self.anotar(self.fadiman, clase='observacion', animo=6).status_code, 400)
        r = self.anotar(self.fadiman, clase='observacion', animo=4, energia=3, nota='Tranquilo')
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        self.assertTrue(r.data['observacion_hoy'])
        self.assertEqual(self.anotar(self.fadiman, clase='observacion', animo=2).status_code, 400)

    def test_otros_suplementos(self):
        self.assertEqual(self.anotar(self.otros, nombre='Creatina').status_code, 400)
        self.assertEqual(self.anotar(self.otros, nombre='Creatina', cantidad='5 g').status_code, 201)
        self.assertEqual(self.anotar(self.otros, clase='observacion', animo=3).status_code, 400)
        self.assertEqual(self.anotar(self.otros, nombre='Creatina', cantidad='5 g',
                                     fecha=(HOY() - timedelta(days=8)).isoformat()).status_code, 400)
        d = self.client.get(reverse('salud', args=[self.otros.id])).data
        self.assertEqual(d['frecuentes'], [{'nombre': 'Creatina', 'cantidad': '5 g'}])

    def test_borrar_solo_el_mismo_dia(self):
        toma = self.anotar(self.otros, nombre='Omega 3', cantidad='1').data['tomas'][0]
        antes = timezone.now() - timedelta(days=2)
        from .models import TomaSalud
        TomaSalud.objects.filter(pk=toma['id']).update(anotado=antes)
        self.assertEqual(self.client.delete(reverse('salud-toma', args=[self.otros.id, toma['id']])).status_code, 400)
        TomaSalud.objects.filter(pk=toma['id']).update(anotado=timezone.now())
        self.assertEqual(self.client.delete(reverse('salud-toma', args=[self.otros.id, toma['id']])).status_code, 200)

    def test_no_se_edita_lo_anotado(self):
        self.anotar(self.otros, nombre='Omega 3', cantidad='1')
        toma = self.otros.tomas_salud.get()
        toma.nota = 'otra'
        from core.exceptions import DatoInmutableError
        with self.assertRaises(DatoInmutableError):
            toma.save()

    def test_lo_de_otra_persona_no_se_ve(self):
        otra = Usuario.objects.create_user(username='o@x.co', email='o@x.co', nombre='O', password='clave-segura-123')
        self.client.force_authenticate(otra)
        self.assertEqual(self.client.get(reverse('salud', args=[self.otros.id])).status_code, 404)
        self.assertEqual(self.anotar(self.otros, nombre='X', cantidad='1').status_code, 404)

    def test_avisos_del_protocolo(self):
        self.ajustar(inicio=HOY().isoformat())
        self.assertEqual([a['clave'] for a in salud.FADIMAN.avisos(self.fadiman, HOY())], ['toma'])
        self.assertEqual([a['clave'] for a in salud.FADIMAN.avisos(self.fadiman, HOY() + timedelta(days=1))],
                         ['observar'])
        self.assertEqual(salud.FADIMAN.avisos(self.fadiman, HOY() + timedelta(days=2)), [])
        self.anotar(self.fadiman, nombre='X', cantidad='1')
        self.assertEqual(salud.FADIMAN.avisos(self.fadiman, HOY()), [])
        fin = HOY() + timedelta(days=28)
        self.assertEqual([a['clave'] for a in salud.FADIMAN.avisos(self.fadiman, fin)], ['descanso'])
        self.ajustar(inicio=HOY().isoformat(), avisar=False)
        self.assertEqual(salud.FADIMAN.avisos(self.fadiman, HOY() + timedelta(days=1)), [])

    def test_avance_es_lo_cumplido_del_primer_ciclo(self):
        self.ajustar(inicio=HOY().isoformat(), semanas_ciclo=4)
        self.anotar(self.fadiman, nombre='X', cantidad='1')
        self.fadiman.refresh_from_db()
        self.assertEqual(self.fadiman.avance, round(100 / 7))

    def test_si_ya_habia_empezado_lo_de_antes_no_cuenta_en_el_avance(self):
        self.ajustar(inicio=(HOY() - timedelta(days=10)).isoformat(), semanas_ciclo=4)
        d = self.client.get(reverse('salud', args=[self.fadiman.id])).data
        self.assertEqual((d['dia']['fase'], d['dia']['semana']), ('ciclo', 2))
        # Las tomas del primer ciclo van en los días 0, 4, 8…24; solo cuentan de hoy (día 10) en adelante.
        self.assertEqual(d['primer_ciclo']['previstas'], 4)


class PlanesSuplementosTest(APITestCase):
    setUp = SaludTest.setUp
    anotar = SaludTest.anotar

    def planes(self, *planes, esperado=status.HTTP_200_OK):
        r = self.client.patch(reverse('crecimiento-proyecto', args=[self.otros.id]),
                              {'datos': {'planes': list(planes)}}, format='json')
        self.assertEqual(r.status_code, esperado, r.data)
        self.otros.refresh_from_db()
        return self.otros.datos.get('planes', [])

    def creatina(self, **extra):
        return {'nombre': 'Creatina', 'cantidad': '5 g', 'dias': list(range(7)), 'horas': ['08:00'], **extra}

    def test_un_plan_se_guarda_limpio_con_su_id(self):
        [p] = self.planes(self.creatina(horas=['20:00', '08:00', '08:00'], duracion_dias=30))
        self.assertEqual(len(p['id']), 8)
        self.assertEqual((p['horas'], p['inicio'], p['duracion_dias']), (['08:00', '20:00'], HOY().isoformat(), 30))
        # Al guardar de nuevo conserva su id.
        [otra] = self.planes(p)
        self.assertEqual(otra['id'], p['id'])

    def test_un_plan_necesita_dias_horas_y_cantidad(self):
        for malo in (self.creatina(dias=[]), self.creatina(horas=[]), self.creatina(horas=['8am']),
                     self.creatina(cantidad=''), self.creatina(duracion_dias=0), self.creatina(dias=[7])):
            self.planes(malo, esperado=status.HTTP_400_BAD_REQUEST)

    def test_toca_segun_dias_y_duracion(self):
        hoy = HOY()
        p = {'inicio': hoy.isoformat(), 'duracion_dias': 3, 'dias': [hoy.weekday()]}
        self.assertTrue(salud.toca(p, hoy))
        self.assertFalse(salud.toca(p, hoy + timedelta(days=1)))
        self.assertFalse(salud.toca({**p, 'dias': list(range(7))}, hoy + timedelta(days=3)))
        self.assertTrue(salud.toca({**p, 'dias': list(range(7)), 'duracion_dias': None}, hoy + timedelta(days=300)))

    def test_avisos_y_ya_lo_tome(self):
        [p] = self.planes(self.creatina(horas=['08:00', '20:00']))
        avisos = salud.SUPLEMENTOS.avisos(self.otros, HOY())
        self.assertEqual([a['clave'] for a in avisos], [f'{p["id"]}@08:00', f'{p["id"]}@20:00'])
        self.assertEqual(avisos[0]['accion'], 'Ya lo tomé')
        salud.SUPLEMENTOS.confirmar(self.otros, f'{p["id"]}@08:00', HOY())
        self.assertTrue(salud.SUPLEMENTOS.resuelto(self.otros, f'{p["id"]}@08:00', HOY()))
        self.assertFalse(salud.SUPLEMENTOS.resuelto(self.otros, f'{p["id"]}@20:00', HOY()))
        toma = self.otros.tomas_salud.get()
        self.assertEqual((toma.nombre, toma.cantidad, toma.plan), ('Creatina', '5 g', f'{p["id"]}@08:00'))

    def test_desde_la_pantalla_con_el_plan(self):
        [p] = self.planes(self.creatina())
        r = self.anotar(self.otros, plan=f'{p["id"]}@08:00')
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        self.assertEqual(r.data['de_hoy'][0]['tomada'], True)
        self.assertEqual(self.anotar(self.otros, plan=f'{p["id"]}@08:00').status_code, 400)
        self.assertEqual(self.anotar(self.otros, plan=f'{p["id"]}@09:00').status_code, 400)

    def test_un_dia_que_no_toca_no_avisa(self):
        otro_dia = (HOY().weekday() + 1) % 7
        self.planes(self.creatina(dias=[otro_dia]))
        self.assertEqual(salud.SUPLEMENTOS.avisos(self.otros, HOY()), [])

    def test_lo_de_ayer_no_se_anota(self):
        self.assertEqual(self.anotar(self.otros, nombre='X', cantidad='1',
                                     fecha=(HOY() - timedelta(days=1)).isoformat()).status_code, 400)
