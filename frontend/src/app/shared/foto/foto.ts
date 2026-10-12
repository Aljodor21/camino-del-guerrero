import { Component, ChangeDetectionStrategy, inject, input } from '@angular/core';
import { toObservable, toSignal } from '@angular/core/rxjs-interop';
import { catchError, map, of, startWith, switchMap } from 'rxjs';

import { FotoService, TamanoFoto } from '../../core/services/foto';

type Carga = { estado: 'cargando' } | { estado: 'lista'; url: string } | { estado: 'error' };

/** Muestra una foto privada de progreso. Ocupa todo su contenedor; el contenedor define la proporción. */
@Component({
  selector: 'app-foto',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: { class: 'block relative overflow-hidden bg-gray-100 dark:bg-dark-900' },
  template: `
    @let c = carga();
    @if (c.estado === 'lista') {
      <img [src]="c.url" [alt]="alt()" class="absolute inset-0 w-full h-full" [class]="ajuste()" />
    } @else if (c.estado === 'error') {
      <div
        class="absolute inset-0 flex items-center justify-center text-gray-400"
        role="img"
        [attr.aria-label]="alt()"
      >
        <i class="pi pi-image text-xl" aria-hidden="true"></i>
      </div>
    } @else {
      <div
        class="absolute inset-0 animate-pulse bg-gray-200 dark:bg-dark-700"
        aria-hidden="true"
      ></div>
    }
  `,
})
export class Foto {
  private fotos = inject(FotoService);

  readonly fotoId = input.required<number>();
  readonly tamano = input<TamanoFoto>('mini');
  readonly alt = input('');
  /** object-cover recorta para llenar; object-contain muestra la foto completa. */
  readonly ajuste = input<'object-cover' | 'object-contain'>('object-cover');

  private peticion = toObservable(this.fotoId).pipe(
    switchMap((id) =>
      this.fotos.url(id, this.tamano()).pipe(
        map((url): Carga => ({ estado: 'lista', url })),
        catchError(() => of<Carga>({ estado: 'error' })),
        startWith<Carga>({ estado: 'cargando' }),
      ),
    ),
  );

  protected carga = toSignal(this.peticion, { initialValue: { estado: 'cargando' } as Carga });
}
