import { ChangeDetectionStrategy, Component, input } from '@angular/core';

/**
 * Cabecera de sección con foto, como un pedazo del home: la foto a lo ancho, oscurecida
 * abajo, y el título encima. Es baja para no quitarle espacio a la pantalla.
 */
@Component({
  selector: 'app-portada',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <picture>
      <source media="(max-width: 767px)" [attr.srcset]="'/home/' + foto() + '-movil.webp'" />
      <img [src]="'/home/' + foto() + '.webp'" alt="" decoding="async" />
    </picture>
    <div class="portada-texto">
      @if (antetitulo()) {
        <p class="antetitulo">{{ antetitulo() }}</p>
      }
      <h1>{{ titulo() }}</h1>
      @if (subtitulo()) {
        <p class="subtitulo">{{ subtitulo() }}</p>
      }
    </div>
    <div class="portada-acciones"><ng-content /></div>
  `,
  styles: `
    :host {
      position: relative;
      display: flex;
      align-items: flex-end;
      gap: 1rem;
      min-height: 9.5rem;
      padding: 1.1rem 1.25rem;
      border-radius: 1rem;
      overflow: hidden;
      isolation: isolate;
      color: #f6f1ea;
      background: #100d0b;
    }
    picture,
    img {
      position: absolute;
      inset: 0;
      width: 100%;
      height: 100%;
      z-index: -2;
    }
    img {
      object-fit: cover;
      object-position: var(--encuadre, 65% 40%);
      animation: entrar 1.6s cubic-bezier(0.16, 1, 0.3, 1) both;
    }
    :host::after {
      content: '';
      position: absolute;
      inset: 0;
      z-index: -1;
      background:
        linear-gradient(
          0deg,
          rgb(16 13 11 / 0.88) 0%,
          rgb(16 13 11 / 0.35) 55%,
          rgb(16 13 11 / 0.1) 100%
        ),
        linear-gradient(90deg, rgb(16 13 11 / 0.55) 0%, transparent 60%);
    }
    .portada-texto {
      flex: 1;
      min-width: 0;
    }
    h1 {
      margin: 0;
      font-family: var(--font-display);
      font-weight: 700;
      font-size: clamp(2.1rem, 3vw + 1.2rem, 2.9rem);
      line-height: 0.92;
      letter-spacing: -0.01em;
      text-wrap: balance;
    }
    .antetitulo {
      margin: 0 0 0.35rem;
      font-size: 0.8rem;
      letter-spacing: 0.06em;
      text-transform: uppercase;
      color: #d4af37;
    }
    .subtitulo {
      margin: 0.4rem 0 0;
      font-size: 0.95rem;
      color: rgb(246 241 234 / 0.78);
    }
    .portada-acciones {
      display: flex;
      gap: 0.5rem;
      flex-shrink: 0;
    }
    .portada-acciones:empty {
      display: none;
    }
    @keyframes entrar {
      from {
        transform: scale(1.08);
      }
      to {
        transform: none;
      }
    }
    @media (prefers-reduced-motion: reduce) {
      img {
        animation: none;
      }
    }
  `,
})
export class Portada {
  /** Nombre de la foto en /home/ (con su versión -movil). */
  readonly foto = input.required<string>();
  readonly titulo = input.required<string>();
  readonly subtitulo = input('');
  readonly antetitulo = input('');
}
