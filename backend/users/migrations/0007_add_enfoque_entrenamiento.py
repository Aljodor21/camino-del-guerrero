from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0006_add_region'),
    ]

    operations = [
        migrations.AddField(
            model_name='objetivousuario',
            name='enfoque_entrenamiento',
            field=models.CharField(
                choices=[
                    ('boxeo',       'Boxeo'),
                    ('cardio_casa', 'Cardio en casa'),
                    ('funcional',   'Funcional / HIIT'),
                    ('fuerza',      'Fuerza'),
                    ('movilidad',   'Yoga / Movilidad'),
                ],
                default='boxeo',
                max_length=30,
            ),
        ),
    ]
