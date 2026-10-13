import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  effect,
  inject,
  viewChild,
} from '@angular/core';

import { CelebracionesService } from '../../core/services/celebraciones';
import { formatearFecha } from '../fechas';
import { Guerrero } from '../guerrero/guerrero';
import { Medalla } from '../medalla/medalla';

/** Pedacitos de confeti: posición, giro, retraso y color salen de este reparto fijo (sin azar, así
 *  se ve igual cada vez y no hay saltos al renderizar). */
const COLORES = ['#c0392b', '#d4af37', '#f1ece5', '#a83224', '#b8960f'];
const CONFETI = Array.from({ length: 28 }, (_, i) => ({
  x: ((i * 37) % 100) - 50,
  giro: ((i * 83) % 720) - 360,
  retraso: (i % 7) * 0.08,
  duracion: 1.6 + (i % 5) * 0.22,
  color: COLORES[i % COLORES.length],
  ancho: 5 + (i % 3) * 2,
}));

/** La celebración: al cerrar el día al 100 % o al lograr un hito. Se cierra con el botón, Escape o tocando fuera. */
@Component({
  selector: 'app-celebracion',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [Guerrero, Medalla],
  template: `
    @if (servicio.fiesta(); as f) {
      <div
        class="fondo fixed inset-0 z-[60] flex items-center justify-center p-4 bg-black/70"
        (click)="servicio.cerrar()"
        (keydown.escape)="servicio.cerrar()"
      >
        <div
          class="tarjeta relative w-full max-w-sm rounded-3xl bg-dark-800 border border-guerrero-gold/40 shadow-2xl overflow-hidden text-center px-6 pt-8 pb-6"
          role="dialog"
          aria-modal="true"
          aria-labelledby="cel-titulo"
          aria-describedby="cel-texto"
          (click)="$event.stopPropagation()"
        >
          <div class="confeti" aria-hidden="true">
            @for (c of confeti; track $index) {
              <i
                [style.--x.px]="c.x * 2.6"
                [style.--giro.deg]="c.giro"
                [style.animation-delay.s]="c.retraso"
                [style.animation-duration.s]="c.duracion"
                [style.background]="c.color"
                [style.width.px]="c.ancho"
                [style.height.px]="c.ancho * 1.8"
              ></i>
            }
          </div>

          @if (f.tipo === 'dia') {
            <app-guerrero estado="celebra" [tamano]="132" />
            <h2 id="cel-titulo" class="mt-3 text-2xl font-bold text-white">Día completo</h2>
            <p id="cel-texto" class="mt-1 text-sm text-gray-300">
              Hoy cumpliste todo lo que tocaba. Así se camina.
            </p>
          } @else {
            <div class="flex justify-center gap-2">
              @for (h of f.hitos.slice(0, 3); track h.id) {
                <app-medalla
                  [grupo]="h.grupo"
                  [nivel]="h.nivel"
                  [nombre]="h.nombre"
                  [tamano]="f.hitos.length === 1 ? 112 : 80"
                />
              }
            </div>
            <p class="mt-3 text-xs font-semibold uppercase tracking-wider text-guerrero-gold">
              {{ f.hitos.length === 1 ? 'Nuevo hito' : f.hitos.length + ' hitos nuevos' }}
            </p>
            <h2 id="cel-titulo" class="mt-1 text-2xl font-bold text-white">
              {{ f.hitos[0].nombre }}
            </h2>
            <p id="cel-texto" class="mt-1 text-sm text-gray-300">
              @if (f.hitos.length === 1) {
                {{ f.hitos[0].descripcion }}
                @if (f.hitos[0].logrado_en) {
                  <span class="block mt-1 text-xs text-gray-400"
                    >Logrado el {{ fecha(f.hitos[0].logrado_en!) }}</span
                  >
                }
              } @else {
                Y {{ f.hitos.length - 1 }} más. Míralos en Avisos › Logros.
              }
            </p>
          }

          <button
            #seguir
            type="button"
            class="mt-6 w-full rounded-xl bg-guerrero-red px-4 py-3 font-semibold text-white focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-guerrero-gold"
            (click)="servicio.cerrar()"
          >
            Seguir
          </button>
        </div>
      </div>
    }
  `,
  styles: `
    .fondo {
      animation: aparece-fondo 0.25s ease-out backwards;
    }
    .tarjeta {
      animation: sube 0.45s cubic-bezier(0.3, 1.4, 0.5, 1) backwards;
    }
    .confeti {
      position: absolute;
      inset: 0;
      pointer-events: none;
    }
    .confeti i {
      position: absolute;
      top: -14px;
      left: 50%;
      border-radius: 1px;
      animation: cae 2s ease-in 1 backwards;
    }
    @keyframes aparece-fondo {
      from {
        opacity: 0;
      }
    }
    @keyframes sube {
      from {
        opacity: 0;
        transform: translateY(24px) scale(0.92);
      }
    }
    @keyframes cae {
      0% {
        opacity: 1;
        transform: translate(0, 0) rotate(0);
      }
      100% {
        opacity: 0;
        transform: translate(var(--x), 380px) rotate(var(--giro));
      }
    }
    @media (prefers-reduced-motion: reduce) {
      .fondo,
      .tarjeta {
        animation: none;
      }
      .confeti {
        display: none;
      }
    }
  `,
})
export class Celebracion {
  protected servicio = inject(CelebracionesService);
  protected confeti = CONFETI;
  private boton = viewChild<ElementRef<HTMLButtonElement>>('seguir');

  constructor() {
    // El foco pasa al botón al abrirse, para que Enter o Espacio la cierren.
    effect(() => {
      this.boton()?.nativeElement.focus();
    });
  }

  protected fecha(iso: string): string {
    return formatearFecha(iso, 'larga');
  }
}
