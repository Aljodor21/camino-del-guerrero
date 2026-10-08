import os
import shutil
import tempfile
from datetime import timedelta
from io import BytesIO

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from core.exceptions import DatoInmutableError
from users.models import Proceso, Usuario

from PIL import Image

from .models import FotoProgreso, Medicion


class MedicionTest(APITestCase):
    def setUp(self):
        self.usuario = Usuario.objects.create_user(username='m@x.co', email='m@x.co', nombre='M',
                                                   password='clave-segura-123', estatura=178)
        self.client.force_authenticate(self.usuario)

    def test_registrar_con_talla_del_perfil_e_imc(self):
        r = self.client.post(reverse('mediciones'), {'peso_kg': 63.2, 'cintura_cm': 72.6}, format='json')
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        self.assertEqual(r.data['talla_cm'], 178)
        self.assertEqual(r.data['imc'], 19.95)
        self.assertEqual(r.data['fecha'], timezone.localdate().isoformat())

    def test_medicion_profesional_con_fecha_pasada(self):
        r = self.client.post(reverse('mediciones'), {
            'peso_kg': 63.2, 'talla_cm': 178, 'origen': 'profesional', 'fecha': '2026-10-05'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        self.assertEqual(r.data['fecha'], '2026-10-05')

    def test_no_acepta_fechas_futuras_ni_valores_absurdos(self):
        manana = (timezone.localdate() + timedelta(days=1)).isoformat()
        self.assertEqual(self.client.post(reverse('mediciones'), {'peso_kg': 63, 'fecha': manana}).status_code,
                         status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.client.post(reverse('mediciones'), {'peso_kg': 630}).status_code,
                         status.HTTP_400_BAD_REQUEST)

    def test_no_se_editan(self):
        m = Medicion.objects.create(usuario=self.usuario, peso_kg=63)
        url = reverse('medicion-detail', args=[m.id])
        self.assertEqual(self.client.patch(url, {'peso_kg': 60}).status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        m.peso_kg = 60
        with self.assertRaises(DatoInmutableError):
            m.save()

    def test_la_inicial_de_un_proceso_no_se_borra(self):
        inicial = Medicion.objects.create(usuario=self.usuario, peso_kg=63.2)
        Proceso.objects.create(usuario=self.usuario, objetivo='ganar_musculo', medicion_inicial=inicial)
        otra = Medicion.objects.create(usuario=self.usuario, peso_kg=63.8)
        self.assertEqual(self.client.delete(reverse('medicion-detail', args=[inicial.id])).status_code,
                         status.HTTP_409_CONFLICT)
        self.assertEqual(self.client.delete(reverse('medicion-detail', args=[otra.id])).status_code,
                         status.HTTP_204_NO_CONTENT)
        lista = self.client.get(reverse('mediciones')).data
        self.assertEqual([m['es_inicial'] for m in lista], [True])

    def test_solo_ve_sus_mediciones(self):
        otro = Usuario.objects.create_user(username='o@x.co', email='o@x.co', nombre='O', password='x')
        Medicion.objects.create(usuario=otro, peso_kg=90)
        self.assertEqual(self.client.get(reverse('mediciones')).data, [])


def _imagen(formato='JPEG', tamano=(3000, 2000), exif=True):
    imagen = Image.new('RGB', tamano, (200, 120, 90))
    salida = BytesIO()
    if exif and formato == 'JPEG':
        datos = Image.Exif()
        datos[0x0112] = 6                       # orientación: rotada 90°
        datos[0x8825] = {1: 'N', 2: (6.0, 15.0, 0.0)}  # GPS
        imagen.save(salida, formato, exif=datos)
    else:
        imagen.save(salida, formato)
    return SimpleUploadedFile('foto.jpg', salida.getvalue(), content_type='image/jpeg')


@override_settings(MEDIA_ROOT=tempfile.mkdtemp(prefix='cdg-test-media-'))
class FotoProgresoTest(APITestCase):
    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(settings.MEDIA_ROOT, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.usuario = Usuario.objects.create_user(username='f@x.co', email='f@x.co', nombre='F',
                                                   password='clave-segura-123', estatura=178)
        self.client.force_authenticate(self.usuario)
        self.medicion = Medicion.objects.create(usuario=self.usuario, peso_kg=63.4)

    def subir(self, medicion, pose='frente', imagen=None):
        return self.client.post(reverse('medicion-fotos', args=[medicion.id]),
                                {'pose': pose, 'imagen': imagen or _imagen()}, format='multipart')

    def test_se_reprocesa_sin_metadatos_y_con_orientacion_corregida(self):
        r = self.subir(self.medicion)
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        foto = FotoProgreso.objects.get(pk=r.data['id'])
        # La original era 3000x2000 rotada 90°: queda vertical y limitada a 1600 px.
        self.assertEqual((foto.ancho, foto.alto), (1067, 1600))
        with Image.open(foto.imagen.path) as guardada:
            self.assertEqual(guardada.format, 'JPEG')
            self.assertEqual(len(guardada.getexif()), 0)
        with Image.open(foto.miniatura.path) as mini:
            self.assertEqual(max(mini.size), 480)

        medicion = self.client.get(reverse('mediciones')).data[0]
        self.assertEqual(medicion['fotos'], [{'id': foto.id, 'pose': 'frente', 'ancho': 1067, 'alto': 1600}])
        self.assertTrue(medicion['admite_fotos'])

    def test_una_foto_por_pose_y_solo_imagenes(self):
        self.assertEqual(self.subir(self.medicion).status_code, status.HTTP_201_CREATED)
        self.assertEqual(self.subir(self.medicion).status_code, status.HTTP_400_BAD_REQUEST)
        texto = SimpleUploadedFile('nota.jpg', b'no soy una imagen', content_type='image/jpeg')
        self.assertEqual(self.subir(self.medicion, 'perfil', texto).status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.subir(self.medicion, 'cabeza').status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.subir(self.medicion, 'espalda', _imagen('PNG')).status_code, status.HTTP_201_CREATED)

    def test_solo_el_duenio_ve_y_sube_fotos(self):
        foto_id = self.subir(self.medicion).data['id']
        r = self.client.get(reverse('foto-progreso', args=[foto_id]), {'tamano': 'mini'})
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r['Content-Type'], 'image/jpeg')
        self.assertIn('private', r['Cache-Control'])
        self.assertEqual(Image.open(BytesIO(b''.join(r.streaming_content))).size, (320, 480))

        otro = Usuario.objects.create_user(username='o@x.co', email='o@x.co', nombre='O', password='clave-segura-123')
        self.client.force_authenticate(otro)
        self.assertEqual(self.client.get(reverse('foto-progreso', args=[foto_id])).status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(self.client.delete(reverse('foto-progreso', args=[foto_id])).status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(self.subir(self.medicion, 'perfil').status_code, status.HTTP_404_NOT_FOUND)

        self.client.logout()
        self.assertEqual(self.client.get(reverse('foto-progreso', args=[foto_id])).status_code, status.HTTP_401_UNAUTHORIZED)

    def test_fotos_iniciales_sagradas_y_con_plazo(self):
        hoy = timezone.localdate()
        Proceso.objects.create(usuario=self.usuario, objetivo='ganar_musculo', fase='volumen',
                               fecha_inicio=hoy - timedelta(days=6), medicion_inicial=self.medicion)
        r = self.subir(self.medicion)
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        r = self.client.delete(reverse('foto-progreso', args=[r.data['id']]))
        self.assertEqual(r.status_code, status.HTTP_409_CONFLICT)
        foto = FotoProgreso.objects.get()
        with self.assertRaises(DatoInmutableError):
            foto.save()

        tarde = Medicion.objects.create(usuario=self.usuario, peso_kg=63)
        Proceso.objects.filter(usuario=self.usuario).delete()
        Proceso.objects.create(usuario=self.usuario, objetivo='ganar_musculo',
                               fecha_inicio=hoy - timedelta(days=7), medicion_inicial=tarde)
        r = self.subir(tarde)
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('primeros 7 días', r.data['detail'])
        medicion = next(m for m in self.client.get(reverse('mediciones')).data if m['id'] == tarde.id)
        self.assertFalse(medicion['admite_fotos'])
        self.assertEqual(medicion['fotos_hasta'], hoy - timedelta(days=1))

    def test_borrar_foto_o_medicion_elimina_los_archivos(self):
        foto = FotoProgreso.objects.get(pk=self.subir(self.medicion).data['id'])
        rutas = [foto.imagen.path, foto.miniatura.path]
        with self.captureOnCommitCallbacks(execute=True):
            r = self.client.delete(reverse('foto-progreso', args=[foto.id]))
        self.assertEqual(r.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(any(os.path.exists(r) for r in rutas))

        foto = FotoProgreso.objects.get(pk=self.subir(self.medicion, 'perfil').data['id'])
        with self.captureOnCommitCallbacks(execute=True):
            self.client.delete(reverse('medicion-detail', args=[self.medicion.id]))
        self.assertFalse(os.path.exists(foto.imagen.path))
