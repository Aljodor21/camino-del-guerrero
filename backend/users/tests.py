from datetime import timedelta

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from core.exceptions import DatoInmutableError
from progress.models import Medicion

from .models import Proceso, Usuario

HOY = timezone.localdate


def crear_usuario(email='guerrero@x.co', estatura=178):
    return Usuario.objects.create_user(username=email, email=email, nombre='Guerrero',
                                       password='clave-segura-123', estatura=estatura)


class ProcesoBaseTest(APITestCase):
    def setUp(self):
        self.usuario = crear_usuario()
        self.client.force_authenticate(self.usuario)

    def payload(self, **cambios):
        datos = {
            'objetivo': 'ganar_musculo', 'fase': 'volumen', 'peso_objetivo': 68,
            'incluye_alimentacion': True, 'incluye_entrenamiento': False,
            'fecha_inicio': HOY().isoformat(),
            'medicion_inicial': {'peso_kg': 63.2, 'origen': 'profesional', 'cintura_cm': 72.6},
        }
        datos.update(cambios)
        return datos

    def crear(self, **cambios):
        return self.client.post(reverse('procesos'), self.payload(**cambios), format='json')


class CrearProcesoTest(ProcesoBaseTest):
    def test_proceso_que_inicia_hoy_guarda_medicion_inicial(self):
        r = self.crear()
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        self.assertEqual(r.data['estado'], 'en_curso')
        self.assertEqual(r.data['fase'], 'volumen')
        inicial = r.data['medicion_inicial']
        self.assertEqual(inicial['fecha'], HOY().isoformat())
        self.assertEqual(inicial['talla_cm'], 178)  # tomada del perfil
        self.assertEqual(inicial['imc'], 19.95)
        self.assertTrue(inicial['es_inicial'])

    def test_proceso_que_inicia_hoy_exige_medicion(self):
        r = self.crear(medicion_inicial=None)
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_proceso_programado_no_recibe_medicion(self):
        lunes = (HOY() + timedelta(days=5)).isoformat()
        self.assertEqual(self.crear(fecha_inicio=lunes).status_code, status.HTTP_400_BAD_REQUEST)
        r = self.crear(fecha_inicio=lunes, medicion_inicial=None)
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        self.assertEqual(r.data['estado'], 'programado')
        self.assertIsNone(r.data['medicion_inicial'])

    def test_fecha_inicio_no_puede_ser_pasada(self):
        ayer = (HOY() - timedelta(days=1)).isoformat()
        self.assertEqual(self.crear(fecha_inicio=ayer).status_code, status.HTTP_400_BAD_REQUEST)

    def test_debe_incluir_algun_modulo(self):
        r = self.crear(incluye_alimentacion=False, incluye_entrenamiento=False)
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_entrenamiento_exige_configuracion(self):
        self.assertEqual(self.crear(incluye_entrenamiento=True).status_code, status.HTTP_400_BAD_REQUEST)
        r = self.crear(incluye_entrenamiento=True, entrenamiento={
            'nivel_actividad': 'intermedio', 'dias_entrenamiento': 4,
            'duracion_sesion': 60, 'enfoque_entrenamiento': 'fuerza'})
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        self.assertEqual(r.data['entrenamiento']['dias_entrenamiento'], 4)

    def test_solo_alimentacion_no_tiene_entrenamiento(self):
        r = self.crear()
        self.assertFalse(r.data['incluye_entrenamiento'])
        self.assertIsNone(r.data['entrenamiento'])


class ProcesosEncadenadosTest(ProcesoBaseTest):
    def setUp(self):
        super().setUp()
        self.actual = Proceso.objects.create(usuario=self.usuario, objetivo='mantener',
                                             fecha_inicio=HOY() - timedelta(days=30))

    def test_nuevo_proceso_cierra_el_actual_el_dia_anterior(self):
        lunes = HOY() + timedelta(days=5)
        r = self.crear(fecha_inicio=lunes.isoformat(), medicion_inicial=None)
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        self.actual.refresh_from_db()
        self.assertEqual(self.actual.fecha_fin, lunes - timedelta(days=1))
        estado = self.client.get(reverse('procesos-estado')).data
        self.assertEqual(estado['actual']['id'], self.actual.id)
        self.assertEqual(estado['programado']['id'], r.data['id'])

    def test_no_se_crea_otro_si_ya_hay_uno_programado(self):
        lunes = (HOY() + timedelta(days=5)).isoformat()
        self.crear(fecha_inicio=lunes, medicion_inicial=None)
        r = self.crear(fecha_inicio=(HOY() + timedelta(days=9)).isoformat(), medicion_inicial=None)
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_no_puede_iniciar_el_mismo_dia_que_el_actual(self):
        Proceso.objects.filter(pk=self.actual.pk).update(fecha_inicio=HOY())
        self.assertEqual(self.crear().status_code, status.HTTP_400_BAD_REQUEST)

    def test_cancelar_programado_reabre_el_actual(self):
        lunes = (HOY() + timedelta(days=5)).isoformat()
        nuevo = self.crear(fecha_inicio=lunes, medicion_inicial=None).data
        r = self.client.delete(reverse('proceso-detail', args=[nuevo['id']]))
        self.assertEqual(r.status_code, status.HTTP_204_NO_CONTENT)
        self.actual.refresh_from_db()
        self.assertIsNone(self.actual.fecha_fin)

    def test_un_proceso_en_curso_no_se_puede_cancelar(self):
        r = self.client.delete(reverse('proceso-detail', args=[self.actual.id]))
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(Proceso.objects.filter(pk=self.actual.pk).exists())


class DatosSagradosTest(ProcesoBaseTest):
    def setUp(self):
        super().setUp()
        self.proceso = Proceso.objects.get(pk=self.crear().data['id'])

    def test_patch_ignora_los_datos_de_inicio(self):
        url = reverse('proceso-detail', args=[self.proceso.id])
        r = self.client.patch(url, {'fecha_inicio': '2020-01-01', 'objetivo': 'bajar_peso',
                                    'fase': 'definicion', 'peso_objetivo': 70}, format='json')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data['fecha_inicio'], HOY().isoformat())
        self.assertEqual(r.data['objetivo'], 'ganar_musculo')
        self.assertEqual(r.data['fase'], 'volumen')
        self.assertEqual(r.data['peso_objetivo'], 70)

    def test_el_modelo_rechaza_cambiar_datos_sagrados(self):
        self.proceso.fecha_inicio = HOY() - timedelta(days=3)
        with self.assertRaises(DatoInmutableError):
            self.proceso.save()

    def test_la_medicion_inicial_no_se_puede_reemplazar(self):
        url = reverse('proceso-medicion-inicial', args=[self.proceso.id])
        r = self.client.post(url, {'peso_kg': 60}, format='json')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_agregar_entrenamiento_despues(self):
        url = reverse('proceso-detail', args=[self.proceso.id])
        self.assertEqual(self.client.patch(url, {'incluye_entrenamiento': True}, format='json').status_code,
                         status.HTTP_400_BAD_REQUEST)
        r = self.client.patch(url, {'incluye_entrenamiento': True, 'entrenamiento': {
            'nivel_actividad': 'principiante', 'dias_entrenamiento': 3,
            'duracion_sesion': 45, 'enfoque_entrenamiento': 'boxeo'}}, format='json')
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        self.assertEqual(r.data['entrenamiento']['enfoque_entrenamiento'], 'boxeo')


class MedicionInicialPendienteTest(ProcesoBaseTest):
    def test_se_registra_una_sola_vez_cuando_el_proceso_ya_inicio(self):
        proceso = Proceso.objects.create(usuario=self.usuario, objetivo='ganar_musculo', fecha_inicio=HOY())
        url = reverse('proceso-medicion-inicial', args=[proceso.id])
        r = self.client.post(url, {'peso_kg': 63.4, 'origen': 'propia'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        self.assertEqual(r.data['medicion_inicial']['peso_kg'], 63.4)
        self.assertEqual(self.client.post(url, {'peso_kg': 64}, format='json').status_code,
                         status.HTTP_400_BAD_REQUEST)

    def test_no_se_registra_antes_del_inicio(self):
        proceso = Proceso.objects.create(usuario=self.usuario, objetivo='ganar_musculo',
                                         fecha_inicio=HOY() + timedelta(days=5))
        url = reverse('proceso-medicion-inicial', args=[proceso.id])
        self.assertEqual(self.client.post(url, {'peso_kg': 63}, format='json').status_code,
                         status.HTTP_400_BAD_REQUEST)
        self.assertFalse(Medicion.objects.exists())

    def test_no_se_accede_a_procesos_ajenos(self):
        otro = crear_usuario('otro@x.co')
        proceso = Proceso.objects.create(usuario=otro, objetivo='mantener', fecha_inicio=HOY())
        url = reverse('proceso-medicion-inicial', args=[proceso.id])
        self.assertEqual(self.client.post(url, {'peso_kg': 63}, format='json').status_code,
                         status.HTTP_404_NOT_FOUND)
        self.assertEqual(self.client.get(reverse('proceso-detail', args=[proceso.id])).status_code,
                         status.HTTP_404_NOT_FOUND)


class DuracionPlanTest(ProcesoBaseTest):
    def test_se_planea_al_crear_y_se_ajusta_despues(self):
        fin = HOY() + timedelta(days=70)
        r = self.crear(fecha_fin_plan=fin.isoformat())
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        self.assertEqual(r.data['fecha_fin_plan'], fin.isoformat())

        url = reverse('proceso-detail', args=[r.data['id']])
        nuevo = fin + timedelta(days=14)
        r = self.client.patch(url, {'fecha_fin_plan': nuevo.isoformat()}, format='json')
        self.assertEqual(r.data['fecha_fin_plan'], nuevo.isoformat())
        r = self.client.patch(url, {'fecha_fin_plan': None}, format='json')
        self.assertIsNone(r.data['fecha_fin_plan'])

    def test_fin_del_plan_coherente(self):
        self.assertEqual(self.crear(fecha_fin_plan=HOY().isoformat()).status_code, status.HTTP_400_BAD_REQUEST)
        lejos = HOY() + timedelta(days=800)
        self.assertEqual(self.crear(fecha_fin_plan=lejos.isoformat()).status_code, status.HTTP_400_BAD_REQUEST)
