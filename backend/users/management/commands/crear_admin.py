from django.core.management.base import BaseCommand
from decouple import config

from users.models import Rol, Usuario


class Command(BaseCommand):
    help = 'Crea el usuario administrador de la app desde variables de entorno'

    def handle(self, *args, **options):
        email    = config('ADMIN_EMAIL',    default='')
        password = config('ADMIN_PASSWORD', default='')
        nombre   = config('ADMIN_NOMBRE',   default='Administrador')

        if not email or not password:
            self.stdout.write(self.style.WARNING(
                'ADMIN_EMAIL o ADMIN_PASSWORD no definidos — se omite la creación del admin.'
            ))
            return

        if Usuario.objects.filter(email=email).exists():
            self.stdout.write(self.style.SUCCESS(
                f'El usuario admin ({email}) ya existe — sin cambios.'
            ))
            return

        rol_admin, _ = Rol.objects.get_or_create(nombre='admin')

        usuario = Usuario.objects.create_user(
            email=email,
            username=email,
            nombre=nombre,
            password=password,
            rol=rol_admin,
        )

        self.stdout.write(self.style.SUCCESS(
            f'Usuario admin creado: {usuario.email}'
        ))
