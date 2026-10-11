import json
from pathlib import Path

from django.db import migrations

ARCHIVO = Path(__file__).resolve().parent.parent / 'datos' / 'intercambios_comfama.json'


def cargar(apps, schema_editor):
    AlimentoIntercambio = apps.get_model('nutricion', 'AlimentoIntercambio')
    alimentos = json.loads(ARCHIVO.read_text(encoding='utf-8'))
    AlimentoIntercambio.objects.bulk_create(
        [AlimentoIntercambio(**a) for a in alimentos], ignore_conflicts=True)


def borrar(apps, schema_editor):
    apps.get_model('nutricion', 'AlimentoIntercambio').objects.all().delete()


class Migration(migrations.Migration):
    """Lista de intercambios de alimentos de la nutricionista (Comfama)."""

    dependencies = [('nutricion', '0008_minuta_y_menu')]

    operations = [migrations.RunPython(cargar, borrar)]
