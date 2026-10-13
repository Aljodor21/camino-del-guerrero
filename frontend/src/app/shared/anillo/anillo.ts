import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';

const RADIO = 42;
const PERIMETRO = 2 * Math.PI * RADIO;

/** El porcentaje del día como un anillo que se llena. El color sube con el avance. */
@Component({
  selector: 'app-anillo',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: {
    class: 'relative inline-block',
    '[style.width.px]': 'tamano()',
    '[style.height.px]': 'tamano()',
    '[class.anillo-pulso]': 'pulso()',
  },
  template: `
    <svg
      viewBox="0 0 100 100"
      class="w-full h-full -rotate-90"
      role="img"
      [attr.aria-label]="etiqueta()"
    >
      <circle
        cx="50"
        cy="50"
        [attr.r]="radio"
        fill="none"
        stroke-width="11"
        class="stroke-gray-200 dark:stroke-dark-700"
      />
      @if (porcentaje() !== null) {
        <circle
          cx="50"
          cy="50"
          [attr.r]="radio"
          fill="none"
          stroke-width="11"
          stroke-linecap="round"
          class="anillo-trazo"
          [class]="color()"
          [attr.stroke-dasharray]="trazo() + ' ' + perimetro"
        />
      }
    </svg>
    <span
      class="absolute inset-0 flex items-center justify-center font-bold tabular-nums text-gray-900 dark:text-white"
      [style.font-size.px]="tamano() * 0.26"
    >
      {{ porcentaje() === null ? '—' : porcentaje() + '%' }}
    </span>
  `,
  styles: `
    .anillo-trazo {
      transition:
        stroke-dasharray 0.9s cubic-bezier(0.3, 1, 0.4, 1),
        stroke 0.4s;
    }
    :host(.anillo-pulso) {
      animation: anillo-pulso 0.6s cubic-bezier(0.3, 1.5, 0.5, 1);
    }
    @keyframes anillo-pulso {
      40% {
        transform: scale(1.12);
      }
    }
    @media (prefers-reduced-motion: reduce) {
      .anillo-trazo {
        transition: none;
      }
      :host(.anillo-pulso) {
        animation: none;
      }
    }
  `,
})
export class Anillo {
  readonly porcentaje = input<number | null>(null);
  readonly tamano = input(64);
  readonly meta = input(50);
  /** Cambia cuando algo se acaba de anotar: el anillo da un salto. */
  readonly pulso = input(false);

  protected radio = RADIO;
  protected perimetro = PERIMETRO;
  protected trazo = computed(() => (Math.min(this.porcentaje() ?? 0, 100) / 100) * PERIMETRO);
  protected color = computed(() => {
    const p = this.porcentaje() ?? 0;
    if (p >= this.meta()) return 'stroke-emerald-500';
    return p >= this.meta() / 2 ? 'stroke-amber-500' : 'stroke-guerrero-red';
  });
  protected etiqueta = computed(() =>
    this.porcentaje() === null
      ? 'Sin datos de hoy'
      : `Hoy llevas el ${this.porcentaje()} por ciento`,
  );
}
