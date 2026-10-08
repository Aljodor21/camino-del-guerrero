import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0008_add_implementos_adicionales'),
        ('progress', '0004_medicion'),
    ]

    operations = [
        migrations.CreateModel(
            name='Proceso',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('objetivo', models.CharField(choices=[('bajar_peso', 'Bajar peso'), ('ganar_musculo', 'Ganar músculo'), ('mantener', 'Mantener peso'), ('resistencia', 'Mejorar resistencia')], max_length=50)),
                ('fase', models.CharField(blank=True, choices=[('volumen', 'Volumen'), ('definicion', 'Definición'), ('mantenimiento', 'Mantenimiento')], max_length=20)),
                ('peso_objetivo', models.FloatField(blank=True, null=True)),
                ('incluye_alimentacion', models.BooleanField(default=True)),
                ('incluye_entrenamiento', models.BooleanField(default=False)),
                ('fecha_inicio', models.DateField(default=django.utils.timezone.localdate)),
                ('fecha_fin', models.DateField(blank=True, null=True)),
                ('notas', models.TextField(blank=True)),
                ('fecha_creacion', models.DateTimeField(auto_now_add=True)),
                ('medicion_inicial', models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='proceso_iniciado', to='progress.medicion')),
                ('usuario', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='procesos', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-fecha_inicio', '-id'],
                'constraints': [
                    models.UniqueConstraint(condition=models.Q(fecha_fin__isnull=True), fields=('usuario',), name='proceso_unico_abierto_por_usuario'),
                    models.CheckConstraint(condition=models.Q(incluye_alimentacion=True) | models.Q(incluye_entrenamiento=True), name='proceso_con_algun_modulo'),
                    models.CheckConstraint(condition=models.Q(fecha_fin__isnull=True) | models.Q(fecha_fin__gte=models.F('fecha_inicio')), name='proceso_fechas_coherentes'),
                ],
            },
        ),
        migrations.AddField(
            model_name='objetivousuario',
            name='proceso',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='users.proceso'),
        ),
    ]
