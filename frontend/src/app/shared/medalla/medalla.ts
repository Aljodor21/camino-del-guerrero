import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';

import { GrupoHito, NivelHito } from '../../core/models/logros.model';

/** El dibujo de cada grupo de hitos (24 × 24, solo trazos para que tome el color de la medalla). */
const ICONOS: Record<GrupoHito, string> = {
  racha: 'M5 17 L12 9 L19 17 M5 12 L12 4 L19 12',
  dias: 'M5 13 L10 18 L19 7',
  agua: 'M12 3 C12 3 5.5 10 5.5 14.5 A6.5 6.5 0 0 0 18.5 14.5 C18.5 10 12 3 12 3 Z',
  entreno: 'M3 9 V15 M6 7 V17 M18 7 V17 M21 9 V15 M6 12 H18',
  comida: 'M12 5 A7 7 0 1 0 12 19 A7 7 0 1 0 12 5 Z M12 9 A3 3 0 1 0 12 15 A3 3 0 1 0 12 9 Z',
  proteina: 'M8 5 H16 V9 H8 Z M7 9 H17 V19 H7 Z M10 13 H14',
  medicion: 'M3 8 H21 V16 H3 Z M7 8 V12 M11 8 V13 M15 8 V12 M19 8 V13',
};

const COLORES: Record<NivelHito, { borde: string; relleno: string; trazo: string }> = {
  bronce: { borde: '#b07a4a', relleno: '#3a2517', trazo: '#e0a874' },
  plata: { borde: '#b8bec6', relleno: '#2a2d31', trazo: '#e4e8ec' },
  oro: { borde: '#d4af37', relleno: '#3a2f0d', trazo: '#f3d56b' },
};

/** Una medalla en forma de escudo, como el del logo. Si aún no se logra se ve apagada. */
@Component({
  selector: 'app-medalla',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: {
    class: 'inline-block',
    '[style.width.px]': 'tamano()',
    '[style.height.px]': 'tamano() * 1.1',
  },
  template: `
    <svg viewBox="0 0 64 70" class="w-full h-full" role="img" [attr.aria-label]="etiqueta()">
      <path
        d="M32 3 L56 14 V38 C56 52 44 62 32 67 C20 62 8 52 8 38 V14 Z"
        [attr.fill]="logrado() ? col().relleno : '#221c17'"
        [attr.stroke]="logrado() ? col().borde : '#5b524a'"
        stroke-width="3"
        stroke-linejoin="round"
        [attr.stroke-dasharray]="logrado() ? null : '4 4'"
      />
      @if (logrado()) {
        <path
          d="M32 9 L50 17 V38 C50 49 41 57 32 61"
          fill="none"
          [attr.stroke]="col().borde"
          stroke-opacity="0.35"
          stroke-width="1.5"
        />
      }
      <g transform="translate(20 22) scale(1)">
        <path
          [attr.d]="icono()"
          fill="none"
          [attr.stroke]="logrado() ? col().trazo : '#7b7067'"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"
        />
      </g>
    </svg>
  `,
})
export class Medalla {
  readonly grupo = input.required<GrupoHito>();
  readonly nivel = input<NivelHito>('bronce');
  readonly logrado = input(true);
  readonly nombre = input('');
  readonly tamano = input(56);

  protected icono = computed(() => ICONOS[this.grupo()]);
  protected col = computed(() => COLORES[this.nivel()]);
  protected etiqueta = computed(
    () => `${this.nombre()}${this.logrado() ? ', logrado' : ', sin lograr'}`,
  );
}
