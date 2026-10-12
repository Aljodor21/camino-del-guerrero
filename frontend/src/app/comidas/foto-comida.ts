import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  inject,
  input,
  signal,
} from '@angular/core';
import { toObservable, takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { switchMap } from 'rxjs/operators';

import { ComidasService } from '../core/services/comidas';

/** La miniatura de la foto de una comida; es privada, así que se pide con el token. */
@Component({
  selector: 'app-foto-comida',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (url(); as src) {
      <img [src]="src" alt="Foto de tu comida" class="w-full h-full object-cover" />
    } @else {
      <span class="pi pi-image text-gray-400" aria-hidden="true"></span>
    }
  `,
  host: { class: 'flex items-center justify-center overflow-hidden bg-gray-100 dark:bg-dark-700' },
})
export class FotoComida {
  readonly registro = input.required<number>();
  protected url = signal<string | null>(null);

  constructor() {
    const comidas = inject(ComidasService);
    toObservable(this.registro)
      .pipe(
        switchMap((id) => comidas.foto(id, 'mini')),
        takeUntilDestroyed(),
      )
      .subscribe({ next: (u) => this.url.set(u), error: () => undefined });
    inject(DestroyRef).onDestroy(() => {
      const u = this.url();
      if (u) URL.revokeObjectURL(u);
    });
  }
}
