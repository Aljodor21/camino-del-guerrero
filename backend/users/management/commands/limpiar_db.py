from django.core.management.base import BaseCommand

from nutricion.models import DiaNutricional, ItemMercado, ListaMercado, PlanNutricional
from progress.models import RegistroEntrenamiento, RegistroPeso
from routines.models import DiaRutina, EjercicioDia, EjercicioImplemento, Ejercicio, Rutina, UsuarioImplemento
from users.models import ObjetivoUsuario, Usuario


class Command(BaseCommand):
    help = 'Limpia la BD conservando solo admin, Implemento, Rol y Sexo'

    def handle(self, *args, **options):
        # Nutricion
        ItemMercado.objects.all().delete()
        ListaMercado.objects.all().delete()
        DiaNutricional.objects.all().delete()
        PlanNutricional.objects.all().delete()
        self.stdout.write('Nutricion eliminada.')

        # Progress
        RegistroEntrenamiento.objects.all().delete()
        RegistroPeso.objects.all().delete()
        self.stdout.write('Progress eliminado.')

        # Routines (ejercicios incluidos)
        EjercicioDia.objects.all().delete()
        DiaRutina.objects.all().delete()
        Rutina.objects.all().delete()
        UsuarioImplemento.objects.all().delete()
        EjercicioImplemento.objects.all().delete()
        Ejercicio.objects.all().delete()
        self.stdout.write('Rutinas y ejercicios eliminados.')

        # Objetivos
        ObjetivoUsuario.objects.all().delete()
        self.stdout.write('Objetivos eliminados.')

        # Usuarios no-admin (conserva usuarios con rol admin)
        eliminados, _ = Usuario.objects.exclude(rol__nombre='admin').delete()
        self.stdout.write(f'Usuarios eliminados: {eliminados}')

        self.stdout.write(self.style.SUCCESS('Limpieza completada. Se conservaron Implemento, Rol y Sexo.'))
