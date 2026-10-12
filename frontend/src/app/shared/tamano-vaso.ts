import { ChangeDetectionStrategy, Component, computed, input, model } from '@angular/core';
import { InputTextModule } from 'primeng/inputtext';

import { clasesChip } from './chip';

export const VASO_MIN_ML = 50;
export const VASO_MAX_ML = 1500;
const COMUNES = [200, 250, 300, 330, 500];

/**
 * De cuántos ml es el vaso (o la porción) de la persona. De ahí salen las porciones del día:
 * 2 litros son 8 vasos de 250 ml o 4 de 500 ml.
 */
@Component({
  selector: 'app-tamano-vaso',
  host: { class: 'block' },
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [InputTextModule],
  template: `
    <div class="flex flex-col gap-2">
      <label [for]="id()" class="text-sm font-medium text-gray-600 dark:text-gray-400"
        >¿De cuántos ml es tu vaso?</label
      >
      <div class="flex flex-wrap items-center gap-2">
        <div role="radiogroup" aria-label="Tamaños comunes" class="flex flex-wrap gap-1.5">
          @for (ml of comunes; track ml) {
            <button
              type="button"
              role="radio"
              [attr.aria-checked]="valor() === ml"
              (click)="valor.set(ml)"
              [class]="clasesChip(valor() === ml)"
            >
              {{ ml }} ml
            </button>
          }
        </div>
        <div class="flex items-center gap-1.5">
          <input
            pInputText
            [id]="id()"
            inputmode="numeric"
            [value]="valor() ?? ''"
            (change)="leer($any($event.target).value)"
            class="w-20 text-center"
            aria-describedby="tamano-vaso-ayuda"
          />
          <span class="text-sm text-gray-500 dark:text-gray-400">ml</span>
        </div>
      </div>
      <p
        id="tamano-vaso-ayuda"
        class="text-xs"
        [class]="valido() ? 'text-gray-500 dark:text-gray-400' : 'text-red-600 dark:text-red-400'"
      >
        @if (valido()) {
          Un vaso pequeño son unos 200 ml, uno normal 250 y una botella personal 500. Así calculamos
          cuántas porciones tomas al día.
        } @else {
          Escribe un tamaño entre {{ min }} y {{ max }} ml.
        }
      </p>
    </div>
  `,
})
export class TamanoVaso {
  /** ml del vaso; es el valor de la persona (puede quedar fuera de rango mientras escribe). */
  readonly valor = model<number | null>(250);
  readonly id = input('tamano-vaso');

  protected comunes = COMUNES;
  protected min = VASO_MIN_ML;
  protected max = VASO_MAX_ML;
  protected clasesChip = clasesChip;
  protected valido = computed(() => {
    const v = this.valor();
    return v !== null && Number.isInteger(v) && v >= VASO_MIN_ML && v <= VASO_MAX_ML;
  });

  protected leer(texto: string): void {
    const n = Number(texto.replace(/[^\d]/g, ''));
    this.valor.set(texto.trim() === '' || Number.isNaN(n) ? null : n);
  }
}

/** ¿Es un tamaño que la API acepta? */
export function vasoValido(ml: number | null): boolean {
  return ml !== null && Number.isInteger(ml) && ml >= VASO_MIN_ML && ml <= VASO_MAX_ML;
}
