import django.db.models.deletion
from django.db import migrations, models


def enlazar_planes(apps, schema_editor):
    PlanNutricional = apps.get_model('nutricion', 'PlanNutricional')
    for plan in PlanNutricional.objects.select_related('objetivo').exclude(objetivo=None):
        plan.proceso_id = plan.objetivo.proceso_id
        plan.save(update_fields=['proceso'])


class Migration(migrations.Migration):

    dependencies = [
        ('nutricion', '0005_itemmercado_frecuencia_and_more'),
        ('users', '0010_objetivos_a_procesos'),
    ]

    operations = [
        migrations.AddField(
            model_name='plannutricional',
            name='proceso',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='planes_nutricionales', to='users.proceso'),
        ),
        migrations.RunPython(enlazar_planes, migrations.RunPython.noop),
        migrations.RemoveField(model_name='plannutricional', name='objetivo'),
    ]
