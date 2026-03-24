from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0007_add_enfoque_entrenamiento'),
    ]

    operations = [
        migrations.AddField(
            model_name='usuario',
            name='implementos_adicionales',
            field=models.CharField(
                blank=True,
                max_length=300,
                help_text='Implementos extra que tiene el usuario fuera del listado del admin',
            ),
        ),
    ]
