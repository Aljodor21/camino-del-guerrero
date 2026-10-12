from django.db import migrations


def asignar_foto_de_frente(apps, schema_editor):
    """Las ilustraciones hechas antes de guardar su foto de origen parten de la foto de frente
    más reciente de su dueño (la que usa la generación), para poder mostrarlas en comparativa."""
    Ilustracion = apps.get_model('nutricion', 'Ilustracion')
    FotoProgreso = apps.get_model('progress', 'FotoProgreso')
    for ilustracion in Ilustracion.objects.filter(foto_origen__isnull=True):
        foto = (FotoProgreso.objects.filter(medicion__usuario_id=ilustracion.usuario_id, pose='frente')
                .order_by('-medicion__fecha', '-id').first())
        if foto:
            ilustracion.foto_origen = foto
            ilustracion.save(update_fields=['foto_origen'])


class Migration(migrations.Migration):
    dependencies = [
        ('nutricion', '0016_foto_origen_de_la_ilustracion'),
        ('progress', '0007_fotoprogreso'),
    ]
    operations = [migrations.RunPython(asignar_foto_de_frente, migrations.RunPython.noop)]
