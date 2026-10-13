import { Injectable, inject } from '@angular/core';
import { App } from '@capacitor/app';
import { Capacitor } from '@capacitor/core';

import { hoyISO } from '../../shared/fechas';
import { AuthService } from './auth';

/** Cada cuánto se mira si ya cambió el día mientras la app está abierta. */
const REVISION_MS = 30_000;
/** Si la app estuvo así de tiempo en segundo plano, lo que muestra ya está viejo. */
const FUERA_MAXIMO_MS = 10 * 60_000;

/**
 * Mantiene la app al día sin que la persona tenga que cerrarla y abrirla: cuando cambia el día
 * (a medianoche, con la app abierta o al volver a ella) o cuando se vuelve tras un buen rato, se
 * vuelve a cargar todo. Si en ese momento hay algo a medias (un campo con texto o una ventana
 * abierta), espera a que termine para no borrarle lo que escribe.
 */
@Injectable({ providedIn: 'root' })
export class RefrescoService {
  private auth = inject(AuthService);

  private fecha = hoyISO();
  private oculta: number | null = null;
  private pendiente = false;
  private iniciado = false;

  iniciar(): void {
    if (this.iniciado) return;
    this.iniciado = true;
    document.addEventListener('visibilitychange', () => {
      if (document.hidden) this.oculta = Date.now();
      else this.alVolver();
    });
    if (Capacitor.isNativePlatform()) {
      void App.addListener('resume', () => this.alVolver()).catch(() => undefined);
      void App.addListener('pause', () => (this.oculta = Date.now())).catch(() => undefined);
    }
    setInterval(() => {
      if (!document.hidden) this.revisar();
    }, REVISION_MS);
  }

  private alVolver(): void {
    const fuera = this.oculta === null ? 0 : Date.now() - this.oculta;
    this.oculta = null;
    if (fuera > FUERA_MAXIMO_MS) this.pendiente = true;
    this.revisar();
  }

  private revisar(): void {
    if (hoyISO() !== this.fecha) this.pendiente = true;
    if (!this.pendiente || !this.auth.isLoggedIn()) return;
    if (this.haciendoAlgo()) return;
    window.location.reload();
  }

  /** Hay un texto escrito, una ventana abierta o una subida en curso: no es buen momento. */
  private haciendoAlgo(): boolean {
    const activo = document.activeElement;
    if (activo instanceof HTMLTextAreaElement && activo.value.trim()) return true;
    if (
      activo instanceof HTMLInputElement &&
      activo.type !== 'checkbox' &&
      activo.type !== 'radio' &&
      activo.type !== 'button' &&
      activo.value.trim()
    )
      return true;
    return !!document.querySelector('[role="dialog"], .p-dialog');
  }
}
