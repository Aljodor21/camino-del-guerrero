import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """ObjetivoUsuario queda solo con los datos de entrenamiento, colgado de su Proceso."""

    dependencies = [
        ('users', '0010_objetivos_a_procesos'),
        ('nutricion', '0006_plannutricional_proceso'),
    ]

    operations = [
        migrations.RemoveField(model_name='objetivousuario', name='usuario'),
        migrations.RemoveField(model_name='objetivousuario', name='objetivo'),
        migrations.RemoveField(model_name='objetivousuario', name='peso_inicial'),
        migrations.RemoveField(model_name='objetivousuario', name='peso_objetivo'),
        migrations.RemoveField(model_name='objetivousuario', name='fecha_inicio'),
        migrations.RemoveField(model_name='objetivousuario', name='activo'),
        migrations.AlterField(
            model_name='objetivousuario',
            name='proceso',
            field=models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='entrenamiento', to='users.proceso'),
        ),
        migrations.RenameModel('ObjetivoUsuario', 'ConfiguracionEntrenamiento'),
    ]
