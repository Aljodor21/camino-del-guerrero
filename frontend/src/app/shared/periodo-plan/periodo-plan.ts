import { ChangeDetectionStrategy, Component, computed, effect, input, model, signal, untracked } from '@angular/core';

import { clasesChip } from '../chip';
import { formatearFecha, hoyISO, sumarDias } from '../fechas';

type Opcion = 'sugerida' | 'semanas8' | 'semanas12' | 'otra' | 'sin';

/**
 * ¿Hasta cuándo va? Se sugiere el mismo tiempo que ya había, pero se puede elegir otro o
 * dejarlo sin definir. `fecha` queda en la fecha elegida, null si es sin definir y
 * undefined mientras falte algo (por ejemplo, la fecha de "Otra fecha").
 */
@Component({
  selector: 'app-periodo-plan',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: { class: 'block' },
  template: `
    <div class="space-y-3">
      <div role="radiogroup" [attr.aria-label]="etiqueta()" class="flex flex-wrap gap-2">
        @for (o of opciones(); track o.id) {
          <button
            type="button"
            role="radio"
            [attr.aria-checked]="elegida() === o.id"
            [class]="clasesChip(elegida() === o.id)"
            (click)="elegir(o.id)"
          >
            {{ o.titulo }}
          </button>
        }
      </div>
      @switch (elegida()) {
        @case ('otra') {
          <div class="flex flex-col gap-1">
            <label for="pp-fecha" class="text-sm font-medium text-gray-600 dark:text-gray-400"
              >Fecha</label
            >
            <input
              id="pp-fecha"
              type="date"
              class="p-inputtext p-component w-full"
              [min]="minima"
              [max]="maxima"
              [value]="otra()"
              (change)="otra.set($any($event.target).value)"
            />
          </div>
        }
        @case ('sin') {
          <p class="text-xs text-gray-500 dark:text-gray-400">
            Sin fecha de control: lo defines cuando quieras, al llegar el siguiente.
          </p>
        }
        @default {
          @if (detalle(); as texto) {
            <p class="text-xs text-gray-500 dark:text-gray-400">{{ texto }}</p>
          }
        }
      }
    </div>
  `,
})
export class PeriodoPlan {
  /** Lo que se sugiere (el mismo tiempo que ya había); si no hay, solo las otras opciones. */
  readonly sugerida = input<{ titulo: string; fecha: string } | null>(null);
  readonly etiqueta = input('¿Hasta cuándo va?');
  /** La elegida: fecha, null (sin definir) o undefined (falta algo). */
  readonly fecha = model<string | null | undefined>(undefined);

  protected clasesChip = clasesChip;
  protected readonly minima = sumarDias(hoyISO(), 1);
  protected readonly maxima = sumarDias(hoyISO(), 730);
  protected elegida = signal<Opcion | null>(null);
  protected otra = signal('');

  protected opciones = computed(() => [
    ...(this.sugerida() ? [{ id: 'sugerida' as const, titulo: this.sugerida()!.titulo }] : []),
    { id: 'semanas8' as const, titulo: '8 semanas' },
    { id: 'semanas12' as const, titulo: '12 semanas' },
    { id: 'otra' as const, titulo: 'Otra fecha' },
    { id: 'sin' as const, titulo: 'Sin definir' },
  ]);

  protected detalle = computed(() => {
    const f = this.fecha();
    return f ? `Hasta el ${formatearFecha(f, 'larga')}.` : '';
  });

  constructor() {
    // La opción sugerida arranca elegida; sin sugerencia, ninguna hasta que se escoja.
    effect(() => {
      const sugerida = this.sugerida();
      untracked(() => {
        if (this.elegida() === null && sugerida) this.elegir('sugerida');
      });
    });
    effect(() => {
      const f = this.calcular();
      untracked(() => this.fecha.set(f));
    });
  }

  protected elegir(opcion: Opcion): void {
    this.elegida.set(opcion);
  }

  private calcular(): string | null | undefined {
    switch (this.elegida()) {
      case 'sugerida':
        return this.sugerida()?.fecha;
      case 'semanas8':
        return sumarDias(hoyISO(), 8 * 7);
      case 'semanas12':
        return sumarDias(hoyISO(), 12 * 7);
      case 'otra': {
        const f = this.otra();
        return f && f >= this.minima && f <= this.maxima ? f : undefined;
      }
      case 'sin':
        return null;
      default:
        return undefined;
    }
  }
}
