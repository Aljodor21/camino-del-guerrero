import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


def _medida():
    return models.FloatField(null=True, blank=True)


class Migration(migrations.Migration):

    dependencies = [
        ('progress', '0003_fix_localdate'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Medicion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('fecha', models.DateField(default=django.utils.timezone.localdate)),
                ('origen', models.CharField(choices=[('propia', 'Tomada por mí'), ('profesional', 'Tomada por un profesional')], default='propia', max_length=20)),
                ('peso_kg', models.FloatField()),
                ('talla_cm', _medida()),
                ('cintura_cm', _medida()),
                ('abdomen_cm', _medida()),
                ('cadera_cm', _medida()),
                ('brazo_cm', _medida()),
                ('muslo_cm', _medida()),
                ('pierna_cm', _medida()),
                ('pliegue_triceps_mm', _medida()),
                ('pliegue_biceps_mm', _medida()),
                ('pliegue_subescapular_mm', _medida()),
                ('pliegue_supraespinal_mm', _medida()),
                ('pliegue_abdominal_mm', _medida()),
                ('pliegue_muslo_mm', _medida()),
                ('pliegue_pierna_mm', _medida()),
                ('pliegue_cresta_iliaca_mm', _medida()),
                ('nota', models.CharField(blank=True, max_length=300)),
                ('fecha_registro', models.DateTimeField(auto_now_add=True)),
                ('usuario', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='mediciones', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['-fecha', '-id']},
        ),
    ]
