from datetime import datetime, time, timedelta

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from nutricion.models import Minuta, PreferenciasComida, RegistroComida
from nutricion.tests import datos_minuta
from users.models import Proceso, Usuario

from . import horarios, notificaciones, sugerencias_de_horas
from .models import Habitos, Notificacion, Recordatorio, RegistroHabito

HOY = timezone.localdate


def a_las(dia, hora, minuto=0):
    return timezone.make_aware(datetime.combine(dia, time(hora, minuto)))


class Base(APITestCase):
    def setUp(self):
        self.usuario = Usuario.objects.create_user(username='c@x.co', email='c@x.co', nombre='C',
                                                   password='clave-segura-123')
        Usuario.objects.filter(pk=self.usuario.pk).update(date_joined=timezone.now() - timedelta(days=30))
        self.usuario.refresh_from_db()
        self.client.force_authenticate(self.usuario)
        self.habitos = Habitos.objects.create(usuario=self.usuario, agua_ml=2000, vaso_ml=500,
                                              hora_levantarse=time(6, 0), hora_dormir=time(22, 0))

    def con_plan(self):
        Proceso.objects.create(usuario=self.usuario, objetivo='ganar_musculo', fase='volumen',
                               fecha_inicio=HOY() - timedelta(days=2), fecha_fin_plan=HOY() + timedelta(days=60))
        PreferenciasComida.objects.create(usuario=self.usuario)
        d = datos_minuta()
        self.client.post(reverse('minutas'), {'origen': 'nutricionista', 'porciones': d['porciones'], 'kcal': d['kcal'],
                                              'menu_ejemplo': d['menu_ejemplo']}, format='json')
        Minuta.objects.update(fecha_creacion=timezone.now() - timedelta(days=2))

    def comidas(self, ahora=None):
        return {a['datos']['tiempo']: a['programada_para']
                for a in notificaciones.programados(self.usuario, HOY(), ahora) if a['tipo'] == 'comida'}


class ComidasSegunLaHoraDeLevantarseTest(Base):
    def test_el_desayuno_es_una_hora_despues_de_levantarse_y_el_resto_se_reparte(self):
        self.con_plan()
        tiempos = ['desayuno', 'onces', 'almuerzo', 'algo', 'cena']
        horas = horarios.horas_de_comidas(self.habitos, HOY(), tiempos)
        self.assertEqual(horas['desayuno'], time(7, 0))          # 6:00 + 1 h
        self.assertEqual(horas['cena'], time(20, 0))             # 22:00 − 2 h
        self.assertEqual(list(horas.values()), sorted(horas.values()))
        # El aviso de contar llega 45 minutos después de cada una.
        self.assertEqual(self.comidas()['desayuno'], a_las(HOY(), 7, 45))

    def test_si_se_levanta_mas_tarde_el_desayuno_tambien(self):
        self.habitos.hora_levantarse = time(8, 30)
        self.habitos.save()
        horas = horarios.horas_de_comidas(self.habitos, HOY(), ['desayuno', 'almuerzo', 'cena'])
        self.assertEqual(horas['desayuno'], time(9, 30))

    def test_solo_cuenta_las_comidas_del_plan_no_inventa_merienda(self):
        self.con_plan()
        self.assertNotIn('merienda', self.comidas())
        info = self.client.get(reverse('habitos')).data['tiempos_comida']
        self.assertNotIn('merienda', [t['tiempo'] for t in info])
        # Con tres comidas se reparten solo entre esas tres.
        horas = horarios.horas_de_comidas(self.habitos, HOY(), ['desayuno', 'almuerzo', 'cena'])
        self.assertEqual(list(horas), ['desayuno', 'almuerzo', 'cena'])
        self.assertEqual(horas['almuerzo'], time(13, 30))

    def test_la_hora_que_la_persona_pone_manda_sobre_el_reparto(self):
        self.con_plan()
        r = self.client.patch(reverse('habitos'), {'horas_comida': {'almuerzo': '12:00'}}, format='json')
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        info = {t['tiempo']: t for t in r.data['tiempos_comida']}
        self.assertEqual((info['almuerzo']['hora'], info['almuerzo']['personalizada']), ('12:00', True))
        self.assertEqual(info['desayuno']['hora'], '07:00')
        self.assertNotEqual(info['almuerzo']['referencia'], '12:00')
        self.assertEqual(self.comidas()['almuerzo'], a_las(HOY(), 12, 45))

    def test_si_aun_no_se_levanto_las_comidas_de_hoy_esperan(self):
        self.con_plan()
        # Hora prevista 6:00; a las 7:30 no ha dicho que se levantó: no se pregunta por el desayuno.
        retenidas = [a['tipo'] for a in notificaciones.programados(self.usuario, HOY(), a_las(HOY(), 7, 30))]
        self.assertNotIn('comida', retenidas)
        # Si se levantó a las 8:30, el desayuno es a las 9:30 y el aviso a las 10:15.
        RegistroHabito.objects.create(usuario=self.usuario, tipo='levantar', fecha=HOY(), momento=a_las(HOY(), 8, 30))
        self.assertEqual(self.comidas(a_las(HOY(), 11))['desayuno'], a_las(HOY(), 10, 15))
        # Y el resto del día se reparte desde esa hora real.
        self.assertGreater(self.comidas(a_las(HOY(), 11))['almuerzo'], a_las(HOY(), 13, 45))

    def test_si_nunca_avisa_que_se_levanto_se_sigue_con_la_hora_prevista(self):
        self.con_plan()
        tarde = a_las(HOY(), 9, 30)      # pasaron más de 3 horas de las 6:00
        self.assertEqual(self.comidas(tarde)['desayuno'], a_las(HOY(), 7, 45))

    def test_sin_aviso_de_levantarse_no_hay_nada_que_esperar(self):
        self.con_plan()
        Habitos.objects.filter(usuario=self.usuario).update(avisos_apagados=['levantar'])
        self.assertIn('desayuno', self.comidas(a_las(HOY(), 7, 30)))

    def test_el_agua_puede_repartirse_en_el_rango_que_la_persona_usa(self):
        r = self.client.patch(reverse('habitos'), {'horas_agua': {'inicio': '09:00', 'fin': '19:00'}}, format='json')
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        agua = [a['programada_para'] for a in notificaciones.programados(self.usuario, HOY()) if a['tipo'] == 'agua']
        self.assertEqual((agua[0], agua[-1]), (a_las(HOY(), 9), a_las(HOY(), 19)))
        malo = self.client.patch(reverse('habitos'), {'horas_agua': {'inicio': '19:00', 'fin': '09:00'}}, format='json')
        self.assertEqual(malo.status_code, status.HTTP_400_BAD_REQUEST)


class PendientesConVariosAvisosTest(Base):
    def pendiente(self, hora=time(16, 0), **extra):
        return Recordatorio.objects.create(usuario=self.usuario, tipo='control', titulo='Control con la nutri',
                                           fecha=HOY(), hora=hora, avisar_dias_antes=1, **extra)

    def test_avisa_una_hora_media_hora_un_cuarto_y_en_el_momento(self):
        r = self.pendiente()
        avisos = {a['clave']: a for a in notificaciones.programados(self.usuario, HOY()) if a['tipo'] == 'recordatorio'}
        base = f'recordatorio:{r.id}:{r.fecha}'
        self.assertEqual({k.rsplit(':', 1)[1]: v['programada_para'] for k, v in avisos.items()},
                         {'60': a_las(HOY(), 15), '30': a_las(HOY(), 15, 30), '15': a_las(HOY(), 15, 45),
                          '0': a_las(HOY(), 16)})
        self.assertEqual(avisos[f'{base}:60']['titulo'], 'En 1 hora: Control con la nutri')
        self.assertEqual(avisos[f'{base}:0']['titulo'], 'Ahora: Control con la nutri')
        self.assertTrue(all(a['datos']['grupo'] == base for a in avisos.values()))

    def test_cada_aviso_reemplaza_al_anterior_en_la_bandeja(self):
        self.pendiente()
        notificaciones.generar(self.usuario, a_las(HOY(), 15, 5))
        self.assertEqual(Notificacion.objects.filter(tipo='recordatorio', resuelta_en__isnull=True).count(), 1)
        notificaciones.generar(self.usuario, a_las(HOY(), 15, 35))
        pendientes = Notificacion.objects.filter(tipo='recordatorio', resuelta_en__isnull=True)
        self.assertEqual([n.datos['minutos'] for n in pendientes], [30])
        notificaciones.generar(self.usuario, a_las(HOY(), 16, 1))
        pendientes = Notificacion.objects.filter(tipo='recordatorio', resuelta_en__isnull=True)
        self.assertEqual([n.datos['minutos'] for n in pendientes], [0])

    def test_el_mismo_grupo_viaja_al_celular_para_que_se_reemplacen(self):
        from . import fcm, push
        r = self.pendiente()
        notificaciones.generar(self.usuario, a_las(HOY(), 15, 35))
        n = Notificacion.objects.filter(tipo='recordatorio', resuelta_en__isnull=True).get()
        self.assertEqual(push.contenido(n)['grupo'], f'recordatorio:{r.id}:{r.fecha}')
        self.assertEqual(n.datos['grupo'], f'recordatorio:{r.id}:{r.fecha}')

    def test_sin_hora_avisa_a_las_ocho_el_dia_y_un_dia_antes(self):
        r = self.pendiente(hora=None)
        hoy = [a for a in notificaciones.programados(self.usuario, HOY()) if a['tipo'] == 'recordatorio']
        self.assertEqual([(a['cuerpo'], a['programada_para']) for a in hoy], [('Es hoy.', a_las(HOY(), 8))])
        antes = notificaciones.programados(self.usuario, HOY() - timedelta(days=1))
        self.assertEqual([a['cuerpo'] for a in antes if a['tipo'] == 'recordatorio'], [f'Es el {HOY():%d/%m}.'])

    def test_un_pendiente_completado_ya_no_avisa(self):
        r = self.pendiente()
        Recordatorio.objects.filter(pk=r.pk).update(completado_en=timezone.now())
        self.assertFalse([a for a in notificaciones.programados(self.usuario, HOY()) if a['tipo'] == 'recordatorio'])


class SugerenciasDeHorasTest(Base):
    def contar(self, tiempo, dias, hora, minuto=0):
        for atras in range(1, dias + 1):
            d = HOY() - timedelta(days=atras)
            RegistroComida.objects.create(usuario=self.usuario, fecha=d, tiempo=tiempo, grupos={},
                                          momento=a_las(d, hora, minuto))

    def test_si_cuenta_el_desayuno_siempre_tarde_propone_su_hora_real(self):
        self.con_plan()
        self.contar('desayuno', 6, 9, 30)          # el aviso llega a las 7:45; él cuenta a las 9:30
        s = {x['id']: x for x in sugerencias_de_horas.de_horas(self.usuario)}
        self.assertEqual(s['comida-desayuno']['sugerida'], '08:45')      # 9:30 − 45 min
        self.assertEqual(s['comida-desayuno']['cambios'], {'horas_comida': {'desayuno': '08:45'}})
        # Al aplicarla ya no hay diferencia.
        r = self.client.patch(reverse('habitos'), s['comida-desayuno']['cambios'], format='json')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertNotIn('comida-desayuno', {x['id'] for x in sugerencias_de_horas.de_horas(self.usuario)})

    def test_con_pocos_datos_o_diferencia_pequena_no_propone_nada(self):
        self.con_plan()
        self.contar('desayuno', 3, 9, 30)          # solo 3 días
        self.contar('almuerzo', 6, 14, 20)         # casi la hora del aviso (14:15)
        self.assertEqual(sugerencias_de_horas.de_horas(self.usuario), [])

    def test_el_agua_propone_el_rango_en_que_realmente_la_toma(self):
        for atras in range(1, 7):
            d = HOY() - timedelta(days=atras)
            for h in (10, 14, 19):
                RegistroHabito.objects.create(usuario=self.usuario, tipo='agua', fecha=d, ml=500, momento=a_las(d, h))
        s = {x['id']: x for x in sugerencias_de_horas.de_horas(self.usuario)}
        self.assertEqual(s['agua']['cambios'], {'horas_agua': {'inicio': '10:00', 'fin': '19:00'}})

    def test_levantarse_y_acostarse_reales_proponen_cambiar_la_hora_general(self):
        for atras in range(1, 7):
            d = HOY() - timedelta(days=atras)
            RegistroHabito.objects.create(usuario=self.usuario, tipo='levantar', fecha=d, momento=a_las(d, 7, 30))
            RegistroHabito.objects.create(usuario=self.usuario, tipo='dormir', fecha=d, momento=a_las(d, 23, 30))
        s = {x['id']: x for x in sugerencias_de_horas.de_horas(self.usuario)}
        self.assertEqual(s['levantarse']['cambios'], {'hora_levantarse': '07:30'})
        self.assertEqual(s['acostarse']['cambios'], {'hora_dormir': '23:30'})

    def test_la_api_devuelve_las_sugerencias(self):
        r = self.client.get(reverse('sugerencias'))
        self.assertEqual((r.status_code, r.data), (status.HTTP_200_OK, []))
