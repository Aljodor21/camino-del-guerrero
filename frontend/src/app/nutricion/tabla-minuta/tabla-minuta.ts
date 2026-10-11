import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';

import { PorcionesMinuta } from '../../core/models/minuta.model';
import { libreDe, tiemposDe } from '../../shared/minuta';
import {
  EJEMPLOS_GRUPO,
  ORDEN_GRUPOS,
  TIEMPOS_COMIDA,
  porcionesDe,
} from '../../core/constants/nutricion';

/** La minuta patrón tal como la dio la nutricionista: qué lleva cada comida. */
@Component({
  selector: 'app-tabla-minuta',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <ol class="divide-y divide-gray-100 dark:divide-dark-700">
      @for (fila of filas(); track fila.tiempo) {
        <li class="py-3 first:pt-0 last:pb-0 grid grid-cols-[6.5rem_1fr] gap-3">
          <div>
            <p class="text-sm font-semibold text-gray-900 dark:text-white">{{ fila.label }}</p>
            <p class="text-xs text-gray-500 dark:text-gray-400">{{ fila.hora }}</p>
          </div>
          <ul class="text-sm text-gray-700 dark:text-gray-200 space-y-1.5">
            @for (g of fila.grupos; track g.texto) {
              <li>
                {{ g.texto }}
                <span class="block text-xs text-gray-500 dark:text-gray-400">{{ g.ejemplo }}</span>
              </li>
            }
          </ul>
        </li>
      }
      @if (delDia().length) {
        <li class="py-3 last:pb-0 grid grid-cols-[6.5rem_1fr] gap-3">
          <div>
            <p class="text-sm font-semibold text-gray-900 dark:text-white">En el día</p>
            <p class="text-xs text-gray-500 dark:text-gray-400">Cuando quieras</p>
          </div>
          <ul class="text-sm text-gray-700 dark:text-gray-200 space-y-0.5">
            @for (g of delDia(); track g) {
              <li>{{ g }}</li>
            }
          </ul>
        </li>
      }
    </ol>
  `,
})
export class TablaMinuta {
  readonly porciones = input.required<PorcionesMinuta>();

  protected filas = computed(() => {
    const p = this.porciones();
    return tiemposDe(p).map((tiempo) => ({
      tiempo,
      ...TIEMPOS_COMIDA[tiempo],
      grupos: ORDEN_GRUPOS.filter((g) => g !== 'agua' && (p[g]?.[tiempo] ?? 0) > 0).map((g) => ({
        texto: porcionesDe(g, p[g]![tiempo]!),
        ejemplo: EJEMPLOS_GRUPO[g],
      })),
    }));
  });

  protected delDia = computed(() => {
    const p = this.porciones();
    return ORDEN_GRUPOS.filter((g) => libreDe(p[g]) > 0).map((g) => porcionesDe(g, libreDe(p[g])));
  });
}
