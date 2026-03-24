from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('routines', '0002_recomendacion'),
    ]

    operations = [
        migrations.AddField(
            model_name='ejercicio',
            name='busqueda_media',
            field=models.CharField(
                blank=True,
                max_length=100,
                help_text='Término en inglés para buscar GIFs/videos (generado por IA)',
            ),
        ),
    ]
