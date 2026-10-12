import { ChangeDetectionStrategy, Component, input, signal } from '@angular/core';

export type DemoAyuda =
  | 'menu'
  | 'mercado'
  | 'plan'
  | 'avisos'
  | 'cumplimiento'
  | 'proyeccion'
  | 'proteina'
  | 'medidas'
  | 'agenda';

/**
 * Qué es esta pantalla y cómo se usa, con una animación corta que muestra qué hace.
 * Se abre sola la primera vez; después queda recogida y se vuelve a abrir con el botón.
 */
@Component({
  selector: 'app-ayuda',
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './ayuda.html',
  styleUrl: './ayuda.css',
})
export class Ayuda {
  /** Identifica esta ayuda para recordar si ya se vio. */
  readonly clave = input.required<string>();
  readonly titulo = input.required<string>();
  readonly para = input.required<string>();
  readonly pasos = input.required<string[]>();
  readonly demo = input.required<DemoAyuda>();

  protected abierta = signal(false);
  protected id = `ayuda-${Math.random().toString(36).slice(2, 8)}`;

  constructor() {
    queueMicrotask(() => {
      const visto = this.leer();
      this.abierta.set(!visto);
      if (!visto) this.guardar();
    });
  }

  protected alternar(): void {
    this.abierta.update((a) => !a);
  }

  private llave(): string {
    return `cdg_ayuda_${this.clave()}`;
  }

  private leer(): boolean {
    try {
      return localStorage.getItem(this.llave()) === '1';
    } catch {
      return false;
    }
  }

  private guardar(): void {
    try {
      localStorage.setItem(this.llave(), '1');
    } catch {
      /* sin almacenamiento: la ayuda vuelve a abrirse, no pasa nada */
    }
  }
}
