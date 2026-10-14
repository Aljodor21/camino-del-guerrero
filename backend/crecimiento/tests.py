from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from users.models import Usuario

from .tipos import TIPOS, Tipo


class CrecimientoTest(APITestCase):
    def setUp(self):
        self.usuario = Usuario.objects.create_user(username='c@x.co', email='c@x.co', nombre='C',
                                                   password='clave-segura-123')
        self.otro = Usuario.objects.create_user(username='o@x.co', email='o@x.co', nombre='O',
                                                password='clave-segura-123')
        self.client.force_authenticate(self.usuario)

    def crear_area(self, nombre='Educación financiera'):
        r = self.client.post(reverse('crecimiento-areas'), {'nombre': nombre}, format='json')
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        return r.data

    def crear_proceso(self, area):
        r = self.client.post(reverse('crecimiento-procesos'), {
            'area': area['id'], 'titulo': 'Sana tus finanzas', 'fuente': 'libro',
            'fuente_titulo': 'Sana tus finanzas, transforma tu vida', 'autor': 'Jaime Jaramillo'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        return r.data

    def crear_proyecto(self, proceso, **extra):
        r = self.client.post(reverse('crecimiento-proyectos'), {
            'proceso': proceso['id'], 'titulo': 'Capítulo 1', **extra}, format='json')
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        return r.data

    def test_un_area_con_su_proceso_segun_un_libro_y_sus_proyectos(self):
        area = self.crear_area()
        proceso = self.crear_proceso(area)
        self.assertEqual((proceso['fuente'], proceso['autor']), ('libro', 'Jaime Jaramillo'))
        p1 = self.crear_proyecto(proceso, avance=100, estado='terminado')
        self.crear_proyecto(proceso, titulo='Capítulo 2')
        self.assertEqual(p1['tipo'], 'libre')
        areas = self.client.get(reverse('crecimiento-areas')).data
        self.assertEqual((areas[0]['procesos'], areas[0]['avance']), (1, 50))
        procesos = self.client.get(reverse('crecimiento-procesos'), {'area': area['id']}).data
        self.assertEqual((procesos[0]['proyectos'], procesos[0]['avance']), (2, 50))

    def test_validaciones(self):
        self.crear_area()
        r = self.client.post(reverse('crecimiento-areas'), {'nombre': 'educación FINANCIERA'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.client.post(reverse('crecimiento-areas'), {'nombre': '  '}, format='json')
                         .status_code, status.HTTP_400_BAD_REQUEST)
        area = self.client.get(reverse('crecimiento-areas')).data[0]
        proceso = self.crear_proceso(area)
        r = self.client.post(reverse('crecimiento-proyectos'), {'proceso': proceso['id'], 'titulo': 'X',
                                                                'tipo': 'inventado'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        r = self.client.post(reverse('crecimiento-proyectos'), {'proceso': proceso['id'], 'titulo': 'X',
                                                                'avance': 101}, format='json')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        r = self.client.patch(reverse('crecimiento-proceso', args=[proceso['id']]),
                              {'fecha_fin': '2000-01-01'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_lo_de_otra_persona_no_se_ve_ni_se_toca(self):
        area = self.crear_area()
        proceso = self.crear_proceso(area)
        proyecto = self.crear_proyecto(proceso)
        self.client.force_authenticate(self.otro)
        self.assertEqual(self.client.get(reverse('crecimiento-areas')).data, [])
        self.assertEqual(self.client.get(reverse('crecimiento-area', args=[area['id']])).status_code,
                         status.HTTP_404_NOT_FOUND)
        r = self.client.post(reverse('crecimiento-procesos'), {'area': area['id'], 'titulo': 'Mío'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        r = self.client.post(reverse('crecimiento-notas'), {'proyecto': proyecto['id'], 'texto': 'hola'},
                             format='json')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_las_notas_se_traen_para_la_app_principal(self):
        proyecto = self.crear_proyecto(self.crear_proceso(self.crear_area()))
        for texto in ('Primera', 'Segunda'):
            r = self.client.post(reverse('crecimiento-notas'), {'proyecto': proyecto['id'], 'texto': texto},
                                 format='json')
            self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        self.assertEqual([n['texto'] for n in self.client.get(reverse('crecimiento-notas')).data],
                         ['Segunda', 'Primera'])
        self.assertEqual(len(self.client.get(reverse('crecimiento-notas'), {'limite': 1}).data), 1)
        self.assertEqual(self.client.get(reverse('crecimiento-notas'), {'proyecto': 'x'}).data, [])
        resumen = self.client.get(reverse('crecimiento-resumen')).data
        self.assertEqual(resumen['areas'][0]['procesos'][0]['fuente_titulo'], 'Sana tus finanzas, transforma tu vida')
        self.assertEqual([n['texto'] for n in resumen['notas']], ['Segunda', 'Primera'])
        self.assertEqual(self.client.post(reverse('crecimiento-notas'), {'proyecto': proyecto['id'], 'texto': ' '},
                                          format='json').status_code, status.HTTP_400_BAD_REQUEST)

    def test_un_tipo_registrado_calcula_su_avance_y_su_resumen(self):
        def valida(datos):
            if not isinstance(datos.get('dias'), list):
                from core.exceptions import ReglaNegocioError
                raise ReglaNegocioError('Faltan los días.')
            return {'dias': sorted(set(datos['dias']))}

        TIPOS['lectura'] = Tipo(nombre='Lectura', valida=valida,
                                avance=lambda p: round(len(p.datos.get('dias', [])) / 21 * 100),
                                resumen=lambda p: f'{len(p.datos.get("dias", []))} de 21 días')
        self.addCleanup(TIPOS.pop, 'lectura')
        proceso = self.crear_proceso(self.crear_area())
        proyecto = self.crear_proyecto(proceso, tipo='lectura', datos={'dias': [1, 1, 2]})
        self.assertEqual((proyecto['avance'], proyecto['resumen'], proyecto['estado']), (10, '2 de 21 días', 'en_curso'))
        # El avance no se manda a mano: sale de los datos del tipo.
        r = self.client.patch(reverse('crecimiento-proyecto', args=[proyecto['id']]),
                              {'avance': 99, 'datos': {'dias': list(range(1, 22))}}, format='json')
        self.assertEqual((r.data['avance'], r.data['resumen']), (100, '21 de 21 días'))
        malo = self.client.patch(reverse('crecimiento-proyecto', args=[proyecto['id']]), {'datos': {}}, format='json')
        self.assertEqual(malo.status_code, status.HTTP_400_BAD_REQUEST)

    def test_borrar_un_area_se_lleva_lo_que_tiene_dentro(self):
        area = self.crear_area()
        proyecto = self.crear_proyecto(self.crear_proceso(area))
        self.client.post(reverse('crecimiento-notas'), {'proyecto': proyecto['id'], 'texto': 'x'}, format='json')
        self.assertEqual(self.client.delete(reverse('crecimiento-area', args=[area['id']])).status_code,
                         status.HTTP_204_NO_CONTENT)
        self.assertEqual(self.client.get(reverse('crecimiento-notas')).data, [])


class ProgramaTest(CrecimientoTest):
    def test_un_programa_del_catalogo_trae_su_fuente_y_sus_proyectos(self):
        programas = self.client.get(reverse('crecimiento-programas')).data
        self.assertEqual(programas[0]['id'], 'sana_tus_finanzas')
        area = self.crear_area()
        r = self.client.post(reverse('crecimiento-procesos'), {'area': area['id'], 'programa': 'sana_tus_finanzas'},
                             format='json')
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        self.assertEqual((r.data['fuente_titulo'], r.data['autor'], r.data['proyectos']),
                         ('Sana tus finanzas, transforma tu vida', 'Jaime Jaramillo', 6))
        proyectos = self.client.get(reverse('crecimiento-proyectos'), {'proceso': r.data['id']}).data
        diario = next(p for p in proyectos if p['clave'] == 'diario_gastos')
        self.assertEqual((diario['tipo'], diario['calcula_avance']), ('diario_gastos', True))
        self.assertEqual(self.client.post(reverse('crecimiento-procesos'), {'area': area['id'], 'programa': 'nada'},
                                          format='json').status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.client.post(reverse('crecimiento-procesos'), {'area': area['id']},
                                          format='json').status_code, status.HTTP_400_BAD_REQUEST)
