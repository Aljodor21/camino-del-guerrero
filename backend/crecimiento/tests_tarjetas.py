from datetime import date, timedelta

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from core.exceptions import ReglaNegocioError
from users.models import Usuario

from . import diario, tarjetas
from .models import Gasto, Proceso, Proyecto, Tarjeta

HOY = timezone.localdate


class CortesTest(APITestCase):
    def test_el_corte_el_pago_y_las_cuotas(self):
        t = Tarjeta(nombre='Visa', dia_corte=25, dia_pago=10)
        oct_ = tarjetas.ordinal(t, date(2026, 10, 25))
        self.assertEqual(tarjetas.ordinal(t, date(2026, 10, 26)), oct_ + 1)
        self.assertEqual(tarjetas.periodo(t, oct_), (date(2026, 9, 26), date(2026, 10, 25)))
        self.assertEqual(tarjetas.pago(t, oct_), date(2026, 11, 10))
        # Un corte el 31 cae el último día de los meses cortos; un pago después del corte va ese mes.
        t = Tarjeta(nombre='Master', dia_corte=31, dia_pago=None)
        self.assertEqual(tarjetas.corte(t, tarjetas.ordinal(t, date(2027, 2, 3))), date(2027, 2, 28))
        self.assertIsNone(tarjetas.pago(t, 0))
        t = Tarjeta(nombre='Otra', dia_corte=5, dia_pago=20)
        self.assertEqual(tarjetas.pago(t, tarjetas.ordinal(t, date(2026, 10, 1))), date(2026, 10, 20))
        # Sin día de corte, el periodo es el mes.
        t = Tarjeta(nombre='Mes')
        self.assertEqual(tarjetas.periodo(t, tarjetas.ordinal(t, date(2026, 10, 9))),
                         (date(2026, 10, 1), date(2026, 10, 31)))
        self.assertEqual(tarjetas.cuotas_de(100001, 3), [33335, 33333, 33333])


class TarjetasTest(APITestCase):
    def setUp(self):
        self.usuario = Usuario.objects.create_user(username='t@x.co', email='t@x.co', nombre='T',
                                                   password='clave-segura-123')
        self.client.force_authenticate(self.usuario)
        area = self.client.post(reverse('crecimiento-areas'), {'nombre': 'Educación financiera'}, format='json').data
        proceso = self.client.post(reverse('crecimiento-procesos'),
                                   {'area': area['id'], 'programa': 'sana_tus_finanzas'}, format='json').data
        self.proceso = proceso['id']
        self.proyecto = Proyecto.objects.get(proceso_id=proceso['id'], clave='diario_gastos')
        self.url = reverse('diario-tarjetas', args=[self.proyecto.id])

    def agregar(self, **extra):
        r = self.client.post(self.url, {'nombre': 'Visa', 'ultimos': '1234', 'cupo': 1000000,
                                        'dia_corte': 25, 'dia_pago': 10, **extra}, format='json')
        return r

    def anotar(self, **extra):
        datos = {'valor': 300001, 'descripcion': 'Tenis', 'categoria': 'estilo_vida', 'clase': 'emocional', **extra}
        return self.client.post(reverse('diario-gastos', args=[self.proyecto.id]), datos, format='json')

    def test_agregar_cambiar_y_validar(self):
        r = self.agregar()
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        t = r.data['tarjetas'][0]
        self.assertEqual((t['nombre'], t['ultimos'], t['disponible'], t['deuda']), ('Visa', '1234', 1000000, 0))
        self.assertEqual(self.agregar(ultimos='4111111111111111').status_code, 400)
        self.assertEqual(self.agregar(nombre=' ').status_code, 400)
        self.assertEqual(self.agregar(dia_corte=32).status_code, 400)
        r = self.client.patch(reverse('diario-tarjeta', args=[self.proyecto.id, t['id']]),
                              {'nombre': 'Visa oro', 'cupo': None}, format='json')
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        self.assertEqual((r.data['tarjetas'][0]['nombre'], r.data['tarjetas'][0]['disponible']), ('Visa oro', None))

    def test_una_compra_con_tarjeta_va_al_registro_y_a_la_tarjeta(self):
        t = self.agregar().data['tarjetas'][0]
        r = self.anotar(tarjeta=t['id'], cuotas=3)
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        self.assertEqual(r.data['resumen']['anotado']['total'], 300001)
        self.assertEqual((r.data['registro'][0]['tarjeta'], r.data['registro'][0]['cuotas']), ('Visa ·1234', 3))
        t = r.data['tarjetas'][0]
        self.assertEqual((t['comprado'], t['emocional'], t['este_corte'], t['deuda'], t['disponible']),
                         (300001, 300001, 100001, 300001, 699999))
        self.assertTrue(r.data['hoy_al_dia'])
        # Sin tarjeta no hay cuotas; las de otra persona no sirven.
        self.assertEqual(self.anotar(cuotas=2).status_code, 400)
        self.assertEqual(self.anotar(tarjeta=t['id'], cuotas=49).status_code, 400)
        otra = Tarjeta.objects.create(proyecto=Proyecto.objects.create(proceso=self.proyecto.proceso,
                                                                        clave='x', tipo='diario_gastos'),
                                      nombre='Ajena')
        self.assertEqual(self.anotar(tarjeta=otra.id).status_code, 400)

    def test_la_factura_del_corte_anterior_queda_hasta_el_dia_de_pago(self):
        t = Tarjeta.objects.create(proyecto=self.proyecto, nombre='Visa', dia_corte=25, dia_pago=10, cupo=500000)
        Gasto.objects.create(proyecto=self.proyecto, fecha=date(2026, 9, 15), valor=120000, descripcion='Mercado',
                             categoria='hogar', clase='cerebral', tarjeta=t, cuotas=2)
        r = tarjetas.resumen_de(t, hoy=date(2026, 10, 5))
        self.assertEqual(r['factura'], {'valor': 60000, 'corte': date(2026, 9, 25), 'pago': date(2026, 10, 10)})
        self.assertEqual((r['este_corte'], r['deuda'], r['disponible']), (60000, 120000, 380000))
        r = tarjetas.resumen_de(t, hoy=date(2026, 10, 11))
        self.assertEqual((r['factura'], r['deuda']), (None, 60000))
        # El aviso: dos días antes y el mismo día del pago, sin botón.
        self.assertEqual([a['titulo'] for a in tarjetas.avisos(self.proyecto, date(2026, 10, 8))],
                         ['En 2 días pagas tu Visa'])
        self.assertEqual(tarjetas.avisos(self.proyecto, date(2026, 10, 9)), [])
        hoy = tarjetas.avisos(self.proyecto, date(2026, 10, 10))
        self.assertEqual((hoy[0]['titulo'], hoy[0]['accion']), ('Hoy pagas tu Visa', ''))
        self.assertIn('$60.000', hoy[0]['cuerpo'])
        with self.assertRaises(ReglaNegocioError):
            diario._confirmar(self.proyecto, f'pago:{t.id}', HOY())
        self.assertFalse(diario._resuelto(self.proyecto, f'pago:{t.id}', HOY()))
        self.assertTrue(diario._resuelto(self.proyecto, f'pago:{t.id}', HOY() - timedelta(days=1)))

    def test_quitar_una_tarjeta_con_compras_la_retira_y_el_registro_queda(self):
        con = self.agregar().data['tarjetas'][0]
        sin = self.agregar(nombre='Master', ultimos='').data['tarjetas']
        sin = next(x for x in sin if x['nombre'] == 'Master')
        self.anotar(tarjeta=con['id'])
        r = self.client.delete(reverse('diario-tarjeta', args=[self.proyecto.id, con['id']]))
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual([x['nombre'] for x in r.data['tarjetas']], ['Master'])
        self.assertEqual(r.data['registro'][0]['tarjeta'], 'Visa ·1234')
        self.assertFalse(Tarjeta.objects.get(pk=con['id']).activa)
        self.client.delete(reverse('diario-tarjeta', args=[self.proyecto.id, sin['id']]))
        self.assertFalse(Tarjeta.objects.filter(pk=sin['id']).exists())
        # Una tarjeta retirada ya no sirve para anotar; borrar el programa se lleva todo.
        self.assertEqual(self.anotar(tarjeta=con['id']).status_code, 400)
        self.assertEqual(self.client.delete(reverse('crecimiento-proceso', args=[self.proceso])).status_code,
                         status.HTTP_204_NO_CONTENT)
        self.assertFalse(Proceso.objects.filter(pk=self.proceso).exists() or Tarjeta.objects.exists())

    def test_lo_de_otra_persona_no_se_toca(self):
        t = self.agregar().data['tarjetas'][0]
        otro = Usuario.objects.create_user(username='z@x.co', email='z@x.co', nombre='Z', password='clave-segura-123')
        self.client.force_authenticate(otro)
        self.assertEqual(self.client.delete(reverse('diario-tarjeta', args=[self.proyecto.id, t['id']])).status_code,
                         status.HTTP_404_NOT_FOUND)
        self.assertEqual(self.agregar().status_code, status.HTTP_404_NOT_FOUND)
