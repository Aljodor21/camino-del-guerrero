from datetime import timedelta

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from users.models import Proceso, Usuario

from .models import Recordatorio

HOY = timezone.localdate


class RecordatorioTest(APITestCase):
    def setUp(self):
        self.usuario = Usuario.objects.create_user(username='a@x.co', email='a@x.co', nombre='A',
                                                   password='clave-segura-123')
        self.client.force_authenticate(self.usuario)
        self.proceso = Proceso.objects.create(usuario=self.usuario, objetivo='ganar_musculo', fase='volumen')

    def crear(self, **cambios):
        datos = {'tipo': 'control', 'titulo': 'Control con la nutricionista',
                 'fecha': (HOY() + timedelta(days=60)).isoformat(), 'hora': '07:30', 'avisar_dias_antes': 3}
        datos.update(cambios)
        return self.client.post(reverse('recordatorios'), datos, format='json')

    def test_crear_queda_ligado_al_proceso(self):
        r = self.crear()
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        self.assertEqual(r.data['proceso'], self.proceso.id)
        self.assertEqual(r.data['tipo_nombre'], 'Control con profesional')
        self.assertIsNone(r.data['completado_en'])

    def test_validaciones(self):
        ayer = (HOY() - timedelta(days=1)).isoformat()
        self.assertEqual(self.crear(fecha=ayer).status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.crear(titulo='   ').status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.crear(avisar_dias_antes=31).status_code, status.HTTP_400_BAD_REQUEST)

    def test_completar_reprogramar_y_borrar(self):
        url = reverse('recordatorio-detail', args=[self.crear().data['id']])
        r = self.client.patch(url, {'completado': True}, format='json')
        self.assertIsNotNone(r.data['completado_en'])
        r = self.client.patch(url, {'completado': False}, format='json')
        self.assertIsNone(r.data['completado_en'])

        nueva = (HOY() + timedelta(days=75)).isoformat()
        self.assertEqual(self.client.patch(url, {'fecha': nueva}, format='json').data['fecha'], nueva)
        self.assertEqual(self.client.put(url, {}, format='json').status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertEqual(self.client.delete(url).status_code, status.HTTP_204_NO_CONTENT)

    def test_uno_vencido_se_puede_completar_sin_tocar_su_fecha(self):
        r = Recordatorio.objects.create(usuario=self.usuario, titulo='Pesarme', fecha=HOY() - timedelta(days=2))
        url = reverse('recordatorio-detail', args=[r.id])
        self.assertEqual(self.client.patch(url, {'completado': True, 'fecha': r.fecha.isoformat()},
                                           format='json').status_code, status.HTTP_200_OK)

    def test_solo_los_propios(self):
        url = reverse('recordatorio-detail', args=[self.crear().data['id']])
        otro = Usuario.objects.create_user(username='b@x.co', email='b@x.co', nombre='B', password='clave-segura-123')
        self.client.force_authenticate(otro)
        self.assertEqual(self.client.get(reverse('recordatorios')).data, [])
        self.assertEqual(self.client.patch(url, {'completado': True}, format='json').status_code,
                         status.HTTP_404_NOT_FOUND)
