import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { NavigationEnd, Router, RouterLink } from '@angular/router';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { filter } from 'rxjs';

import { CelebracionesService } from '../../core/services/celebraciones';
import { Guerrero, estadoDe, META_DEL_DIA } from '../guerrero/guerrero';

/**
 * El guerrero que acompaña todos los días: siempre está en una esquina, con los días de racha, y
 * hace lo que la persona acaba de hacer (toma agua, come, duerme, se levanta, entrena). Al tocarlo
 * dice cómo va la racha y qué falta para sostenerla hoy.
 */
@Component({
  selector: 'app-companero',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [Guerrero, RouterLink],
  host: { '(document:keydown.escape)': 'abierto.set(false)' },
  template: `
    @if (!enLogros()) {
      <div class="companero" [class.actuando]="actuando()">
        @if (abierto()) {
          <section
            id="companero-panel"
            class="panel"
            aria-labelledby="companero-titulo"
            role="dialog"
            aria-label="Tu racha"
          >
            <p class="flex items-baseline gap-2">
              <span class="numero">{{ racha() }}</span>
              <span id="companero-titulo" class="text-sm font-medium text-gray-200"
                >{{ racha() === 1 ? 'día' : 'días' }} de racha</span
              >
            </p>
            <p class="text-sm text-gray-300">{{ estadoDelDia() }}</p>
            <div class="flex items-center justify-between gap-3 pt-1">
              <a
                routerLink="/avisos"
                [queryParams]="{ seccion: 'logros' }"
                class="text-sm font-semibold text-guerrero-gold focus-visible:outline-2 focus-visible:outline-guerrero-gold"
                (click)="abierto.set(false)"
                >Ver mis logros</a
              >
              <button
                type="button"
                class="text-sm text-gray-400 focus-visible:outline-2 focus-visible:outline-guerrero-gold"
                (click)="abierto.set(false)"
              >
                Cerrar
              </button>
            </div>
          </section>
        }

        @if (celebraciones.frase()) {
          <p class="frase" role="status">{{ celebraciones.frase() }}</p>
        }

        <button
          type="button"
          class="boton"
          [attr.aria-expanded]="abierto()"
          aria-controls="companero-panel"
          [attr.aria-label]="
            'Tu guerrero: ' + racha() + (racha() === 1 ? ' día' : ' días') + ' de racha'
          "
          (click)="abierto.set(!abierto())"
        >
          <app-guerrero
            [estado]="estado()"
            [accion]="celebraciones.accion()"
            [tamano]="actuando() ? 150 : 64"
            (terminada)="celebraciones.terminoDeReaccionar()"
          />
          <span class="insignia" aria-hidden="true">{{ racha() }}</span>
        </button>
      </div>
    }
  `,
  styles: `
    :host {
      position: fixed;
      right: 12px;
      bottom: calc(5.4rem + env(safe-area-inset-bottom, 0px));
      z-index: 40;
    }
    .companero {
      position: relative;
      display: flex;
      flex-direction: column;
      align-items: flex-end;
      gap: 8px;
    }
    .boton {
      position: relative;
      display: block;
      border-radius: 20px;
      background: rgb(27 21 17 / 0.82);
      border: 1px solid rgb(212 175 55 / 0.35);
      padding: 6px 8px 0;
      line-height: 0;
      box-shadow: 0 6px 18px rgb(0 0 0 / 0.38);
      transition: transform 0.2s cubic-bezier(0.16, 1, 0.3, 1);
    }
    .boton:active {
      transform: scale(0.96);
    }
    .boton:focus-visible {
      outline: 2px solid #d4af37;
      outline-offset: 2px;
    }
    .insignia {
      position: absolute;
      top: -8px;
      left: -8px;
      min-width: 24px;
      height: 24px;
      padding: 0 6px;
      border-radius: 12px;
      background: #d4af37;
      color: #1b1511;
      font:
        700 14px/24px 'Barlow Condensed',
        'Barlow',
        sans-serif;
      text-align: center;
    }
    .actuando .boton {
      animation: entra 0.35s cubic-bezier(0.16, 1, 0.3, 1);
    }
    .frase {
      padding: 6px 12px;
      border-radius: 12px;
      background: #d4af37;
      color: #1b1511;
      font-weight: 700;
      font-size: 14px;
      box-shadow: 0 4px 12px rgb(0 0 0 / 0.3);
      animation: aparece 0.3s cubic-bezier(0.16, 1, 0.3, 1);
    }
    .panel {
      width: min(86vw, 17rem);
      padding: 14px 16px;
      border-radius: 18px;
      background: #1b1511;
      border: 1px solid rgb(212 175 55 / 0.4);
      box-shadow: 0 10px 28px rgb(0 0 0 / 0.5);
      animation: aparece 0.25s cubic-bezier(0.16, 1, 0.3, 1);
    }
    .numero {
      font:
        700 56px/0.9 'Barlow Condensed',
        'Barlow',
        sans-serif;
      color: #d4af37;
      font-variant-numeric: tabular-nums;
    }
    @keyframes aparece {
      from {
        opacity: 0;
        transform: translateY(8px);
      }
    }
    @keyframes entra {
      from {
        transform: scale(0.85);
      }
    }
    @media (prefers-reduced-motion: reduce) {
      .actuando .boton,
      .frase,
      .panel {
        animation: none;
      }
    }
  `,
})
export class Companero {
  protected celebraciones = inject(CelebracionesService);
  private router = inject(Router);
  protected abierto = signal(false);
  /** En la pestaña de Logros el guerrero grande ya está en pantalla: no se repite. */
  protected enLogros = signal(this.router.url.includes('seccion=logros'));

  constructor() {
    this.router.events
      .pipe(
        filter((e) => e instanceof NavigationEnd),
        takeUntilDestroyed(),
      )
      .subscribe((e) =>
        this.enLogros.set((e as NavigationEnd).urlAfterRedirects.includes('seccion=logros')),
      );
  }

  protected actuando = computed(() => this.celebraciones.accion() !== null);
  protected racha = computed(() => this.celebraciones.logros()?.racha.actual ?? 0);
  protected estado = computed(() => estadoDe(this.celebraciones.hoy(), this.umbral()));
  private umbral = computed(() => this.celebraciones.logros()?.racha.umbral ?? META_DEL_DIA);

  /** Qué falta hoy para que el día cuente: o que la racha de hoy ya está a salvo. */
  protected estadoDelDia = computed(() => {
    const hoy = this.celebraciones.hoy();
    const umbral = this.umbral();
    if (hoy === null) return 'Cuando empieces a anotar, el día cuenta.';
    if (hoy >= umbral) return `Hoy llevas ${hoy} %: la racha de hoy está a salvo.`;
    return `Hoy llevas ${hoy} %. Te faltan ${umbral - hoy} puntos para sostener tu racha.`;
  });
}
