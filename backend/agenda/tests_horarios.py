from datetime import datetime, time, timedelta

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from users.models import Proceso, Usuario

from . import horarios, notificaciones
from .models import Habitos, HorarioDia, Notificacion, RegistroHabito

HOY = timezone.localdate


def a_las(dia, hora, minuto=0):
    return timezone.make_aware(datetime.combine(dia, time(hora, minuto)))


class HorariosBase(APITestCase):
    def setUp(self):
        self.usuario = Usuario.objects.create_user(username='h@x.co', email='h@x.co', nombre='H',
                                                   password='clave-segura-123')
        Usuario.objects.filter(pk=self.usuario.pk).update(date_joined=timezone.now() - timedelta(days=30))
        self.usuario.refresh_from_db()
        self.client.force_authenticate(self.usuario)
        self.habitos = Habitos.objects.create(usuario=self.usuario, agua_ml=2000, vaso_ml=500,
                                              hora_levantarse=time(6, 0), hora_dormir=time(22, 0))
        self.manana = HOY() + timedelta(days=1)


class HorasDeUnDiaTest(HorariosBase):
    def test_manda_lo_de_ese_dia_luego_el_dia_de_la_semana_luego_lo_general(self):
        dia = self.manana
        self.assertEqual(horarios.horas_de(self.habitos, dia)['levantarse'], time(6, 0))
        self.habitos.horas_semana = {str(dia.isoweekday()): {'levantarse': '08:30'}}
        self.habitos.save()
        horas = horarios.horas_de(self.habitos, dia)
        self.assertEqual((horas['levantarse'], horas['dormir'], horas['personalizado']), (time(8, 30), time(22, 0), False))
        HorarioDia.objects.create(usuario=self.usuario, fecha=dia, hora_levantarse=time(5, 0))
        horas = horarios.horas_de(self.habitos, dia)
        self.assertEqual((horas['levantarse'], horas['personalizado']), (time(5, 0), True))
        # Otro día de la semana sigue con la hora general.
        otro = dia + timedelta(days=1)
        self.assertEqual(horarios.horas_de(self.habitos, otro)['levantarse'], time(6, 0))

    def test_los_avisos_del_dia_siguen_la_hora_de_ese_dia(self):
        HorarioDia.objects.create(usuario=self.usuario, fecha=self.manana, hora_levantarse=time(5, 0),
                                  hora_dormir=time(21, 0))
        avisos = {a['clave']: a for a in notificaciones.programados(self.usuario, self.manana)}
        self.assertEqual(avisos[f'levantar:{self.manana}']['programada_para'], a_las(self.manana, 5))
        self.assertEqual(avisos[f'dormir:{self.manana}']['programada_para'], a_las(self.manana, 20, 30))
        # El agua se reparte entre una hora después de levantarse (6:00) y una antes de dormir (20:00).
        primero = avisos[f'agua:{self.manana}:1']['programada_para']
        ultimo = avisos[f'agua:{self.manana}:4']['programada_para']
        self.assertEqual((primero, ultimo), (a_las(self.manana, 6), a_las(self.manana, 20)))

    def test_cambiar_las_horas_de_un_solo_dia_por_la_api(self):
        url = reverse('horario-dia', args=[self.manana.isoformat()])
        r = self.client.put(url, {'hora_levantarse': '05:00'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        self.assertEqual((str(r.data['levantarse']), r.data['personalizado']), ('05:00:00', True))
        self.assertEqual(HorarioDia.objects.get().hora_dormir, None)
        hoy = self.client.get(reverse('hoy')).data['horario']
        self.assertEqual((hoy['manana']['levantarse'], hoy['manana']['personalizado']), ('05:00', True))
        self.assertFalse(hoy['hoy']['personalizado'])
        # Dejar las dos vacías vuelve a lo de siempre.
        self.client.put(url, {'hora_levantarse': None, 'hora_dormir': None}, format='json')
        self.assertFalse(HorarioDia.objects.exists())

    def test_no_se_cambian_fechas_muy_lejanas_ni_horas_iguales(self):
        lejos = (HOY() + timedelta(days=200)).isoformat()
        self.assertEqual(self.client.put(reverse('horario-dia', args=[lejos]), {'hora_levantarse': '05:00'},
                                         format='json').status_code, status.HTTP_400_BAD_REQUEST)
        url = reverse('horario-dia', args=[self.manana.isoformat()])
        self.assertEqual(self.client.put(url, {'hora_levantarse': '05:00', 'hora_dormir': '05:00'},
                                         format='json').status_code, status.HTTP_400_BAD_REQUEST)

    def test_las_horas_por_dia_de_la_semana_se_validan_y_se_guardan(self):
        r = self.client.patch(reverse('habitos'), {'horas_semana': {'6': {'levantarse': '8:30', 'dormir': '23:30'}}},
                              format='json')
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        self.assertEqual(r.data['horas_semana'], {'6': {'levantarse': '08:30', 'dormir': '23:30'}})
        for malo in ({'9': {'levantarse': '07:00'}}, {'1': {'levantarse': 'tarde'}},
                     {'1': {'levantarse': '07:00', 'dormir': '07:00'}}):
            self.assertEqual(self.client.patch(reverse('habitos'), {'horas_semana': malo}, format='json').status_code,
                             status.HTTP_400_BAD_REQUEST)


class HorasDeComidaTest(HorariosBase):
    def test_el_aviso_de_como_te_fue_llega_despues_de_la_hora_de_comer(self):
        from nutricion.tests import datos_minuta
        from nutricion.models import Minuta, PreferenciasComida
        Proceso.objects.create(usuario=self.usuario, objetivo='ganar_musculo', fase='volumen',
                               fecha_inicio=HOY() - timedelta(days=2), fecha_fin_plan=HOY() + timedelta(days=60))
        PreferenciasComida.objects.create(usuario=self.usuario)
        datos = datos_minuta()
        self.client.post(reverse('minutas'), {'origen': 'nutricionista', 'porciones': datos['porciones'],
                                              'kcal': datos['kcal'], 'menu_ejemplo': datos['menu_ejemplo']},
                         format='json')
        Minuta.objects.update(fecha_creacion=timezone.now() - timedelta(days=2))
        comidas = lambda: {a['datos']['tiempo']: a['programada_para']
                           for a in notificaciones.programados(self.usuario, HOY()) if a['tipo'] == 'comida'}
        # Sin hora propia: la de referencia (desayuno 7:00) más 45 minutos.
        self.assertEqual(comidas()['desayuno'], a_las(HOY(), 7, 45))
        # Con su hora: a las 6:00 come, a las 6:45 pregunta.
        r = self.client.patch(reverse('habitos'), {'horas_comida': {'desayuno': '06:00'}}, format='json')
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        self.assertEqual(comidas()['desayuno'], a_las(HOY(), 6, 45))
        info = {t['tiempo']: t for t in r.data['tiempos_comida']}
        self.assertEqual((info['desayuno']['hora'], info['desayuno']['personalizada'], info['desayuno']['referencia']),
                         ('06:00', True, '07:00'))
        self.assertFalse(info['almuerzo']['personalizada'])

    def test_una_comida_que_no_existe_se_rechaza(self):
        r = self.client.patch(reverse('habitos'), {'horas_comida': {'brunch': '10:00'}}, format='json')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)


class ComparacionConLoPrevistoTest(HorariosBase):
    def test_dice_cuantos_minutos_antes_o_despues_de_lo_previsto(self):
        ayer = HOY() - timedelta(days=1)
        # Previsto: acostarse 22:00, levantarse 6:00. Se acostó 21:30 y se levantó 6:15.
        RegistroHabito.objects.create(usuario=self.usuario, tipo='dormir', fecha=ayer, momento=a_las(ayer, 21, 30))
        RegistroHabito.objects.create(usuario=self.usuario, tipo='levantar', fecha=HOY(), momento=a_las(HOY(), 6, 15))
        d = self.client.get(reverse('hoy')).data['levantar']
        self.assertEqual((d['acostarse_min'], d['levantarse_min']), (-30, 15))
        n = self.client.get(reverse('sueno'), {'desde': HOY().isoformat()}).data
        self.assertEqual((n['promedio_acostarse_min'], n['promedio_levantarse_min']), (-30, 15))

    def test_usa_la_hora_de_ese_dia_y_no_la_general(self):
        ayer = HOY() - timedelta(days=1)
        HorarioDia.objects.create(usuario=self.usuario, fecha=HOY(), hora_levantarse=time(5, 0))
        RegistroHabito.objects.create(usuario=self.usuario, tipo='dormir', fecha=ayer, momento=a_las(ayer, 22, 0))
        RegistroHabito.objects.create(usuario=self.usuario, tipo='levantar', fecha=HOY(), momento=a_las(HOY(), 5, 10))
        self.assertEqual(self.client.get(reverse('hoy')).data['levantar']['levantarse_min'], 10)

    def test_sin_hora_prevista_no_compara(self):
        Habitos.objects.filter(usuario=self.usuario).update(hora_levantarse=None, hora_dormir=None)
        ayer = HOY() - timedelta(days=1)
        RegistroHabito.objects.create(usuario=self.usuario, tipo='dormir', fecha=ayer, momento=a_las(ayer, 22, 0))
        RegistroHabito.objects.create(usuario=self.usuario, tipo='levantar', fecha=HOY(), momento=a_las(HOY(), 6, 0))
        d = self.client.get(reverse('hoy')).data['levantar']
        self.assertEqual(d['dormiste_horas'], 8.0)
        self.assertIsNone(d['levantarse_min'])
