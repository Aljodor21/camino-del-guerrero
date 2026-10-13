from datetime import datetime, time, timedelta

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from users.models import Usuario

from . import notificaciones, sueno
from .models import Habitos, Notificacion, RegistroHabito

HOY = timezone.localdate


def a_las(dia, hora, minuto=0):
    return timezone.make_aware(datetime.combine(dia, time(hora, minuto)))


class SuenoTest(APITestCase):
    def setUp(self):
        self.usuario = Usuario.objects.create_user(username='s@x.co', email='s@x.co', nombre='S',
                                                   password='clave-segura-123')
        Usuario.objects.filter(pk=self.usuario.pk).update(date_joined=timezone.now() - timedelta(days=20))
        self.usuario.refresh_from_db()
        self.client.force_authenticate(self.usuario)
        Habitos.objects.create(usuario=self.usuario, agua_ml=2000, vaso_ml=500,
                               hora_levantarse=time(6, 0), hora_dormir=time(22, 0))

    def noche(self, dia, acostado, levantado):
        """Se acostó la noche de `dia` a la hora `acostado` y se levantó a la mañana siguiente."""
        RegistroHabito.objects.create(usuario=self.usuario, tipo='dormir', fecha=dia,
                                      momento=a_las(dia, *acostado))
        manana = dia + timedelta(days=1)
        RegistroHabito.objects.create(usuario=self.usuario, tipo='levantar', fecha=manana,
                                      momento=a_las(manana, *levantado))

    def test_el_promedio_sale_de_acostarse_a_levantarse(self):
        self.noche(HOY() - timedelta(days=3), (22, 30), (6, 15))      # 7 h 45 min
        self.noche(HOY() - timedelta(days=2), (23, 0), (6, 0))        # 7 h
        r = self.client.get(reverse('sueno')).data
        self.assertEqual([n['horas'] for n in r['noches']], [7.75, 7.0])
        self.assertEqual(r['promedio_horas'], 7.38)

    def test_se_acostar_pasada_la_medianoche_tambien_cuenta(self):
        ayer = HOY() - timedelta(days=1)
        RegistroHabito.objects.create(usuario=self.usuario, tipo='dormir', fecha=ayer, momento=a_las(HOY(), 0, 30))
        RegistroHabito.objects.create(usuario=self.usuario, tipo='levantar', fecha=HOY(), momento=a_las(HOY(), 6, 30))
        self.assertEqual(sueno.anoche(self.usuario)['horas'], 6.0)

    def test_sin_una_de_las_dos_horas_o_con_horas_absurdas_no_cuenta(self):
        RegistroHabito.objects.create(usuario=self.usuario, tipo='levantar', fecha=HOY() - timedelta(days=2),
                                      momento=a_las(HOY() - timedelta(days=2), 6))      # sin acostarse
        self.noche(HOY() - timedelta(days=5), (6, 0), (6, 0))          # 24 h: se olvidó una
        r = self.client.get(reverse('sueno')).data
        self.assertEqual(r['noches'], [])
        self.assertIsNone(r['promedio_horas'])

    def test_el_aviso_de_levantarse_sale_a_la_hora_y_se_confirma_con_su_boton(self):
        notificaciones.generar(self.usuario, a_las(HOY(), 7))
        n = Notificacion.objects.get(usuario=self.usuario, tipo='levantar')
        self.assertEqual(n.titulo, 'Buenos días: ¿ya te levantaste?')
        self.assertEqual(notificaciones.accion_de(n), 'Ya me levanté')
        r = self.client.post(reverse('aviso-confirmar', args=[n.id]))
        self.assertEqual(r.status_code, status.HTTP_204_NO_CONTENT)
        self.assertTrue(RegistroHabito.objects.filter(usuario=self.usuario, tipo='levantar', notificacion=n).exists())

    def test_el_boton_me_levante_anota_una_sola_vez_al_dia(self):
        a = self.client.post(reverse('registrar-levantar'))
        b = self.client.post(reverse('registrar-levantar'))
        self.assertEqual(a.status_code, status.HTTP_201_CREATED)
        self.assertEqual(a.data['id'], b.data['id'])
        self.assertEqual(RegistroHabito.objects.filter(tipo='levantar').count(), 1)

    def test_el_boton_me_acoste_anota_la_noche_y_lo_de_hoy_lo_cuenta(self):
        r = self.client.post(reverse('registrar-dormir'))
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertEqual(self.client.post(reverse('registrar-dormir')).data['id'], r.data['id'])
        hoy = self.client.get(reverse('hoy')).data
        self.assertEqual(RegistroHabito.objects.filter(usuario=self.usuario, tipo='dormir').count(), 1)
        self.assertIn('dormir', hoy)

    def test_hoy_dice_si_ya_te_levantaste_y_cuanto_dormiste(self):
        ayer = HOY() - timedelta(days=1)
        RegistroHabito.objects.create(usuario=self.usuario, tipo='dormir', fecha=ayer, momento=a_las(ayer, 23))
        self.assertIsNone(self.client.get(reverse('hoy')).data['levantar']['levantado'])
        RegistroHabito.objects.create(usuario=self.usuario, tipo='levantar', fecha=HOY(), momento=a_las(HOY(), 6, 30))
        d = self.client.get(reverse('hoy')).data['levantar']
        self.assertIsNotNone(d['levantado'])
        self.assertEqual(d['dormiste_horas'], 7.5)

    def test_el_periodo_no_pasa_de_un_trimestre(self):
        r = self.client.get(reverse('sueno'), {'desde': (HOY() - timedelta(days=200)).isoformat()})
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_se_puede_apagar_el_aviso_de_levantarse(self):
        Habitos.objects.filter(usuario=self.usuario).update(avisos_apagados=['levantar'])
        notificaciones.generar(self.usuario, a_las(HOY(), 7))
        self.assertFalse(Notificacion.objects.filter(usuario=self.usuario, tipo='levantar').exists())
