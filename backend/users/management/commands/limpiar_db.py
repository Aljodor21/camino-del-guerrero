from django.core.management.base import BaseCommand

from nutricion.models import ItemMercado, ListaMercado
from progress.models import Medicion, RegistroEntrenamiento
from routines.models import DiaRutina, EjercicioDia, EjercicioImplemento, Ejercicio, Rutina, UsuarioImplemento
from users.models import Proceso, Usuario


class Command(BaseCommand):
    help = 'Limpia la BD conservando solo admin, Implemento, Rol y Sexo'

    def handle(self, *args, **options):
        # Nutricion
        ItemMercado.objects.all().delete()
        ListaMercado.objects.all().delete()
        self.stdout.write('Nutricion eliminada.')

        # Progress
        RegistroEntrenamiento.objects.all().delete()
        self.stdout.write('Registros de entrenamiento eliminados.')

        # Routines (ejercicios incluidos)
        EjercicioDia.objects.all().delete()
        DiaRutina.objects.all().delete()
        Rutina.objects.all().delete()
        UsuarioImplemento.objects.all().delete()
        EjercicioImplemento.objects.all().delete()
        Ejercicio.objects.all().delete()
        self.stdout.write('Rutinas y ejercicios eliminados.')

        # Procesos (su configuración de entrenamiento cae en cascada) y mediciones.
        # Los procesos van primero porque protegen su medición inicial.
        Proceso.objects.all().delete()
        Medicion.objects.all().delete()
        self.stdout.write('Procesos y mediciones eliminados.')

        # Usuarios no-admin (conserva usuarios con rol admin)
        eliminados, _ = Usuario.objects.exclude(rol__nombre='admin').delete()
        self.stdout.write(f'Usuarios eliminados: {eliminados}')

        self.stdout.write(self.style.SUCCESS('Limpieza completada. Se conservaron Implemento, Rol y Sexo.'))
