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

    def test_proceso_programado_guarda_la_medicion_del_onboarding(self):
        lunes = (HOY() + timedelta(days=5)).isoformat()
        r = self.crear(fecha_inicio=lunes)
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        self.assertEqual(r.data['estado'], 'programado')
        self.assertEqual(r.data['medicion_inicial']['peso_kg'], 63.2)

    def test_proceso_programado_puede_no_traer_medicion(self):
        lunes = (HOY() + timedelta(days=5)).isoformat()
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


class UnSoloProcesoTest(ProcesoBaseTest):
    def setUp(self):
        super().setUp()
        self.actual = Proceso.objects.create(usuario=self.usuario, objetivo='mantener',
                                             fecha_inicio=HOY() - timedelta(days=30))

    def test_no_se_crea_otro_si_hay_uno_en_curso(self):
        lunes = (HOY() + timedelta(days=5)).isoformat()
        r = self.crear(fecha_inicio=lunes, medicion_inicial=None)
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('en curso', str(r.data))
        self.actual.refresh_from_db()
        self.assertIsNone(self.actual.fecha_fin)

    def test_no_se_crea_otro_si_hay_uno_programado(self):
        Proceso.objects.filter(pk=self.actual.pk).delete()
        Proceso.objects.create(usuario=self.usuario, objetivo='mantener', fecha_inicio=HOY() + timedelta(days=5))
        r = self.crear(fecha_inicio=(HOY() + timedelta(days=9)).isoformat(), medicion_inicial=None)
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('programado', str(r.data))

    def test_sin_proceso_se_puede_empezar_uno(self):
        Proceso.objects.filter(pk=self.actual.pk).delete()
        self.assertEqual(self.crear().status_code, status.HTTP_201_CREATED)

    def test_borrar_un_proceso_en_curso_lo_reinicia_todo(self):
        r = self.client.delete(reverse('proceso-detail', args=[self.actual.id]))
        self.assertEqual(r.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Proceso.objects.filter(pk=self.actual.pk).exists())
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.nombre, 'Guerrero')


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
    def test_se_planea_al_crear_y_ya_no_se_mueve(self):
        fin = HOY() + timedelta(days=70)
        r = self.crear(fecha_fin_plan=fin.isoformat())
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        self.assertEqual(r.data['fecha_fin_plan'], fin.isoformat())

        url = reverse('proceso-detail', args=[r.data['id']])
        nuevo = fin + timedelta(days=14)
        r = self.client.patch(url, {'fecha_fin_plan': nuevo.isoformat()}, format='json')
        self.assertEqual(r.status_code, status.HTTP_409_CONFLICT, r.data)
        r = self.client.patch(url, {'fecha_fin_plan': None}, format='json')
        self.assertEqual(r.status_code, status.HTTP_409_CONFLICT, r.data)

    def test_sin_fecha_meta_se_puede_poner_una_vez(self):
        r = self.crear()
        url = reverse('proceso-detail', args=[r.data['id']])
        fin = HOY() + timedelta(days=40)
        r = self.client.patch(url, {'fecha_fin_plan': fin.isoformat()}, format='json')
        self.assertEqual(r.data['fecha_fin_plan'], fin.isoformat())

    def test_fin_del_plan_coherente(self):
        self.assertEqual(self.crear(fecha_fin_plan=HOY().isoformat()).status_code, status.HTTP_400_BAD_REQUEST)
        lejos = HOY() + timedelta(days=800)
        self.assertEqual(self.crear(fecha_fin_plan=lejos.isoformat()).status_code, status.HTTP_400_BAD_REQUEST)


class DatosSagradosTest(APITestCase):
    """Los datos de inicio no se editan; solo las restricciones alimentarias. Borrar el proceso
    deja únicamente los datos personales."""

    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            username='s@x.co', email='s@x.co', nombre='Sara', password='clave-segura-123',
            estatura=165, nacionalidad='Colombia', region='Paisa')
        self.client.force_authenticate(self.usuario)

    def perfil(self, **datos):
        return self.client.patch(reverse('perfil'), datos, format='json')

    def test_datos_de_inicio_no_se_cambian(self):
        for campo, valor in (('nombre', 'Otra'), ('estatura', 170), ('nacionalidad', 'Perú'), ('region', 'Costa')):
            r = self.perfil(**{campo: valor})
            self.assertEqual(r.status_code, status.HTTP_409_CONFLICT, (campo, r.data))
        self.usuario.refresh_from_db()
        self.assertEqual((self.usuario.nombre, self.usuario.estatura), ('Sara', 165))

    def test_repetir_el_mismo_valor_y_restricciones_si_se_guardan(self):
        r = self.perfil(nombre='Sara', preferencias_alimentarias='sin gluten')
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        self.assertEqual(r.data['preferencias_alimentarias'], 'sin gluten')

    def test_lo_que_falta_se_puede_completar_una_vez(self):
        Usuario.objects.filter(pk=self.usuario.pk).update(fecha_nacimiento=None)
        self.assertEqual(self.perfil(fecha_nacimiento='1995-04-02').status_code, status.HTTP_200_OK)
        self.assertEqual(self.perfil(fecha_nacimiento='1996-04-02').status_code, status.HTTP_409_CONFLICT)

    def test_fecha_meta_no_se_mueve_una_vez_puesta(self):
        proceso = Proceso.objects.create(usuario=self.usuario, objetivo='mantener',
                                         fecha_inicio=HOY(), fecha_fin_plan=HOY() + timedelta(days=60))
        url = reverse('proceso-detail', args=[proceso.id])
        r = self.client.patch(url, {'fecha_fin_plan': (HOY() + timedelta(days=90)).isoformat()}, format='json')
        self.assertEqual(r.status_code, status.HTTP_409_CONFLICT, r.data)

    def test_borrar_el_proceso_deja_solo_los_datos_personales(self):
        proceso = Proceso.objects.create(usuario=self.usuario, objetivo='mantener', fecha_inicio=HOY())
        r = self.client.delete(reverse('proceso-detail', args=[proceso.id]))
        self.assertEqual(r.status_code, status.HTTP_204_NO_CONTENT, r.data)
        self.assertFalse(self.usuario.procesos.exists())
        self.usuario.refresh_from_db()
        self.assertEqual((self.usuario.nombre, self.usuario.region), ('Sara', 'Paisa'))


class RecuperarClaveTest(APITestCase):
    NAVEGADOR = 'navegador-de-prueba-0123456789'

    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.usuario = Usuario.objects.create_user(username='r@x.co', email='r@x.co', nombre='Rosa',
                                                   password='clave-vieja-123')

    def pedir(self, email='r@x.co', navegador=None):
        return self.client.post(reverse('recuperar-clave'),
                                {'email': email, 'dispositivo': navegador or self.NAVEGADOR}, format='json')

    def token_del_ultimo_correo(self):
        from django.core import mail
        enlace = next(l for l in mail.outbox[-1].body.splitlines() if '/auth/restablecer?' in l)
        return enlace.split('token=')[1]

    def cambiar(self, token, clave='clave-nueva-456', navegador=None):
        return self.client.post(reverse('restablecer-clave'), {
            'token': token, 'dispositivo': navegador or self.NAVEGADOR, 'password': clave}, format='json')

    def test_llega_el_usuario_con_logo_y_el_enlace_sirve_una_vez(self):
        from django.core import mail
        self.assertEqual(self.pedir('R@x.co').status_code, status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 1)
        correo = mail.outbox[0]
        self.assertIn('Tu usuario es: r@x.co', correo.body)
        html = correo.html
        self.assertIn('Crear clave nueva', html)
        self.assertIn('cid:logo', html)
        self.assertTrue(any(p.get('Content-ID') == '<logo>' for p in correo.message().walk()))
        token = self.token_del_ultimo_correo()

        self.assertEqual(self.cambiar(token, '123').status_code, status.HTTP_400_BAD_REQUEST)
        ok = self.cambiar(token)
        self.assertEqual(ok.status_code, status.HTTP_200_OK, ok.data)
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password('clave-nueva-456'))
        # Ya se usó: no sirve otra vez.
        self.assertEqual(self.cambiar(token, 'otra-clave-789').status_code, status.HTTP_400_BAD_REQUEST)
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password('clave-nueva-456'))

    def test_solo_sirve_en_el_navegador_donde_se_pidio(self):
        self.pedir()
        token = self.token_del_ultimo_correo()
        r = self.cambiar(token, navegador='otro-navegador-distinto-987654')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('mismo navegador', str(r.data))
        # Intentarlo desde otro lado no gasta el enlace.
        self.assertEqual(self.cambiar(token).status_code, status.HTTP_200_OK)

    def test_el_enlace_vence(self):
        from datetime import timedelta
        from django.utils import timezone
        from .models import SolicitudRecuperacion
        self.pedir()
        token = self.token_del_ultimo_correo()
        SolicitudRecuperacion.objects.update(creada=timezone.now() - timedelta(minutes=31))
        self.assertEqual(self.cambiar(token).status_code, status.HTTP_400_BAD_REQUEST)
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password('clave-vieja-123'))

    def test_pedir_otro_enlace_anula_el_anterior(self):
        self.pedir()
        primero = self.token_del_ultimo_correo()
        self.pedir()
        segundo = self.token_del_ultimo_correo()
        self.assertEqual(self.cambiar(primero).status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.cambiar(segundo).status_code, status.HTTP_200_OK)

    def test_no_se_sabe_si_el_correo_existe(self):
        from django.core import mail
        self.assertEqual(self.pedir('nadie@x.co').status_code, status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 0)

    def test_enlace_falso_o_sin_navegador_no_cambia_nada(self):
        self.assertEqual(self.cambiar('falso').status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.pedir(navegador='corto').status_code, status.HTTP_400_BAD_REQUEST)

    def test_se_limitan_los_intentos(self):
        for _ in range(5):
            self.pedir()
        self.assertEqual(self.pedir().status_code, status.HTTP_429_TOO_MANY_REQUESTS)


class BienvenidaTest(APITestCase):
    def test_al_registrarse_llega_un_correo_de_bienvenida(self):
        from django.core import mail
        from .models import Sexo
        sexo = Sexo.objects.create(nombre='Femenino')
        r = self.client.post(reverse('registro'), {
            'nombre': 'Lucía <b>', 'email': 'lucia@x.co', 'password': 'clave-segura-123',
            'sexo': sexo.id, 'fecha_nacimiento': '1999-05-05'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        self.assertEqual(len(mail.outbox), 1)
        correo = mail.outbox[0]
        self.assertEqual(correo.to, ['lucia@x.co'])
        self.assertIn('Bienvenido', correo.subject)
        html = correo.html
        self.assertIn('Entrar a la app', html)
        self.assertNotIn('<b>', html)  # el nombre se escapa


class ModulosYControlTest(ProcesoBaseTest):
    def setUp(self):
        super().setUp()
        self.proceso = Proceso.objects.create(
            usuario=self.usuario, objetivo='ganar_musculo', incluye_alimentacion=True, incluye_entrenamiento=True,
            fecha_inicio=HOY() - timedelta(days=10), fecha_fin_plan=HOY() + timedelta(days=20))
        from .models import ConfiguracionEntrenamiento
        ConfiguracionEntrenamiento.objects.create(proceso=self.proceso)

    def quitar(self, modulo):
        return self.client.post(reverse('proceso-quitar-modulo', args=[self.proceso.id]), {'modulo': modulo}, format='json')

    def test_se_quita_el_entrenamiento_y_sigue_la_alimentacion(self):
        from .models import ConfiguracionEntrenamiento
        r = self.quitar('entrenamiento')
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        self.assertFalse(r.data['incluye_entrenamiento'])
        self.assertTrue(r.data['incluye_alimentacion'])
        self.assertFalse(ConfiguracionEntrenamiento.objects.filter(proceso=self.proceso).exists())
        # Ya no se puede quitar el último módulo.
        self.assertEqual(self.quitar('alimentacion').status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.quitar('entrenamiento').status_code, status.HTTP_400_BAD_REQUEST)

    def test_se_quita_la_alimentacion_y_se_borra_su_plan(self):
        from nutricion.models import Minuta
        Minuta.objects.create(usuario=self.usuario, proceso=self.proceso, origen='nutricionista',
                              porciones={'cereales': {'dia': 1, 'desayuno': 1}})
        r = self.quitar('alimentacion')
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        self.assertFalse(Minuta.objects.filter(proceso=self.proceso).exists())
        self.assertTrue(r.data['incluye_entrenamiento'])

    def test_patch_no_quita_modulos(self):
        url = reverse('proceso-detail', args=[self.proceso.id])
        r = self.client.patch(url, {'incluye_entrenamiento': False}, format='json')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_la_fecha_meta_solo_se_mueve_al_llegar_el_control(self):
        url = reverse('proceso-renovar', args=[self.proceso.id])
        nueva = (HOY() + timedelta(days=60)).isoformat()
        self.assertEqual(self.client.post(url, {'fecha_fin_plan': nueva}, format='json').status_code,
                         status.HTTP_409_CONFLICT)
        vieja = HOY() - timedelta(days=1)
        Proceso.objects.filter(pk=self.proceso.pk).update(fecha_fin_plan=vieja)
        self.assertTrue(self.client.get(reverse('proceso-detail', args=[self.proceso.id])).data['plan_terminado'])
        self.assertEqual(self.client.post(url, {'fecha_fin_plan': vieja.isoformat()}, format='json').status_code,
                         status.HTTP_400_BAD_REQUEST)
        r = self.client.post(url, {'fecha_fin_plan': nueva}, format='json')
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        self.assertEqual(r.data['fecha_fin_plan'], nueva)
        self.assertEqual(r.data['renovaciones'][0]['hasta'], vieja.isoformat())
        self.assertFalse(r.data['plan_terminado'])

    def test_se_puede_seguir_sin_fecha(self):
        Proceso.objects.filter(pk=self.proceso.pk).update(fecha_fin_plan=HOY() - timedelta(days=1))
        r = self.client.post(reverse('proceso-renovar', args=[self.proceso.id]), {'fecha_fin_plan': None}, format='json')
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        self.assertIsNone(r.data['fecha_fin_plan'])

    def test_al_llegar_el_control_sale_un_aviso_que_se_resuelve_al_renovar(self):
        from agenda import notificaciones
        from agenda.models import Notificacion
        Usuario.objects.filter(pk=self.usuario.pk).update(date_joined=timezone.now() - timedelta(days=40))
        self.usuario.refresh_from_db()
        Proceso.objects.filter(pk=self.proceso.pk).update(fecha_fin_plan=HOY())
        notificaciones.generar(self.usuario)
        aviso = Notificacion.objects.get(usuario=self.usuario, tipo='proceso')
        self.assertEqual(notificaciones.url_de(aviso), '/control')
        self.client.post(reverse('proceso-renovar', args=[self.proceso.id]),
                         {'fecha_fin_plan': (HOY() + timedelta(days=30)).isoformat()}, format='json')
        notificaciones.generar(self.usuario)
        aviso.refresh_from_db()
        self.assertIsNotNone(aviso.resuelta_en)
