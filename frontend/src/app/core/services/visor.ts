import { Injectable, signal } from '@angular/core';
import { Observable } from 'rxjs';

export interface ContenidoVisor {
  titulo: string;
  tipo: 'imagen' | 'pdf';
  url: string;
}

/**
 * Para ver una foto o un PDF dentro de la app, en una ventana, sin salir a otra pestaña.
 * Se pide con el archivo (privado, llega con el token) o con una URL local que ya se tiene.
 */
@Injectable({ providedIn: 'root' })
export class VisorService {
  private _contenido = signal<ContenidoVisor | null>(null);
  private _cargando = signal(false);
  private _error = signal('');
  private propia = false;

  readonly contenido = this._contenido.asReadonly();
  readonly cargando = this._cargando.asReadonly();
  readonly error = this._error.asReadonly();
  readonly abierto = () => this._cargando() || this._contenido() !== null || !!this._error();

  /** Un archivo privado: se descarga y se muestra. */
  abrir(titulo: string, archivo: Observable<Blob>): void {
    this.cerrar();
    this._cargando.set(true);
    archivo.subscribe({
      next: (blob) => {
        this.propia = true;
        this._contenido.set({
          titulo,
          tipo: blob.type === 'application/pdf' ? 'pdf' : 'imagen',
          url: URL.createObjectURL(blob),
        });
        this._cargando.set(false);
      },
      error: () => {
        this._error.set('No pudimos abrir el archivo.');
        this._cargando.set(false);
      },
    });
  }

  /** Una imagen que la pantalla ya tiene (URL local): se muestra tal cual y no se libera aquí. */
  abrirUrl(titulo: string, url: string): void {
    this.cerrar();
    this.propia = false;
    this._contenido.set({ titulo, tipo: 'imagen', url });
  }

  cerrar(): void {
    const c = this._contenido();
    if (c && this.propia) URL.revokeObjectURL(c.url);
    this.propia = false;
    this._contenido.set(null);
    this._cargando.set(false);
    this._error.set('');
  }
}
