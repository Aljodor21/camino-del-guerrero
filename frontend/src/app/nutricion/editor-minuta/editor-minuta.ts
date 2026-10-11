import { ChangeDetectionStrategy, Component, computed, model, signal } from '@angular/core';
import { NgTemplateOutlet } from '@angular/common';

import { GrupoMinuta, PorcionesMinuta, TiempoComida } from '../../core/models/minuta.model';
import {
  EJEMPLOS_GRUPO,
  GRUPOS_MINUTA,
  ORDEN_GRUPOS,
  TIEMPOS_COMIDA,
} from '../../core/constants/nutricion';
import { clasesChip } from '../../shared/chip';
import { conValor, libreDe, tiemposDe } from '../../shared/minuta';

const COMIDAS_USUALES: TiempoComida[] = ['desayuno', 'onces', 'almuerzo', 'algo', 'cena'];
const GRUPOS_COMIDA = ORDEN_GRUPOS.filter((g) => g !== 'agua');
/** Lo que suele ir "en el día" y no en una comida fija. */
const GRUPOS_DIA: GrupoMinuta[] = ['agua', 'semillas'];

/**
 * Plantilla de la minuta: las porciones de cada grupo en cada comida, tal como las
 * escribió la nutricionista. Sirve para cualquier nutricionista.
 */
@Component({
  selector: 'app-editor-minuta',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="space-y-5">
      <fieldset class="space-y-2">
        <legend class="text-sm font-medium text-gray-800 dark:text-gray-100 mb-2">
          ¿Qué comidas tiene tu plan?
        </legend>
        <div class="flex flex-wrap gap-2">
          @for (t of todas; track t) {
            <button
              type="button"
              [attr.aria-pressed]="comidas().includes(t)"
              [class]="clasesChip(comidas().includes(t))"
              (click)="alternarComida(t)"
            >
              {{ tiempos[t].label }}
            </button>
          }
        </div>
      </fieldset>

      @if (comidas().length) {
        <div class="space-y-2">
          <div
            class="flex gap-1 overflow-x-auto no-scrollbar -mx-1 px-1"
            role="tablist"
            aria-label="Comida"
          >
            @for (t of comidas(); track t) {
              <button
                type="button"
                role="tab"
                [attr.aria-selected]="actual() === t"
                (click)="seleccion.set(t)"
                [class]="
                  'shrink-0 px-3 py-1.5 rounded-lg text-sm transition-colors ' +
                  (actual() === t
                    ? 'bg-guerrero-red text-white font-semibold'
                    : 'bg-gray-100 dark:bg-dark-700 text-gray-600 dark:text-gray-300')
                "
              >
                {{ tiempos[t].label }}
                @if (totalEn(t)) {
                  <span class="tabular-nums opacity-80"> · {{ totalEn(t) }}</span>
                }
              </button>
            }
          </div>
          <p class="text-xs text-gray-500 dark:text-gray-400">
            Porciones de cada grupo en {{ tiempos[actual()].con }}, como dice tu minuta.
          </p>
          <ul class="divide-y divide-gray-100 dark:divide-dark-700">
            @for (g of gruposComida; track g) {
              <li class="flex items-center justify-between gap-3 py-1.5">
                <span class="min-w-0">
                  <span class="block text-sm text-gray-800 dark:text-gray-100">{{
                    grupos[g]
                  }}</span>
                  <span class="block text-xs text-gray-500 dark:text-gray-400">{{
                    ejemplos[g]
                  }}</span>
                </span>
                <ng-container
                  *ngTemplateOutlet="
                    paso;
                    context: { grupo: g, tiempo: actual(), valor: valorEn(g, actual()) }
                  "
                />
              </li>
            }
          </ul>
        </div>
      }

      <div class="space-y-1">
        <p class="text-sm font-medium text-gray-800 dark:text-gray-100">
          En el día, cuando quieras
        </p>
        <ul class="divide-y divide-gray-100 dark:divide-dark-700">
          @for (g of gruposDia(); track g) {
            <li class="flex items-center justify-between gap-3 py-1.5">
              <span class="text-sm text-gray-800 dark:text-gray-100">
                {{ g === 'agua' ? 'Vasos de agua' : grupos[g] }}
              </span>
              <ng-container
                *ngTemplateOutlet="paso; context: { grupo: g, tiempo: null, valor: libre(g) }"
              />
            </li>
          }
        </ul>
      </div>
    </div>

    <ng-template #paso let-grupo="grupo" let-tiempo="tiempo" let-valor="valor">
      <div class="flex items-center gap-1">
        <button
          type="button"
          class="w-9 h-9 rounded-lg bg-gray-100 dark:bg-dark-700 text-gray-700 dark:text-gray-200 font-bold disabled:opacity-30"
          [disabled]="valor <= 0"
          [attr.aria-label]="'Menos ' + nombre(grupo)"
          (click)="cambiar(grupo, tiempo, valor - 1)"
        >
          −
        </button>
        <input
          type="number"
          inputmode="decimal"
          min="0"
          max="30"
          step="0.5"
          class="w-12 h-9 text-center rounded-lg border border-gray-200 dark:border-dark-700 bg-transparent text-gray-900 dark:text-white tabular-nums [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none"
          [attr.aria-label]="nombre(grupo)"
          [value]="valor"
          (change)="cambiar(grupo, tiempo, $any($event.target).valueAsNumber)"
        />
        <button
          type="button"
          class="w-9 h-9 rounded-lg bg-gray-100 dark:bg-dark-700 text-gray-700 dark:text-gray-200 font-bold disabled:opacity-30"
          [disabled]="valor >= 30"
          [attr.aria-label]="'Más ' + nombre(grupo)"
          (click)="cambiar(grupo, tiempo, valor + 1)"
        >
          +
        </button>
      </div>
    </ng-template>
  `,
  imports: [NgTemplateOutlet],
})
export class EditorMinuta {
  readonly porciones = model.required<PorcionesMinuta>();

  protected todas = Object.keys(TIEMPOS_COMIDA) as TiempoComida[];
  protected tiempos = TIEMPOS_COMIDA;
  protected grupos = GRUPOS_MINUTA;
  protected ejemplos = EJEMPLOS_GRUPO;
  protected gruposComida = GRUPOS_COMIDA;
  protected clasesChip = clasesChip;

  /** Las comidas elegidas; si llega una minuta llena, las suyas. */
  private elegidas = signal<TiempoComida[] | null>(null);
  protected comidas = computed(() => {
    const propias = this.elegidas();
    if (propias) return propias;
    const llenas = tiemposDe(this.porciones());
    return llenas.length ? llenas : COMIDAS_USUALES;
  });
  protected seleccion = signal<TiempoComida | null>(null);
  protected actual = computed(() => {
    const s = this.seleccion();
    return s && this.comidas().includes(s) ? s : this.comidas()[0];
  });
  protected gruposDia = computed(() => {
    const p = this.porciones();
    return [
      ...GRUPOS_DIA,
      ...ORDEN_GRUPOS.filter((g) => !GRUPOS_DIA.includes(g) && libreDe(p[g]) > 0),
    ];
  });

  protected nombre(grupo: string): string {
    return GRUPOS_MINUTA[grupo as GrupoMinuta];
  }

  protected valorEn(grupo: GrupoMinuta, tiempo: TiempoComida): number {
    return this.porciones()[grupo]?.[tiempo] ?? 0;
  }

  protected libre(grupo: GrupoMinuta): number {
    return libreDe(this.porciones()[grupo]);
  }

  protected totalEn(tiempo: TiempoComida): number {
    return GRUPOS_COMIDA.reduce((suma, g) => suma + this.valorEn(g, tiempo), 0);
  }

  protected cambiar(grupo: GrupoMinuta, tiempo: TiempoComida | null, valor: number): void {
    const limpio = Number.isFinite(valor)
      ? Math.min(30, Math.max(0, Math.round(valor * 2) / 2))
      : 0;
    this.porciones.update((p) => conValor(p, grupo, tiempo, limpio));
  }

  protected alternarComida(tiempo: TiempoComida): void {
    const actuales = this.comidas();
    if (actuales.includes(tiempo)) {
      // Al quitar una comida se quitan sus porciones.
      this.porciones.update((p) =>
        GRUPOS_COMIDA.reduce((acc, g) => (acc[g]?.[tiempo] ? conValor(acc, g, tiempo, 0) : acc), p),
      );
      this.elegidas.set(actuales.filter((t) => t !== tiempo));
    } else {
      this.elegidas.set(this.todas.filter((t) => t === tiempo || actuales.includes(t)));
      this.seleccion.set(tiempo);
    }
  }
}
