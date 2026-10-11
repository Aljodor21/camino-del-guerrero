from django.db import migrations, models


def a_tomas(apps, schema_editor):
    """La comida y lo que reemplazaba pasan a ser la única toma del día."""
    Suplemento = apps.get_model('nutricion', 'Suplemento')
    for s in Suplemento.objects.exclude(tiempo_comida=''):
        s.tomas = [{'tiempo': s.tiempo_comida, 'scoops': None, 'reemplaza': s.reemplaza or {}}]
        s.save(update_fields=['tomas'])


class Migration(migrations.Migration):

    dependencies = [
        ('nutricion', '0009_cargar_intercambios'),
    ]

    operations = [
        migrations.AddField(
            model_name='suplemento',
            name='peso_envase_g',
            field=models.PositiveIntegerField(blank=True, help_text='Peso neto del envase', null=True),
        ),
        migrations.AddField(
            model_name='suplemento',
            name='porcion_g',
            field=models.DecimalField(blank=True, decimal_places=1, help_text='Gramos de una porción', max_digits=5, null=True),
        ),
        migrations.AddField(
            model_name='suplemento',
            name='scoops_porcion',
            field=models.DecimalField(blank=True, decimal_places=1, help_text='Scoops que hacen una porción', max_digits=3, null=True),
        ),
        migrations.AlterField(
            model_name='suplemento',
            name='tipo',
            field=models.CharField(choices=[('hipercalorico', 'Proteína hipercalórica'), ('proteina', 'Proteína'), ('creatina', 'Creatina'), ('otro', 'Otro')], max_length=20),
        ),
        migrations.AddField(
            model_name='suplemento',
            name='tomas',
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.RunPython(a_tomas, migrations.RunPython.noop),
        migrations.RemoveField(model_name='suplemento', name='tiempo_comida'),
        migrations.RemoveField(model_name='suplemento', name='reemplaza'),
    ]
