import { ChangeDetectionStrategy, Component, DestroyRef, inject, input, signal } from '@angular/core';
import { toObservable, takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { combineLatest } from 'rxjs';
import { switchMap } from 'rxjs/operators';

import { SuplementoService } from '../core/services/suplemento';

/** La foto del producto; es privada, así que se pide con el token. Se vuelve a pedir si cambia `version`. */
@Component({
  selector: 'app-foto-suplemento',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (url(); as src) {
      <img [src]="src" alt="Foto del producto" class="w-full h-full object-cover" />
    }
  `,
  host: { class: 'block overflow-hidden bg-gray-100 dark:bg-dark-700' },
})
export class FotoSuplemento {
  readonly suplemento = input.required<number>();
  /** Cualquier valor que cambie cuando se sube o se quita la foto. */
  readonly version = input<unknown>(null);
  protected url = signal<string | null>(null);

  constructor() {
    const servicio = inject(SuplementoService);
    combineLatest([toObservable(this.suplemento), toObservable(this.version)])
      .pipe(
        switchMap(([id]) => servicio.verFoto(id)),
        takeUntilDestroyed(),
      )
      .subscribe({
        next: (blob) => {
          this.soltar();
          this.url.set(URL.createObjectURL(blob));
        },
        error: () => this.url.set(null),
      });
    inject(DestroyRef).onDestroy(() => this.soltar());
  }

  private soltar(): void {
    const u = this.url();
    if (u) URL.revokeObjectURL(u);
  }
}
