from datetime import timedelta
from unittest import mock

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from agenda.models import Recordatorio
from users.models import Proceso, Usuario

from . import suplementos
from .models import Suplemento


class ModulosDelProcesoTest(APITestCase):
    """Alimentación y entrenamiento son independientes: uno no exige el otro."""

    def setUp(self):
        self.usuario = Usuario.objects.create_user(username='n@x.co', email='n@x.co', nombre='N',
                                                   password='clave-segura-123')
        self.client.force_authenticate(self.usuario)

    @mock.patch('nutricion.views.AIService')
    def test_rutina_rechazada_si_el_proceso_es_solo_alimentacion(self, ai):
        Proceso.objects.create(usuario=self.usuario, objetivo='ganar_musculo')
        r = self.client.post(reverse('generar-rutina'))
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        ai.assert_not_called()


class SuplementoTest(APITestCase):
    """La proteína se asume a 3 meses hasta que el usuario lo confirme, y la agenda sugiere qué hacer."""

    def setUp(self):
        self.usuario = Usuario.objects.create_user(username='s@x.co', email='s@x.co', nombre='S',
                                                   password='clave-segura-123')
        self.client.force_authenticate(self.usuario)
        self.hoy = timezone.localdate()
        self.proceso = Proceso.objects.create(usuario=self.usuario, objetivo='ganar_musculo', fase='volumen',
                                              fecha_fin_plan=self.hoy + timedelta(days=60))

    def crear(self, **datos):
        r = self.client.post(reverse('suplementos'), datos, format='json')
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        return r.data

    def sugeridos(self):
        return {r.motivo: r for r in Recordatorio.objects.filter(usuario=self.usuario, completado_en__isnull=True)}

    def accion(self, sup, accion, **datos):
        return self.client.post(reverse('suplemento-accion', args=[sup['id'], accion]), datos, format='json')

    def test_la_informacion_nutricional_es_un_enlace_o_un_archivo_privado(self):
        import tempfile
        from io import BytesIO
        from django.core.files.uploadedfile import SimpleUploadedFile
        from django.test import override_settings
        from PIL import Image
        sup = self.crear(tipo='proteina', duracion_dias=90, porciones_envase=30, porciones_dia=1)
        url = reverse('suplemento-detail', args=[sup['id']])
        for malo in ('javascript:alert(1)', 'ftp://x.co/a', 'no es un enlace'):
            r = self.client.patch(url, {'info_url': malo}, format='json')
            self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST, malo)
        r = self.client.patch(url, {'info_url': 'https://marca.co/whey'}, format='json')
        self.assertEqual(r.data['info_url'], 'https://marca.co/whey')

        info = reverse('suplemento-info', args=[sup['id']])
        with override_settings(MEDIA_ROOT=tempfile.mkdtemp(prefix='cdg-test-media-')):
            self.assertEqual(self.client.get(info).status_code, status.HTTP_404_NOT_FOUND)
            r = self.client.post(info, {'archivo': SimpleUploadedFile('a.txt', b'hola', 'text/plain')}, format='multipart')
            self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
            imagen = BytesIO()
            Image.new('RGB', (3000, 2000), 'white').save(imagen, 'PNG')
            r = self.client.post(info, {'archivo': SimpleUploadedFile('e.png', imagen.getvalue(), 'image/png')},
                                 format='multipart')
            self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
            self.assertEqual(r.data['info_archivo_tipo'], 'imagen')
            foto = self.client.get(info)
            self.assertLessEqual(Image.open(BytesIO(b''.join(foto.streaming_content))).width, 1600)
            r = self.client.post(info, {'archivo': SimpleUploadedFile('e.pdf', b'%PDF-1.4 x', 'application/pdf')},
                                 format='multipart')
            self.assertEqual(r.data['info_archivo_tipo'], 'pdf')
            self.assertEqual(self.client.get(info)['Content-Type'], 'application/pdf')
            otro = Usuario.objects.create_user(username='o@x.co', email='o@x.co', nombre='O',
                                               password='clave-segura-123')
            self.client.force_authenticate(otro)
            self.assertEqual(self.client.get(info).status_code, status.HTTP_404_NOT_FOUND)
            self.client.force_authenticate(self.usuario)
            r = self.client.delete(info)
            self.assertIsNone(r.data['info_archivo_tipo'])
            self.assertEqual(self.client.get(info).status_code, status.HTTP_404_NOT_FOUND)

    def test_la_foto_del_producto_es_privada_y_se_reduce(self):
        import tempfile
        from io import BytesIO
        from django.core.files.uploadedfile import SimpleUploadedFile
        from django.test import override_settings
        from PIL import Image
        sup = self.crear(tipo='proteina', duracion_dias=90, porciones_envase=30, porciones_dia=1)
        self.assertFalse(sup['tiene_foto'])
        foto = reverse('suplemento-foto', args=[sup['id']])
        with override_settings(MEDIA_ROOT=tempfile.mkdtemp(prefix='cdg-test-media-')):
            self.assertEqual(self.client.get(foto).status_code, status.HTTP_404_NOT_FOUND)
            # Un PDF no es una foto.
            r = self.client.post(foto, {'archivo': SimpleUploadedFile('a.pdf', b'%PDF-1.4 x', 'application/pdf')},
                                 format='multipart')
            self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
            imagen = BytesIO()
            Image.new('RGB', (3000, 2000), 'white').save(imagen, 'PNG')
            r = self.client.post(foto, {'archivo': SimpleUploadedFile('p.png', imagen.getvalue(), 'image/png')},
                                 format='multipart')
            self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
            self.assertTrue(r.data['tiene_foto'])
            descarga = self.client.get(foto)
            self.assertEqual(descarga['Content-Type'], 'image/jpeg')
            self.assertLessEqual(Image.open(BytesIO(b''.join(descarga.streaming_content))).width, 1600)
            otro = Usuario.objects.create_user(username='o2@x.co', email='o2@x.co', nombre='O',
                                               password='clave-segura-123')
            self.client.force_authenticate(otro)
            self.assertEqual(self.client.get(foto).status_code, status.HTTP_404_NOT_FOUND)
            self.client.force_authenticate(self.usuario)
            self.assertFalse(self.client.delete(foto).data['tiene_foto'])
            self.assertEqual(self.client.get(foto).status_code, status.HTTP_404_NOT_FOUND)

    def test_proteina_asumida_pide_confirmar_y_revisar_al_final(self):
        sup = self.crear(tipo='proteina', duracion_dias=90, porciones_envase=30, porciones_dia=1)
        self.assertEqual(sup['fin_estimado'], (self.hoy + timedelta(days=89)).isoformat())
        self.assertEqual(sup['se_acaba'], (self.hoy + timedelta(days=29)).isoformat())

        s = self.sugeridos()
        self.assertEqual(set(s), {'confirmar', 'reponer', 'revisar'})
        self.assertEqual(s['confirmar'].titulo, 'Confirma si la proteína va 3 meses')
        self.assertEqual(s['revisar'].fecha, self.hoy + timedelta(days=89))
        self.assertEqual(s['revisar'].proceso, self.proceso)

        url = reverse('suplemento-detail', args=[sup['id']])
        self.client.patch(url, {'duracion_confirmada': True}, format='json')
        s = self.sugeridos()
        self.assertNotIn('confirmar', s)
        self.assertTrue(Recordatorio.objects.filter(motivo='confirmar', completado_en__isnull=False).exists())

        # Siguió con la misma un mes más: el aviso de revisión se corre.
        r = self.accion(sup, 'continuar', dias=30)
        self.assertEqual(r.data['duracion_dias'], 120)
        self.assertEqual(self.sugeridos()['revisar'].fecha, self.hoy + timedelta(days=119))

    def test_hipercalorico_va_hasta_el_fin_del_plan(self):
        sup = self.crear(tipo='hipercalorico', porciones_envase=20, porciones_dia=2, duracion_confirmada=True)
        self.assertEqual(sup['fin_estimado'], self.proceso.fecha_fin_plan.isoformat())
        self.assertEqual(sup['dias_envase'], 10)
        self.assertEqual(set(self.sugeridos()), {'reponer'})

        # Si el envase alcanza hasta el final del plan, no hay nada que reponer.
        Proceso.objects.filter(pk=self.proceso.pk).update(fecha_fin_plan=self.hoy + timedelta(days=5))
        self.proceso.refresh_from_db()
        suplementos.sincronizar_proceso(self.proceso)
        self.assertEqual(self.sugeridos(), {})

    def test_las_porciones_salen_de_la_etiqueta(self):
        # 3 kg, porción de 150 g en 3 scoops, 2 al día: 20 porciones, 10 días.
        sup = self.crear(tipo='hipercalorico', peso_envase_g=3000, porcion_g=150, scoops_porcion=3,
                         porciones_dia=2, duracion_confirmada=True)
        self.assertEqual(sup['porciones_por_envase'], 20)
        self.assertEqual(sup['dias_envase'], 10)
        self.assertEqual(sup['se_acaba'], (self.hoy + timedelta(days=9)).isoformat())
        self.assertEqual(Recordatorio.objects.get(motivo='reponer').titulo.count('proteína hipercalórica'), 1)

        r = self.client.post(reverse('suplementos'), {'tipo': 'proteina', 'porcion_g': 0}, format='json')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_abrir_envase_resuelve_y_reprograma(self):
        sup = self.crear(tipo='proteina', duracion_dias=90, duracion_confirmada=True, porciones_envase=30)
        Suplemento.objects.filter(pk=sup['id']).update(envase_desde=self.hoy - timedelta(days=28))
        self.accion(sup, 'abrir-envase')
        self.assertEqual(self.sugeridos()['reponer'].fecha, self.hoy + timedelta(days=29))
        self.assertEqual(Recordatorio.objects.filter(motivo='reponer', completado_en__isnull=False).count(), 1)

    def test_cambiar_de_proteina(self):
        sup = self.crear(tipo='proteina', nombre='Whey A', duracion_dias=90, duracion_confirmada=True)
        r = self.accion(sup, 'reemplazar', nombre='Whey B', duracion_dias=60, duracion_confirmada=True)
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        self.assertEqual(r.data['tipo'], 'proteina')

        lista = self.client.get(reverse('suplementos')).data
        self.assertEqual([(x['nombre'], x['fecha_fin']) for x in lista],
                         [('Whey B', None), ('Whey A', self.hoy.isoformat())])
        self.assertEqual([x.titulo for x in self.sugeridos().values()], ['Terminan los 2 meses de Whey B: ¿qué sigue?'])
        self.assertEqual(self.accion(sup, 'terminar').status_code, status.HTTP_400_BAD_REQUEST)

    def test_los_sugeridos_se_resuelven_desde_el_suplemento(self):
        self.crear(tipo='proteina', duracion_dias=90)
        url = reverse('recordatorio-detail', args=[self.sugeridos()['revisar'].id])
        for cambio in ({'titulo': 'Otro'}, {'completado': True}):
            self.assertEqual(self.client.patch(url, cambio, format='json').status_code,
                             status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.client.delete(url).status_code, status.HTTP_400_BAD_REQUEST)

    def test_solo_los_propios(self):
        sup = self.crear(tipo='creatina')
        otro = Usuario.objects.create_user(username='o@x.co', email='o@x.co', nombre='O', password='clave-segura-123')
        self.client.force_authenticate(otro)
        self.assertEqual(self.accion(sup, 'terminar').status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(self.client.post(reverse('suplementos'), {'tipo': 'proteina'}, format='json').status_code,
                         status.HTTP_400_BAD_REQUEST)


TABLA_MINUTA = """
 Grupos de alimentos              Porciones   Desayuno   Onces   Almuerzo   Algo   Cena   Merienda
                                    al día
 Sustitutos
 Huevos, quesos, cuajada,              3.0        3.0      0.0       0.0     0.0    0.0      0.0
 Lácteos                               2.0        0.0      1.0       0.0     1.0    0.0      0.0
 Leche, yogurt, kumis
 Carnes                                4.0        0.0      0.0       2.0     0.0    2.0      0.0
 Cereales, raíces, tubérculos y
 plátanos                             10.0        2.0      1.0       4.0     1.0    2.0      0.0
 Verduras                              2.0        0.0      0.0       1.0     0.0    1.0      0.0
 Frutas                                2.0        0.0      1.0       0.0     1.0    0.0      0.0
 Aceites vegetales y aguacate          7.0        2.0      0.0       3.0     0.0    2.0      0.0
 Aguacate, aceites de oliva, ajonjolí
 Semillas y oleaginosas
 Ajonjolí, calabaza, girasol,          2.0        0.0      0.0       0.0     0.0    0.0      0.0
 Agua                                 10.0        0.0      0.0       0.0     0.0    0.0      0.0
 2. Menú sugerido
 2700 kcal
 1.5 grs de prot
 Desayuno:   3 huevos con arepa
 Media mañana:   yogur griego con fruta
 y avena
 Recomendaciones y restricciones
 Tomar agua durante el día.
 3. Medidas antropométricas
"""


def datos_minuta():
    from .lector_minuta import interpretar
    return interpretar(TABLA_MINUTA)


class LectorMinutaTest(APITestCase):
    """La minuta se toma tal cual del PDF; si no cuadra, no se carga."""

    def test_lee_porciones_por_comida_calorias_y_menu_de_ejemplo(self):
        datos = datos_minuta()
        self.assertEqual(datos['porciones']['cereales'],
                         {'dia': 10, 'desayuno': 2, 'onces': 1, 'almuerzo': 4, 'algo': 1, 'cena': 2, 'merienda': 0})
        self.assertEqual(datos['porciones']['grasas']['almuerzo'], 3)
        self.assertEqual(datos['kcal'], 2700)
        self.assertEqual(str(datos['proteina_g_kg']), '1.5')
        self.assertEqual(datos['menu_ejemplo'], {'desayuno': '3 huevos con arepa',
                                                 'onces': 'yogur griego con fruta y avena'})
        self.assertEqual(datos['recomendaciones'], 'Tomar agua durante el día.')

    def test_rechaza_una_minuta_que_no_suma(self):
        from .lector_minuta import MinutaIlegibleError, interpretar
        with self.assertRaises(MinutaIlegibleError):
            interpretar(TABLA_MINUTA.replace(' Carnes                                4.0', ' Carnes                                5.0'))


@mock.patch('nutricion.menus.AIService')
class MinutaYMenuTest(APITestCase):
    def setUp(self):
        from .models import PreferenciasComida
        self.usuario = Usuario.objects.create_user(username='m@x.co', email='m@x.co', nombre='M',
                                                   password='clave-segura-123')
        self.client.force_authenticate(self.usuario)
        self.hoy = timezone.localdate()
        Usuario.objects.filter(pk=self.usuario.pk).update(date_joined=timezone.now() - timedelta(days=2))
        self.usuario.refresh_from_db()
        self.proceso = Proceso.objects.create(usuario=self.usuario, objetivo='ganar_musculo', fase='volumen',
                                              fecha_inicio=self.hoy - timedelta(days=self.hoy.weekday()),
                                              fecha_fin_plan=self.hoy + timedelta(days=60))
        PreferenciasComida.objects.create(usuario=self.usuario)

    def subir_y_confirmar(self, **extra):
        datos = datos_minuta()
        r = self.client.post(reverse('minutas'), {
            'origen': 'nutricionista', 'porciones': datos['porciones'], 'kcal': datos['kcal'],
            'menu_ejemplo': datos['menu_ejemplo'], **extra}, format='json')
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        return r.data

    def armar_menu(self):
        r = self.client.post(reverse('menu'), {}, format='json')
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        return r.data

    def assertCumpleMinuta(self, comida):
        suma = {}
        for c in comida['componentes']:
            if c['grupo'] != 'libres':
                suma[c['grupo']] = suma.get(c['grupo'], 0) + c['porciones']
        self.assertEqual(suma, {r['grupo']: r['porciones'] for r in comida['requerido']}, comida)

    def test_un_plan_nuevo_trae_su_periodo_y_la_fecha_meta_anterior_queda_guardada(self, ai):
        self.subir_y_confirmar()
        meta = self.proceso.fecha_fin_plan
        # Sin la llave, la fecha meta no se toca.
        self.subir_y_confirmar()
        self.proceso.refresh_from_db()
        self.assertEqual(self.proceso.fecha_fin_plan, meta)
        # Con otro periodo, sí: y la anterior queda en el historial.
        nueva = self.hoy + timedelta(days=90)
        self.subir_y_confirmar(fecha_fin_plan=nueva.isoformat())
        self.proceso.refresh_from_db()
        self.assertEqual(self.proceso.fecha_fin_plan, nueva)
        self.assertEqual(self.proceso.renovaciones[0]['hasta'], meta.isoformat())
        # Sin definir.
        self.subir_y_confirmar(fecha_fin_plan=None)
        self.proceso.refresh_from_db()
        self.assertIsNone(self.proceso.fecha_fin_plan)

    def test_proyeccion_une_peso_gasto_plan_y_cumplimiento(self, ai):
        from progress.models import Medicion
        Usuario.objects.filter(pk=self.usuario.pk).update(estatura=178, fecha_nacimiento='2001-12-25')
        self.usuario.refresh_from_db()
        self.assertEqual(self.client.get(reverse('proyeccion')).status_code, status.HTTP_400_BAD_REQUEST)
        self.subir_y_confirmar()
        Medicion.objects.create(usuario=self.usuario, peso_kg=70)
        r = self.client.get(reverse('proyeccion'))
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        d = r.data
        self.assertEqual((d['kcal_plan'], d['dias']), (2700, 60))
        self.assertEqual(d['balance_kcal'], 2700 - d['gasto_kcal'])
        todo = d['escenarios'][0]
        self.assertEqual(todo['porcentaje'], 100)
        self.assertAlmostEqual(todo['cambio_kg'], d['balance_kcal'] * 60 / 7700, places=1)
        self.assertAlmostEqual(todo['peso_final_kg'], 70 + todo['cambio_kg'], places=1)
        self.assertTrue(any('Peso actual: 70' in f for f in d['factores']))
        self.assertIn('estimación', d['aviso'])

    def test_la_ilustracion_pide_permiso_foto_y_cambio_notable_y_es_privada(self, ai):
        import tempfile
        from io import BytesIO
        from django.core.files.uploadedfile import SimpleUploadedFile
        from django.test import override_settings
        from PIL import Image
        from progress import fotos
        from progress.models import Medicion
        Usuario.objects.filter(pk=self.usuario.pk).update(estatura=178, fecha_nacimiento='2001-12-25')
        self.usuario.refresh_from_db()
        url = reverse('ilustraciones')
        png = BytesIO()
        Image.new('RGB', (800, 1200), 'gray').save(png, 'PNG')
        generada = BytesIO()
        Image.new('RGB', (1024, 1536), 'white').save(generada, 'PNG')
        pedir = mock.patch('nutricion.ilustracion._pedir_a_openai', return_value=generada.getvalue())

        with override_settings(MEDIA_ROOT=tempfile.mkdtemp(prefix='cdg-test-media-'), OPENAI_API_KEY='', ILUSTRACIONES_POR_DIA=2):
            # Sin llave la función no aparece ni se puede usar.
            self.assertFalse(self.client.get(url).data['disponible'])
            self.assertEqual(self.client.post(url, {'consentimiento': True}, format='json').status_code,
                             status.HTTP_400_BAD_REQUEST)
        with override_settings(MEDIA_ROOT=tempfile.mkdtemp(prefix='cdg-test-media-'), OPENAI_API_KEY='x', ILUSTRACIONES_POR_DIA=2):
            self.assertTrue(self.client.get(url).data['disponible'])
            self.subir_y_confirmar(kcal=3300)
            Medicion.objects.create(usuario=self.usuario, peso_kg=70)
            with pedir as llamada:
                # Sin permiso, no se envía nada.
                r = self.client.post(url, {}, format='json')
                self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn('OpenAI', str(r.data))
                # Sin foto de frente.
                r = self.client.post(url, {'consentimiento': True}, format='json')
                self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn('foto de frente', str(r.data))
                llamada.assert_not_called()

                medicion = Medicion.objects.get(usuario=self.usuario)
                fotos.agregar_foto(medicion, 'frente', SimpleUploadedFile('f.png', png.getvalue(), 'image/png'))
                r = self.client.post(url, {'consentimiento': True}, format='json')
                self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
                # Con 3.300 kcal la cuenta da más de 7 kg, pero la imagen se queda en un cambio moderado.
                self.assertEqual(r.data['cambio_kg'], 3.0)
                self.assertTrue(r.data['limitado'])
                self.assertEqual(r.data['peso_final'], 73.0)
                self.assertEqual(r.data['peso_base'], 70)
                prompt = llamada.call_args.args[1]
                self.assertIn('Conserva idénticos el rostro', prompt)
                self.assertIn('+3.0 kg', prompt)
                self.assertIn('cambio pequeño y realista', prompt)
                nueva = r.data['id']
                imagen = self.client.get(reverse('ilustracion-imagen', args=[nueva]))
                self.assertEqual(imagen['Content-Type'], 'image/jpeg')
                otro = Usuario.objects.create_user(username='o3@x.co', email='o3@x.co', nombre='O',
                                                   password='clave-segura-123')
                self.client.force_authenticate(otro)
                self.assertEqual(self.client.get(reverse('ilustracion-imagen', args=[nueva])).status_code,
                                 status.HTTP_404_NOT_FOUND)
                self.client.force_authenticate(self.usuario)

                # Límite diario.
                self.assertEqual(self.client.post(url, {'consentimiento': True}, format='json').status_code,
                                 status.HTTP_201_CREATED)
                r = self.client.post(url, {'consentimiento': True}, format='json')
                self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn('Vuelve mañana', str(r.data))
                self.assertEqual(self.client.get(url).data['restantes_hoy'], 0)
                self.assertEqual(self.client.delete(reverse('ilustracion-imagen', args=[nueva])).status_code,
                                 status.HTTP_204_NO_CONTENT)
                self.assertEqual(self.client.get(url).data['restantes_hoy'], 1)

    def test_con_un_cambio_minimo_no_se_genera_imagen(self, ai):
        import tempfile
        from django.test import override_settings
        from progress.models import Medicion
        Usuario.objects.filter(pk=self.usuario.pk).update(estatura=178, fecha_nacimiento='2001-12-25')
        self.usuario.refresh_from_db()
        Medicion.objects.create(usuario=self.usuario, peso_kg=70)
        with override_settings(MEDIA_ROOT=tempfile.mkdtemp(prefix='cdg-test-media-'), OPENAI_API_KEY='x'):
            self.subir_y_confirmar(kcal=2270)  # casi el gasto estimado: cambio mínimo
            with mock.patch('nutricion.ilustracion._pedir_a_openai') as llamada:
                r = self.client.post(reverse('ilustraciones'), {'consentimiento': True}, format='json')
            self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertIn('casi no se notaría', str(r.data))
            llamada.assert_not_called()

    def test_la_minuta_guardada_queda_fija(self, ai):
        from core.exceptions import DatoInmutableError
        from .models import Minuta
        minuta = self.subir_y_confirmar()
        self.assertEqual(minuta['origen'], 'nutricionista')
        self.assertEqual(minuta['tiempos'], ['desayuno', 'onces', 'almuerzo', 'algo', 'cena'])
        self.assertEqual(minuta['durante_el_dia'], {'semillas': 2.0, 'agua': 10.0})
        self.assertEqual(self.client.delete(reverse('minuta-detail', args=[minuta['id']])).status_code,
                         status.HTTP_405_METHOD_NOT_ALLOWED)
        guardada = Minuta.objects.get(pk=minuta['id'])
        guardada.kcal = 1000
        with self.assertRaises(DatoInmutableError):
            guardada.save()
        with self.assertRaises(DatoInmutableError):
            guardada.delete()
        # Una nueva pasa a mandar y la anterior queda en el historial.
        nueva = self.subir_y_confirmar()
        lista = self.client.get(reverse('minutas')).data
        self.assertEqual([m['id'] for m in lista], [nueva['id'], minuta['id']])

    def test_la_plantilla_valida_las_porciones(self, ai):
        for porciones in ({'pan': {'desayuno': 1}}, {'cereales': {'brunch': 1}}, {'cereales': {'cena': 0.3}},
                          {'agua': {'dia': 8}}):
            r = self.client.post(reverse('minutas'), {'origen': 'nutricionista', 'porciones': porciones},
                                 format='json')
            self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST, porciones)

    def test_lo_del_dia_que_no_va_en_comidas_queda_libre(self, ai):
        r = self.client.post(reverse('minutas'), {'origen': 'nutricionista', 'porciones': {
            'cereales': {'almuerzo': 2, 'dia': 2}, 'frutas': {'onces': 1, 'dia': 3}, 'agua': {'dia': 8}}},
            format='json')
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        self.assertEqual(r.data['durante_el_dia'], {'frutas': 2.0, 'agua': 8.0})

    def test_el_pdf_solo_llena_la_plantilla(self, ai):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from .models import Minuta
        with mock.patch('nutricion.views.lector_minuta.leer', return_value=datos_minuta()):
            r = self.client.post(reverse('minuta-leer-pdf'),
                                 {'archivo': SimpleUploadedFile('plan.pdf', b'%PDF-1.4 x')}, format='multipart')
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        self.assertEqual(r.data['porciones']['carnes']['almuerzo'], 2)
        self.assertFalse(Minuta.objects.exists())

    def test_la_ia_calcula_una_minuta_con_las_calorias_de_la_meta(self, ai):
        from datetime import date
        from progress.models import Medicion
        from .calculadora import kcal_de
        from .minutas import normalizar_porciones
        self.usuario.estatura, self.usuario.fecha_nacimiento = 178, date(2000, 1, 1)
        self.usuario.save()
        Medicion.objects.create(usuario=self.usuario, peso_kg=63.2)
        with mock.patch('nutricion.calculadora.AIService') as ai_calc:
            ai_calc.return_value.calcular_minuta.side_effect = Exception('sin IA')
            r = self.client.post(reverse('minuta-calcular'))
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        self.assertEqual(r.data['proteina_g_kg'], 1.8)
        self.assertLess(abs(kcal_de(normalizar_porciones(r.data['porciones'])) - r.data['kcal']), 100)
        self.assertIn(str(r.data['kcal']), r.data['explicacion'])
        r = self.client.post(reverse('minutas'), {'origen': 'ia', 'porciones': r.data['porciones'],
                                                  'kcal': r.data['kcal']}, format='json')
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)

    def test_sin_ia_el_menu_sale_solo_de_los_intercambios_y_cumple_la_minuta(self, ai):
        from .models import AlimentoIntercambio
        ai.return_value.proponer_menu.side_effect = Exception('sin IA')
        self.subir_y_confirmar()
        menu = self.armar_menu()
        self.assertEqual(len(menu['comidas']), 7 * 5)
        self.assertEqual(menu['durante_el_dia'][0]['grupo'], 'semillas')
        for comida in menu['comidas']:
            self.assertCumpleMinuta(comida)
            for c in comida['componentes']:
                self.assertEqual(AlimentoIntercambio.objects.get(pk=c['alimento_id']).grupo, c['grupo'])
        grasas = AlimentoIntercambio.objects.filter(
            id__in=[c['alimento_id'] for m in menu['comidas'] for c in m['componentes'] if c['grupo'] == 'grasas'])
        self.assertFalse(grasas.exclude(subgrupo__in=['Poliinsaturadas', 'Monoinsaturadas']).exists())

    def test_la_ia_solo_completa_lo_que_la_minuta_no_nombra(self, ai):
        from .models import AlimentoIntercambio, ComidaMenu
        self.subir_y_confirmar()
        lunes = self.hoy - timedelta(days=self.hoy.weekday())
        # La minuta nombra yogur griego y avena en las onces, pero de la fruta solo dice "fruta".
        fruta = AlimentoIntercambio.objects.filter(grupo='frutas').first()
        arepa = AlimentoIntercambio.objects.get(grupo='cereales', nombre__startswith='Arepa delgada')
        ai.return_value.proponer_menu.return_value = {'comidas': [
            {'fecha': lunes.isoformat(), 'tiempo': 'onces', 'componentes': [[fruta.id, 1]]},
            # Una arepa no es una fruta: se descarta y la fruta sale de la lista de intercambios.
            {'fecha': (lunes + timedelta(days=1)).isoformat(), 'tiempo': 'onces', 'componentes': [[arepa.id, 1]]},
        ]}
        menu = self.armar_menu()
        pedidos = ai.return_value.proponer_menu.call_args.kwargs['pedidos']
        self.assertIn('onces: frutas 1', pedidos)
        # Huevos, arepa, yogur y avena ya los nombra la minuta: la IA no los toca.
        self.assertNotIn('sustitutos', pedidos)
        self.assertNotIn('cereales', pedidos)
        self.assertNotIn('lacteos', pedidos)
        onces = [c for c in menu['comidas'] if c['tiempo'] == 'onces']
        self.assertIn(fruta.id, [c['alimento_id'] for c in onces[0]['componentes']])
        for comida in menu['comidas']:
            self.assertCumpleMinuta(comida)
        # Lo nombrado sale solo de lo que dice la minuta: yogur griego, avena, huevo y arepa.
        nombres = {c['alimento'].lower() for m in menu['comidas'] if m['tiempo'] in ('desayuno', 'onces')
                   for c in m['componentes'] if c['grupo'] in ('lacteos', 'cereales', 'sustitutos')}
        self.assertTrue(all(any(n in x for n in ('yogur', 'yogurt', 'avena', 'huevo', 'arepa')) for x in nombres), nombres)
        self.assertTrue(menu['generado_con_ia'])

    def test_sin_nada_abierto_no_se_llama_a_la_ia(self, ai):
        self.subir_y_confirmar()
        self.armar_menu()
        # La minuta de prueba deja la fruta abierta; si no hubiera nada abierto, la IA no se usa.
        self.assertTrue(ai.return_value.proponer_menu.called)

    def test_cada_toma_cubre_lo_que_reemplaza_en_su_comida(self, ai):
        ai.return_value.proponer_menu.side_effect = Exception('sin IA')
        self.subir_y_confirmar()
        self.armar_menu()
        etiqueta = {'tipo': 'hipercalorico', 'peso_envase_g': 2268, 'porcion_g': 150, 'scoops_porcion': 6,
                    'duracion_confirmada': True}

        def toma(tiempo, scoops, reemplaza):
            return {'tiempo': tiempo, 'scoops': scoops, 'reemplaza': reemplaza}

        # Las onces de la minuta no tienen carnes y solo tienen 1 lácteo; las tomas suman la porción.
        for tomas in ([toma('onces', 6, {'carnes': 1})], [toma('onces', 6, {'lacteos': 2})],
                      [toma('onces', 3, {}), toma('algo', 2, {})],
                      [toma('onces', 3, {}), toma('onces', 3, {})]):
            r = self.client.post(reverse('suplementos'), {**etiqueta, 'tomas': tomas}, format='json')
            self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST, tomas)

        # La porción de 6 scoops se reparte 3 y 3: media mañana y tarde, cada una con lo suyo.
        r = self.client.post(reverse('suplementos'), {
            **etiqueta, 'tomas': [toma('algo', 3, {'lacteos': 1, 'cereales': 1}), toma('onces', 3, {'lacteos': 1})],
        }, format='json')
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        self.assertEqual([t['tiempo'] for t in r.data['tomas']], ['onces', 'algo'])
        self.assertEqual(r.data['porciones_dia'], 1)
        self.assertEqual(r.data['porciones_por_envase'], 15)
        self.assertEqual(r.data['dias_envase'], 15)

        menu = self.client.get(reverse('menu')).data
        for comida in menu['comidas']:
            self.assertCumpleMinuta(comida)
            if comida['tiempo'] in ('onces', 'algo') and comida['fecha'] >= self.hoy.isoformat():
                self.assertNotIn('lacteos', [c['grupo'] for c in comida['componentes']])
                self.assertEqual(comida['suplementos'][0]['scoops'], 3)
        algo = next(c for c in menu['comidas'] if c['tiempo'] == 'algo' and c['fecha'] >= self.hoy.isoformat())
        self.assertNotIn('cereales', [c['grupo'] for c in algo['componentes']])

    def test_el_huevo_se_muestra_como_lo_dice_la_minuta(self, ai):
        from .models import AlimentoIntercambio
        from .cantidades import nombre_visible
        huevo = AlimentoIntercambio.objects.get(nombre='Huevo de gallina crudo')
        self.assertEqual(nombre_visible(huevo), 'Huevo')

    def test_las_grasas_son_solo_aceites_y_aguacate(self, ai):
        from .menus import Catalogo
        nombres = {a.nombre for a in Catalogo().por_grupo['grasas']}
        self.assertIn('Aceite de canola', nombres)
        self.assertIn('Aguacate Hass', nombres)
        for fuera in ('Margarinas suaves sin sal', 'Mayonesa comercial', 'Salsa ranch', 'Mantequilla de maní'):
            self.assertNotIn(fuera, nombres)

    def test_cambiar_un_alimento_solo_por_otro_del_mismo_grupo(self, ai):
        from .models import AlimentoIntercambio
        ai.return_value.proponer_menu.side_effect = Exception('sin IA')
        self.subir_y_confirmar()
        comida = next(c for c in self.armar_menu()['comidas'] if c['tiempo'] == 'almuerzo')
        carne = next(c for c in comida['componentes'] if c['grupo'] == 'carnes')
        opciones = self.client.get(reverse('comida-opciones', args=[comida['id']]), {'componente': carne['id']}).data
        self.assertTrue(opciones)
        self.assertFalse(AlimentoIntercambio.objects.filter(id__in=[o['id'] for o in opciones])
                         .exclude(grupo='carnes').exists())
        url = reverse('comida-accion', args=[comida['id'], 'cambiar'])
        arroz = AlimentoIntercambio.objects.get(grupo='cereales', nombre='Arroz blanco, cocido')
        r = self.client.post(url, {'componente': carne['id'], 'alimento': arroz.id}, format='json')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        r = self.client.post(url, {'componente': carne['id'], 'alimento': opciones[0]['id']}, format='json')
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        cambiada = next(c for c in r.data['comidas'] if c['id'] == comida['id'])
        self.assertTrue(cambiada['cambiada'])
        self.assertIn(opciones[0]['id'], [c['alimento_id'] for c in cambiada['componentes']])

    def test_no_puedo_con_esta_comida_propone_otra_dentro_de_la_minuta(self, ai):
        ai.return_value.proponer_menu.side_effect = Exception('sin IA')
        ai.return_value.proponer_comida.return_value = {'nombre': 'Inventada', 'componentes': [[999999, 2]]}
        self.subir_y_confirmar()
        comida = next(c for c in self.armar_menu()['comidas'] if c['tiempo'] == 'almuerzo')
        r = self.client.post(reverse('comida-accion', args=[comida['id'], 'sugerir']), {'motivo': 'tiempo'},
                             format='json')
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        nueva = next(c for c in r.data['comidas'] if c['id'] == comida['id'])
        self.assertEqual(nueva['nombre'], '')
        self.assertCumpleMinuta(nueva)

    def test_el_menu_no_incluye_dias_antes_del_inicio_del_proceso(self, ai):
        from .models import ComidaMenu
        ai.return_value.proponer_menu.side_effect = Exception('sin IA')
        self.subir_y_confirmar()
        semana = self.hoy - timedelta(days=self.hoy.weekday())
        domingo = semana + timedelta(days=6)
        Proceso.objects.filter(pk=self.proceso.pk).update(fecha_inicio=domingo)
        r = self.client.post(reverse('menu'), {'semana': semana.isoformat()}, format='json')
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        self.assertEqual(set(ComidaMenu.objects.values_list('fecha', flat=True)), {domingo})

        Proceso.objects.filter(pk=self.proceso.pk).update(fecha_inicio=semana + timedelta(days=14))
        r = self.client.post(reverse('menu'), {'semana': semana.isoformat()}, format='json')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_las_comidas_por_fuera_no_entran_al_mercado(self, ai):
        from .models import ComidaMenu
        ai.return_value.proponer_menu.side_effect = Exception('sin IA')
        self.subir_y_confirmar()
        r = self.client.patch(reverse('preferencias-comida'), {'por_fuera': {'almuerzo': 'entre_semana'}},
                              format='json')
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        menu = self.armar_menu()
        almuerzos = [c for c in menu['comidas'] if c['tiempo'] == 'almuerzo']
        self.assertEqual([c['por_fuera'] for c in almuerzos], [True] * 5 + [False] * 2)
        self.assertTrue(almuerzos[0]['requerido'][0]['ejemplo'])
        with mock.patch('nutricion.views.AIService') as ai_vista:
            ai_vista.return_value.generar_lista_mercado.side_effect = Exception('sin IA')
            r = self.client.post(reverse('lista-mercado'), {'num_personas': 1}, format='json')
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        from .cantidades import NOMBRE_EN_MINUTA
        en_casa = set(ComidaMenu.objects.filter(por_fuera=False).values_list('componentes__alimento__nombre', flat=True))
        en_casa = {NOMBRE_EN_MINUTA.get(n, n) for n in en_casa}
        self.assertTrue({i['nombre'] for i in r.data['items']} <= en_casa)

    def test_mercado_de_15_dias_y_de_un_mes_solo_multiplica_lo_que_dura(self, ai):
        from datetime import date
        from . import mercado
        ai.return_value.proponer_menu.side_effect = Exception('sin IA')
        self.subir_y_confirmar()
        self.armar_menu()

        def lista(periodo):
            r = self.client.post(reverse('lista-mercado'), {'num_personas': 1, 'periodo': periodo}, format='json')
            self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
            return r.data, {i['nombre']: i for i in r.data['items']}

        semana, items_semana = lista('semana')
        quincena, items_quincena = lista('quincena')
        mes, items_mes = lista('mes')
        self.assertEqual((semana['periodo'], quincena['periodo'], mes['periodo']), ('semana', 'quincena', 'mes'))
        self.assertTrue(all(i['frecuencia'] == 'semanal' for i in items_semana.values()))
        self.assertEqual({i['frecuencia'] for i in items_quincena.values()}, {'semanal', 'quincenal'})
        self.assertTrue(any(i['frecuencia'] == 'mensual' for i in items_mes.values()))
        # Lo perecedero es igual en los tres: se compra cada semana.
        perecederos = {n for n, i in items_semana.items() if i['frecuencia'] == 'semanal' and n in items_mes
                       and items_mes[n]['frecuencia'] == 'semanal'}
        self.assertTrue(perecederos)
        self.assertTrue(all(items_semana[n]['cantidad'] == items_mes[n]['cantidad'] for n in perecederos))
        self.assertTrue(any('Colanta' in c for c in mes['consejos_compra']))
        self.assertTrue(any('Ara' in c and 'D1' in c for c in mes['consejos_compra']))
        r = self.client.post(reverse('lista-mercado'), {'periodo': 'año'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        # Promoción de Colanta: el 15 y el 30 (en febrero, el último día).
        self.assertEqual(mercado.proxima_promocion_colanta(date(2026, 10, 11)), date(2026, 10, 15))
        self.assertEqual(mercado.proxima_promocion_colanta(date(2026, 10, 16)), date(2026, 10, 30))
        self.assertEqual(mercado.proxima_promocion_colanta(date(2026, 10, 31)), date(2026, 11, 15))
        self.assertEqual(mercado.proxima_promocion_colanta(date(2027, 2, 16)), date(2027, 2, 28))
        self.assertEqual(mercado.proxima_promocion_colanta(date(2026, 12, 31)), date(2027, 1, 15))

    def test_la_leche_de_la_proteina_entra_al_mercado(self, ai):
        ai.return_value.proponer_menu.side_effect = Exception('sin IA')
        self.subir_y_confirmar()
        menu = self.armar_menu()
        base = {'tipo': 'proteina', 'peso_envase_g': 2268, 'porcion_g': 30, 'scoops_porcion': 1,
                'duracion_confirmada': True, 'tomas': [{'tiempo': 'onces', 'scoops': 1, 'reemplaza': {}}]}

        def mercado():
            with mock.patch('nutricion.views.AIService') as ai_vista:
                ai_vista.return_value.generar_lista_mercado.side_effect = Exception('sin IA')
                r = self.client.post(reverse('lista-mercado'), {'num_personas': 1}, format='json')
            self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
            return [i for i in r.data['items'] if 'proteína' in i['nombre']]

        # Con agua no se compra nada; con leche, los ml de la porción por los días de la semana.
        r = self.client.post(reverse('suplementos'), {**base, 'liquido': 'agua', 'liquido_ml': 300}, format='json')
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        self.assertEqual(mercado(), [])
        r = self.client.patch(reverse('suplemento-detail', args=[r.data['id']]),
                              {'liquido': 'leche', 'liquido_ml': 300}, format='json')
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        dias = sum(1 for i in range(7) if Suplemento.objects.get().activo_en(
            timezone.datetime.fromisoformat(menu['semana']).date() + timedelta(days=i)))
        litros = f'{300 * dias / 1000:.1f}'.replace('.', ',').removesuffix(',0')
        self.assertEqual([i['cantidad'] for i in mercado()], [f'{litros} L' if 300 * dias >= 1000 else f'{300 * dias} ml'])
        # Sin líquido, los ml se descartan.
        r = self.client.patch(reverse('suplemento-detail', args=[r.data['id']]), {'liquido': ''}, format='json')
        self.assertIsNone(r.data['liquido_ml'])

    def test_cumplimiento_de_la_minuta_con_lo_que_se_cuenta(self, ai):
        from .models import RegistroComida
        ai.return_value.proponer_menu.side_effect = Exception('sin IA')
        self.subir_y_confirmar()
        pedido = self.client.get(reverse('pedido-comida'), {'tiempo': 'almuerzo'}).data
        grupos = {g['grupo']: g['porciones'] for g in pedido['grupos']}
        self.assertFalse(pedido['contada'])
        url = reverse('registros-comida')

        # Solo grupos que la comida lleva, y de 0 a 1 de lo pedido.
        r = self.client.post(url, {'tiempo': 'almuerzo', 'avances': {'frutas': 1, 'inventado': 1}}, format='json')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        r = self.client.post(url, {'tiempo': 'almuerzo', 'avances': {g: 0.9 for g in grupos}}, format='json')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(RegistroComida.objects.count(), 0)

        # Comió todo menos la mitad de los cereales: cumplió casi todo y falta una parte de cereales.
        avances = {g: 1 for g in grupos} | {'cereales': 0.5}
        r = self.client.post(url, {'tiempo': 'almuerzo', 'avances': avances, 'nota': 'Pollo con arroz'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        self.assertEqual(self.client.post(url, {'tiempo': 'almuerzo', 'avances': avances}, format='json').status_code,
                         status.HTTP_400_BAD_REQUEST)
        total = sum(grupos.values())
        faltan = grupos['cereales'] / 2
        c = self.client.get(reverse('cumplimiento'), {'periodo': 'hoy'}).data
        self.assertEqual(c['porcentaje'], round((total - faltan) / total * 100))
        self.assertEqual([f['grupo'] for f in c['faltantes']], ['cereales'])
        self.assertEqual(c['faltantes'][0]['porciones'], faltan)
        self.assertIn('de cereales', c['mensaje'])
        # Lo que el usuario contó no se edita.
        from core.exceptions import DatoInmutableError
        registro = RegistroComida.objects.get()
        registro.nota = 'otra'
        with self.assertRaises(DatoInmutableError):
            registro.save()

    def test_la_foto_de_la_comida_es_privada_y_se_reduce(self, ai):
        import tempfile
        from io import BytesIO
        from django.core.files.uploadedfile import SimpleUploadedFile
        from django.test import override_settings
        from PIL import Image
        ai.return_value.proponer_menu.side_effect = Exception('sin IA')
        self.subir_y_confirmar()
        grupos = {g['grupo']: 1 for g in self.client.get(reverse('pedido-comida'), {'tiempo': 'cena'}).data['grupos']}
        imagen = BytesIO()
        Image.new('RGB', (3000, 2000), 'red').save(imagen, 'PNG')
        with override_settings(MEDIA_ROOT=tempfile.mkdtemp(prefix='cdg-test-media-')):
            r = self.client.post(reverse('registros-comida'), {
                'tiempo': 'cena', 'avances': __import__('json').dumps(grupos),
                'foto': SimpleUploadedFile('c.png', imagen.getvalue(), 'image/png')}, format='multipart')
            self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
            self.assertTrue(r.data['tiene_foto'])
            foto = self.client.get(reverse('registro-comida-foto', args=[r.data['id']]))
            self.assertEqual(foto.status_code, status.HTTP_200_OK)
            self.assertLessEqual(Image.open(BytesIO(b''.join(foto.streaming_content))).width, 1600)
            otro = Usuario.objects.create_user(username='o@x.co', email='o@x.co', nombre='O', password='clave-segura-123')
            self.client.force_authenticate(otro)
            self.assertEqual(self.client.get(reverse('registro-comida-foto', args=[r.data['id']])).status_code,
                             status.HTTP_404_NOT_FOUND)

    def test_el_aviso_de_la_comida_sale_al_contarla(self, ai):
        from datetime import datetime, time
        from agenda import notificaciones
        from agenda.models import Notificacion
        ai.return_value.proponer_menu.side_effect = Exception('sin IA')
        self.subir_y_confirmar()
        ahora = timezone.make_aware(datetime.combine(self.hoy, time(14, 0)))
        notificaciones.generar(self.usuario, ahora)
        avisos = {n.datos['tiempo']: n for n in Notificacion.objects.filter(tipo='comida')}
        self.assertTrue({'desayuno', 'onces', 'almuerzo'} <= set(avisos))
        self.assertNotIn('cena', avisos)
        self.assertEqual(avisos['almuerzo'].titulo, '¿Cómo te fue con el almuerzo?')
        # No se confirma a ciegas: hay que contar qué se comió.
        r = self.client.post(reverse('aviso-confirmar', args=[avisos['almuerzo'].id]))
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        grupos = {g['grupo']: 1 for g in self.client.get(reverse('pedido-comida'), {'tiempo': 'almuerzo'}).data['grupos']}
        r = self.client.post(reverse('registros-comida'), {'tiempo': 'almuerzo', 'avances': grupos}, format='json')
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        avisos['almuerzo'].refresh_from_db()
        self.assertEqual(avisos['almuerzo'].resolucion, 'automatica')
        avisos['desayuno'].refresh_from_db()
        self.assertIsNone(avisos['desayuno'].resuelta_en)
