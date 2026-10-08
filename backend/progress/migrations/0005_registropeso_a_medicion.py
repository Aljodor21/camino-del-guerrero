from django.db import migrations


def copiar_registros_peso(apps, schema_editor):
    """Cada RegistroPeso pasa a ser una Medicion, conservando fecha, peso y nota."""
    RegistroPeso = apps.get_model('progress', 'RegistroPeso')
    Medicion = apps.get_model('progress', 'Medicion')
    Medicion.objects.bulk_create([
        Medicion(
            usuario_id=r.usuario_id,
            fecha=r.fecha,
            peso_kg=r.peso_kg,
            talla_cm=r.usuario.estatura,
            nota=r.nota,
            origen='propia',
        )
        for r in RegistroPeso.objects.select_related('usuario').order_by('fecha', 'id')
    ])


class Migration(migrations.Migration):

    dependencies = [
        ('progress', '0004_medicion'),
    ]

    operations = [
        migrations.RunPython(copiar_registros_peso, migrations.RunPython.noop),
    ]
