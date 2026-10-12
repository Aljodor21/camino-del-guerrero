import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  ElementRef,
  afterNextRender,
  inject,
  signal,
  viewChild,
} from '@angular/core';
import { RouterLink } from '@angular/router';

import { AuthService } from '../core/services/auth';

/**
 * 404: la animación a pantalla completa (el guerrero pasa por el poste que dice 404) y, por
 * encima, solo la barra de arriba y el pie, transparentes. Hay una versión horizontal y una
 * vertical, y se usa la que le queda a la pantalla. Con "reducir movimiento" se queda el cuadro
 * fijo.
 */
@Component({
  selector: 'app-no-encontrada',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [RouterLink],
  template: `
    @if (fuente(); as f) {
      <video
        #video
        class="fondo"
        autoplay
        muted
        loop
        playsinline
        preload="auto"
        aria-hidden="true"
        [src]="f.video"
        [poster]="f.cuadro"
      ></video>
    }
    <div class="velo" aria-hidden="true"></div>

    <header class="barra">
      <a routerLink="/" class="barra-logo" aria-label="Camino del Guerrero, inicio">
        <img src="/Logo oscuro-sf.png" alt="" width="160" height="48" />
      </a>
      <nav class="barra-acciones" aria-label="Cuenta">
        @if (auth.isLoggedIn()) {
          <a routerLink="/inicio" class="enlace">Mi camino</a>
        } @else {
          <a routerLink="/auth/login" class="enlace">Iniciar sesión</a>
        }
      </nav>
    </header>

    <main>
      <h1 class="sr-only">Página no encontrada (404). Te saliste del camino.</h1>
    </main>

    <footer class="pie">
      <img src="/Logo oscuro-sf.png" alt="Camino del Guerrero" width="120" height="36" />
      <nav aria-label="Navegación">
        <a routerLink="/">Volver al inicio</a>
        @if (auth.isLoggedIn()) {
          <a routerLink="/inicio">Mi camino</a>
        } @else {
          <a routerLink="/auth/login">Iniciar sesión</a>
          <a routerLink="/auth/registro">Crear cuenta</a>
        }
      </nav>
    </footer>
  `,
  styles: `
    :host {
      position: relative;
      display: block;
      min-height: 100svh;
      background: #100d0b;
      color: #f6f1ea;
      font-family: 'Barlow', 'Segoe UI', system-ui, sans-serif;
      isolation: isolate;
    }
    .fondo {
      position: fixed;
      inset: 0;
      z-index: -2;
      width: 100%;
      height: 100%;
      object-fit: cover;
      object-position: 62% 50%;
    }
    /* Solo para que la barra y el pie se lean sobre la escena; la imagen queda a la vista. */
    .velo {
      position: fixed;
      inset: 0;
      z-index: -1;
      pointer-events: none;
      background:
        linear-gradient(180deg, rgb(16 13 11 / 0.62) 0%, transparent 22%),
        linear-gradient(0deg, rgb(16 13 11 / 0.72) 0%, transparent 24%);
    }
    .barra {
      position: absolute;
      inset: 0 0 auto;
      z-index: 2;
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 26px 4.5%;
    }
    .barra-logo img {
      display: block;
      height: 3rem;
      width: auto;
    }
    .barra-acciones {
      display: flex;
      align-items: center;
      gap: 1.75rem;
    }
    .enlace,
    .pie a {
      color: #f6f1ea;
      text-decoration: none;
      font-weight: 500;
      font-size: 1.0625rem;
      text-shadow: 0 1px 8px rgb(16 13 11 / 0.6);
      transition: opacity 160ms;
    }
    .enlace {
      padding: 10px 0;
    }
    .enlace:hover,
    .pie a:hover {
      opacity: 0.72;
    }
    .barra-logo:focus-visible,
    .enlace:focus-visible,
    .pie a:focus-visible {
      outline: 3px solid currentColor;
      outline-offset: 5px;
    }
    main {
      min-height: 100svh;
    }
    .pie {
      position: absolute;
      inset: auto 0 0;
      z-index: 2;
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      justify-content: space-between;
      gap: 1rem 2rem;
      padding: 1.75rem 4.5%;
    }
    .pie img {
      height: 2.25rem;
      width: auto;
    }
    .pie nav {
      display: flex;
      flex-wrap: wrap;
      gap: 0.5rem 1.5rem;
    }
    .sr-only {
      position: absolute;
      width: 1px;
      height: 1px;
      margin: -1px;
      padding: 0;
      overflow: hidden;
      clip: rect(0, 0, 0, 0);
      white-space: nowrap;
      border: 0;
    }

    @media (orientation: portrait) {
      .fondo {
        object-position: 50% 50%;
      }
      .barra {
        padding: 22px 20px;
      }
      .barra-logo img {
        height: 2.5rem;
      }
      .pie {
        padding: 1.5rem 20px;
      }
    }
  `,
})
export class NoEncontrada {
  protected auth = inject(AuthService);
  private destroyRef = inject(DestroyRef);
  private video = viewChild<ElementRef<HTMLVideoElement>>('video');

  /** Qué video y qué cuadro fijo se usan; hasta saber la pantalla no se carga ninguno. */
  protected fuente = signal<{ video: string; cuadro: string } | null>(null);

  constructor() {
    afterNextRender(() => {
      const vertical = matchMedia('(orientation: portrait)');
      const elegir = () =>
        this.fuente.set(
          vertical.matches
            ? { video: '/home/404-movil.mp4', cuadro: '/home/404-movil-poster.webp' }
            : { video: '/home/404.mp4', cuadro: '/home/404-poster.webp' },
        );
      elegir();
      vertical.addEventListener('change', elegir);
      this.destroyRef.onDestroy(() => vertical.removeEventListener('change', elegir));

      // Con "reducir movimiento" se queda el cuadro fijo, sin reproducir.
      if (matchMedia('(prefers-reduced-motion: reduce)').matches) {
        setTimeout(() => {
          const v = this.video()?.nativeElement;
          v?.removeAttribute('autoplay');
          v?.pause();
        });
      }
    });
  }
}
