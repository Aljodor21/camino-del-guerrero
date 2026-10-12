import { Injectable, signal } from '@angular/core';

import { environment } from '../../../environments/environment';

/**
 * ¿El servidor responde? Un solo fallo puede ser un tropiezo; dos seguidos, y la app avisa con
 * claridad (sin internet, o el servidor no responde), reintenta sola y se recupera sin recargar.
 * El sondeo va con fetch y no con HttpClient: así no pasa por el interceptor que lo alimenta.
 */
@Injectable({ providedIn: 'root' })
export class ServidorService {
  readonly caido = signal(false);
  readonly sinInternet = signal(typeof navigator !== 'undefined' && !navigator.onLine);
  /** Un instante en verde ("Conexión recuperada") después de volver. */
  readonly recuperado = signal(false);
  readonly probando = signal(false);

  private fallos = 0;
  private temporizador: number | null = null;

  constructor() {
    window.addEventListener('offline', () => {
      this.sinInternet.set(true);
      this.marcarCaido();
    });
    window.addEventListener('online', () => {
      this.sinInternet.set(false);
      if (this.caido()) void this.probar();
    });
  }

  /** El interceptor avisa de cada respuesta de nuestra API (cualquier respuesta: el servidor vive). */
  reportarRespuesta(): void {
    this.fallos = 0;
    if (this.caido()) this.volvio();
  }

  /** Sin respuesta (0) o 502/503/504: no llegó al servidor, o el servidor no está. */
  reportarFallo(): void {
    this.fallos++;
    if (this.fallos >= 2) this.marcarCaido();
  }

  async probar(): Promise<void> {
    if (this.probando()) return;
    this.probando.set(true);
    try {
      const r = await fetch(`${environment.apiUrl}/app/version/`, {
        cache: 'no-store',
        signal: AbortSignal.timeout(6000),
      });
      if (r.status < 502) this.reportarRespuesta();
    } catch {
      /* sigue caído: se vuelve a intentar */
    } finally {
      this.probando.set(false);
    }
  }

  private marcarCaido(): void {
    if (this.caido()) return;
    this.caido.set(true);
    this.recuperado.set(false);
    this.temporizador = window.setInterval(() => void this.probar(), 8000);
  }

  private volvio(): void {
    this.caido.set(false);
    this.sinInternet.set(false);
    if (this.temporizador !== null) window.clearInterval(this.temporizador);
    this.temporizador = null;
    this.recuperado.set(true);
    window.setTimeout(() => this.recuperado.set(false), 3000);
  }
}
