import base64

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from django.core.management.base import BaseCommand


def _b64(datos):
    return base64.urlsafe_b64encode(datos).rstrip(b'=').decode()


class Command(BaseCommand):
    help = 'Genera las llaves VAPID para las notificaciones al celular (van en .env.docker).'

    def handle(self, *args, **options):
        privada = ec.generate_private_key(ec.SECP256R1())
        numero = privada.private_numbers().private_value.to_bytes(32, 'big')
        publica = privada.public_key().public_bytes(serialization.Encoding.X962,
                                                     serialization.PublicFormat.UncompressedPoint)
        self.stdout.write(f'VAPID_PUBLIC_KEY={_b64(publica)}')
        self.stdout.write(f'VAPID_PRIVATE_KEY={_b64(numero)}')
        self.stdout.write('VAPID_EMAIL=tu-correo@ejemplo.com')
