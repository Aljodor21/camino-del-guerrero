from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from auditoria.models import Evento


class Command(BaseCommand):
    help = 'Borra las huellas de auditoría más viejas que --dias (90 por defecto).'

    def add_arguments(self, parser):
        parser.add_argument('--dias', type=int, default=90)

    def handle(self, *args, dias, **options):
        borradas, _ = Evento.objects.filter(momento__lt=timezone.now() - timedelta(days=dias)).delete()
        if options['verbosity']:
            self.stdout.write(f'{borradas} huellas borradas (más de {dias} días).')
