import {
  Component,
  ChangeDetectionStrategy,
  DestroyRef,
  computed,
  inject,
  input,
  model,
  signal,
} from '@angular/core';

import { Pose } from '../../core/models/proceso.model';
import { POSES } from '../../core/constants/proceso';
import { FotosPorPose, prepararFoto } from '../../core/services/foto';

/** Elige fotos por pose (frente, perfil, espalda) y muestra cómo quedarán antes de subirlas. */
@Component({
  selector: 'app-selector-fotos',
  templateUrl: './selector-fotos.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class SelectorFotos {
  readonly fotos = model<FotosPorPose>({});
  /** Poses que se pueden elegir; las demás no se muestran (p. ej. las que ya tienen foto). */
  readonly poses = input<Pose[]>(POSES.map((p) => p.value));
  readonly idPrefijo = input('fotos');

  protected opciones = computed(() => POSES.filter((p) => this.poses().includes(p.value)));
  protected procesando = signal<Pose | null>(null);
  protected error = signal('');

  private vistas = new Map<Blob, string>();

  constructor() {
    inject(DestroyRef).onDestroy(() => this.vistas.forEach((url) => URL.revokeObjectURL(url)));
  }

  protected vista(foto: Blob): string {
    let url = this.vistas.get(foto);
    if (!url) {
      url = URL.createObjectURL(foto);
      this.vistas.set(foto, url);
    }
    return url;
  }

  protected async elegir(pose: Pose, evento: Event): Promise<void> {
    const campo = evento.target as HTMLInputElement;
    const archivo = campo.files?.[0];
    campo.value = '';
    if (!archivo) return;
    this.error.set('');
    this.procesando.set(pose);
    try {
      const foto = await prepararFoto(archivo);
      this.fotos.update((actuales) => ({ ...actuales, [pose]: foto }));
    } catch {
      this.error.set('No pudimos leer esa foto. Prueba con una imagen JPG o PNG.');
    } finally {
      this.procesando.set(null);
    }
  }

  protected quitar(pose: Pose): void {
    const foto = this.fotos()[pose];
    if (foto) {
      URL.revokeObjectURL(this.vistas.get(foto) ?? '');
      this.vistas.delete(foto);
    }
    this.fotos.update(({ [pose]: _, ...resto }) => resto);
  }
}
