from datetime import timedelta
from itertools import groupby

from django.db import migrations


def objetivos_a_procesos(apps, schema_editor):
    """Convierte cada ObjetivoUsuario en un Proceso con ambos módulos.

    Se conservan intactos el objetivo, el peso meta y la fecha de inicio. El
    peso_inicial queda como medición inicial: se reutiliza la medición del
    mismo día y peso (la que guardó el onboarding) o se crea una nueva.
    """
    ObjetivoUsuario = apps.get_model('users', 'ObjetivoUsuario')
    Proceso = apps.get_model('users', 'Proceso')
    Medicion = apps.get_model('progress', 'Medicion')

    objetivos = ObjetivoUsuario.objects.select_related('usuario').order_by('usuario_id', 'fecha_inicio', 'id')
    for _, grupo in groupby(objetivos, key=lambda o: o.usuario_id):
        grupo = list(grupo)
        usadas = set()
        for i, obj in enumerate(grupo):
            siguiente = grupo[i + 1] if i + 1 < len(grupo) else None
            fecha_fin = None
            if siguiente:
                fecha_fin = max(obj.fecha_inicio, siguiente.fecha_inicio - timedelta(days=1))

            medicion = (Medicion.objects
                        .filter(usuario_id=obj.usuario_id, fecha=obj.fecha_inicio,
                                peso_kg__gte=obj.peso_inicial - 0.05, peso_kg__lte=obj.peso_inicial + 0.05)
                        .exclude(pk__in=usadas).order_by('id').first())
            if medicion is None:
                medicion = Medicion.objects.create(
                    usuario_id=obj.usuario_id, fecha=obj.fecha_inicio, peso_kg=obj.peso_inicial,
                    talla_cm=obj.usuario.estatura, origen='propia',
                )
            usadas.add(medicion.pk)

            proceso = Proceso.objects.create(
                usuario_id=obj.usuario_id,
                objetivo=obj.objetivo,
                peso_objetivo=obj.peso_objetivo,
                incluye_alimentacion=True,
                incluye_entrenamiento=True,
                fecha_inicio=obj.fecha_inicio,
                fecha_fin=fecha_fin,
                medicion_inicial=medicion,
            )
            obj.proceso = proceso
            obj.save(update_fields=['proceso'])


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0009_proceso'),
        ('progress', '0005_registropeso_a_medicion'),
    ]

    operations = [
        migrations.RunPython(objetivos_a_procesos, migrations.RunPython.noop),
    ]
