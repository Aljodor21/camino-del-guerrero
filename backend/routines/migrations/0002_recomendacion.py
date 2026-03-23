from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('routines', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Recomendacion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('titulo', models.CharField(max_length=200)),
                ('descripcion', models.TextField(blank=True)),
                ('url_video', models.URLField(blank=True)),
                ('categoria', models.CharField(
                    choices=[('tecnica', 'Técnica'), ('fisico', 'Físico'), ('nutricion', 'Nutrición'), ('mental', 'Mental'), ('general', 'General')],
                    default='general', max_length=20,
                )),
                ('activa', models.BooleanField(default=True)),
                ('orden', models.PositiveIntegerField(default=0)),
                ('fecha_creacion', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'ordering': ['orden', '-fecha_creacion'],
            },
        ),
    ]
