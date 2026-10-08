from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('progress', '0005_registropeso_a_medicion'),
        ('users', '0010_objetivos_a_procesos'),
    ]

    operations = [
        migrations.DeleteModel(name='RegistroPeso'),
    ]
