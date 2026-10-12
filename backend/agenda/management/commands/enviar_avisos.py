import time

from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from agenda import notificaciones, push
from agenda.models import Notificacion
from users.models import Usuario


class Command(BaseCommand):
    help = 'Crea los avisos cuya hora llegó y los manda al celular. Con --cada, se queda corriendo.'

    def add_arguments(self, parser):
        parser.add_argument('--cada', type=int, default=0, help='Segundos entre revisiones (0: una vez)')

    def handle(self, *args, cada, **options):
        while True:
            self.revisar()
            if not cada:
                return
            time.sleep(cada)

    def revisar(self):
        ahora = timezone.now()
        usuarios = Usuario.objects.filter(
            Q(habitos__isnull=False) | Q(suplementos__fecha_fin__isnull=True)
            | Q(rutina__activa=True) | Q(recordatorios__completado_en__isnull=True)).distinct()
        for usuario in usuarios:
            notificaciones.generar(usuario, ahora)

        por_mandar = Notificacion.objects.filter(enviada_en__isnull=True).select_related(
            'usuario', 'recordatorio')
        # Lo muy atrasado (el servidor estuvo apagado) no se manda de golpe: queda en la app.
        por_mandar.filter(programada_para__lt=ahora - notificaciones.VIGENCIA_PUSH).update(enviada_en=ahora)
        for n in por_mandar.filter(resuelta_en__isnull=True, programada_para__lte=ahora):
            push.enviar(n)
            n.enviada_en = timezone.now()
            n.save(update_fields=['enviada_en'])
