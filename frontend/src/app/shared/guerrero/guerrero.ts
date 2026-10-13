import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';

export type EstadoGuerrero = 'descansa' | 'firme' | 'celebra';

/** El estado del guerrero según cuánto va del día: poco, a medias o la meta. */
export function estadoDe(porcentaje: number | null | undefined, meta = 80): EstadoGuerrero {
  if (porcentaje == null || porcentaje < 30) return 'descansa';
  return porcentaje >= meta ? 'celebra' : 'firme';
}

/**
 * El guerrero del logo, de busto y dibujado a mano en SVG. Tiene tres estados: descansa (cabeza baja,
 * ojos cerrados), firme (de pie, atento) y celebra (ojos dorados, salta). Sin imágenes: pesa casi nada
 * y las animaciones son solo CSS (se apagan con «reducir movimiento»).
 */
@Component({
  selector: 'app-guerrero',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: { class: 'inline-block', '[style.width.px]': 'tamano()', '[style.height.px]': 'tamano()' },
  template: `
    <svg
      viewBox="0 -12 120 144"
      class="g"
      [class]="'g ' + estado()"
      role="img"
      [attr.aria-label]="etiqueta()"
    >
      <defs>
        <linearGradient id="g-casco" x1="0" x2="1" y1="0" y2="0">
          <stop offset="0" stop-color="#d9503f" />
          <stop offset="0.55" stop-color="#c0392b" />
          <stop offset="1" stop-color="#8f2a1f" />
        </linearGradient>
        <linearGradient id="g-cuerpo" x1="0" x2="1" y1="0" y2="0">
          <stop offset="0" stop-color="#a8322a" />
          <stop offset="1" stop-color="#6e1f18" />
        </linearGradient>
        <radialGradient id="g-aura" cx="0.5" cy="0.45" r="0.5">
          <stop offset="0.55" stop-color="#d4af37" stop-opacity="0.35" />
          <stop offset="1" stop-color="#d4af37" stop-opacity="0" />
        </radialGradient>
      </defs>

      <circle class="aura" cx="60" cy="52" r="62" fill="url(#g-aura)" />

      <g class="todo">
        <!-- hombros y peto -->
        <path d="M4 132 C6 106 26 96 44 96 L76 96 C94 96 114 106 116 132 Z" fill="url(#g-cuerpo)" />
        <path
          d="M12 122 C16 110 30 102 44 100 M108 122 C104 110 90 102 76 100"
          fill="none"
          stroke="#d4af37"
          stroke-width="2.4"
          stroke-linecap="round"
        />
        <path
          d="M44 96 L60 114 L76 96"
          fill="none"
          stroke="#d4af37"
          stroke-width="3"
          stroke-linejoin="round"
        />
        <rect x="50" y="86" width="20" height="14" fill="#4a130e" />

        <g class="cabeza">
          <!-- cresta -->
          <g class="cresta">
            <path
              d="M54 20 C52 6 55 -6 60 -14 C65 -6 68 6 66 20 Z"
              fill="#8f2a1f"
              stroke="#d4af37"
              stroke-width="1.6"
              stroke-linejoin="round"
            />
            <path d="M60 -8 C58 0 58 10 60 18" fill="none" stroke="#c0392b" stroke-width="2" />
          </g>
          <!-- casco -->
          <path
            d="M60 14 C82 14 98 30 98 56 L98 74 C98 86 92 96 84 102 L76 108 L70 92 L50 92 L44 108 L36 102 C28 96 22 86 22 74 L22 56 C22 30 38 14 60 14 Z"
            fill="url(#g-casco)"
            stroke="#d4af37"
            stroke-width="2.6"
            stroke-linejoin="round"
          />
          <path
            d="M38 40 C44 28 54 24 60 24"
            fill="none"
            stroke="#f1ece5"
            stroke-opacity="0.28"
            stroke-width="2.4"
            stroke-linecap="round"
          />
          <path
            d="M56.5 22 L63.5 22 L65 58 L62 94 L58 94 L55 58 Z"
            fill="#a8322a"
            stroke="#d4af37"
            stroke-width="1"
            stroke-linejoin="round"
          />
          <path
            d="M36 48 L56 53 M84 48 L64 53"
            fill="none"
            stroke="#d4af37"
            stroke-width="1.8"
            stroke-linecap="round"
          />
          <!-- aberturas de los ojos y de la boca -->
          <path d="M37 51 L56 56 L56 66 L40 64 Z M83 51 L64 56 L64 66 L80 64 Z" fill="#120a08" />
          <path d="M50 78 L70 78 L68 91 L52 91 Z" fill="#120a08" />
          <!-- ojos -->
          <g class="ojos">
            <path class="ojo" d="M42 58 L54 61 L54 64 L43 63 Z" />
            <path class="ojo" d="M78 58 L66 61 L66 64 L77 63 Z" />
          </g>
        </g>
      </g>
    </svg>
  `,
  styles: `
    :host {
      line-height: 0;
    }
    .g {
      width: 100%;
      height: 100%;
      overflow: visible;
    }
    .aura {
      opacity: 0;
      transform-origin: 60px 52px;
    }
    .ojo {
      fill: #f1ece5;
      transform-box: fill-box;
      transform-origin: center;
      transition:
        fill 0.4s,
        transform 0.4s;
    }
    .cresta,
    .cabeza,
    .todo {
      transition: transform 0.5s cubic-bezier(0.3, 1.4, 0.5, 1);
    }
    .cresta {
      transform-origin: 60px 18px;
      transform-box: view-box;
    }
    .cabeza {
      transform-origin: 60px 100px;
      transform-box: view-box;
    }

    /* descansa: cabeza baja, ojos cerrados y colores apagados */
    .descansa {
      filter: saturate(0.55) brightness(0.85);
    }
    .descansa .ojo {
      transform: scaleY(0.12);
    }
    .descansa .cabeza {
      transform: translateY(5px) rotate(4deg);
    }
    .descansa .cresta {
      transform: rotate(-12deg);
    }
    .descansa .todo {
      animation: respira 4.5s ease-in-out infinite;
    }

    /* firme: de pie, atento */
    .firme .todo {
      animation: respira 3.2s ease-in-out infinite;
    }
    .firme .cabeza {
      animation: mira 7s ease-in-out infinite;
    }

    /* celebra: ojos dorados, salta y se enciende el aura */
    .celebra .ojo {
      fill: #ffd54a;
      filter: drop-shadow(0 0 3px #d4af37);
    }
    .celebra .aura {
      opacity: 1;
      animation: aura 1.8s ease-in-out infinite;
    }
    .celebra .cresta {
      transform: translateY(-2px) scaleY(1.08);
    }
    .celebra .todo {
      animation: salta 0.9s cubic-bezier(0.3, 0.7, 0.4, 1) 3;
    }

    @keyframes respira {
      50% {
        transform: translateY(-1.8px);
      }
    }
    @keyframes mira {
      0%,
      100% {
        transform: rotate(0);
      }
      35% {
        transform: rotate(-2.5deg);
      }
      70% {
        transform: rotate(2.5deg);
      }
    }
    @keyframes salta {
      0%,
      100% {
        transform: translateY(0);
      }
      40% {
        transform: translateY(-9px);
      }
    }
    @keyframes aura {
      50% {
        transform: scale(1.07);
        opacity: 0.7;
      }
    }
    @media (prefers-reduced-motion: reduce) {
      .todo,
      .cabeza,
      .aura {
        animation: none !important;
      }
    }
  `,
})
export class Guerrero {
  readonly estado = input<EstadoGuerrero>('firme');
  readonly tamano = input(96);

  protected etiqueta = computed(
    () =>
      ({
        descansa: 'El guerrero descansa',
        firme: 'El guerrero está firme',
        celebra: 'El guerrero celebra',
      })[this.estado()],
  );
}
