import { HttpClient } from '@angular/common/http';
import { Injectable, computed, inject, signal } from '@angular/core';
import { Capacitor } from '@capacitor/core';
import { firstValueFrom } from 'rxjs';

import { environment } from '../../../environments/environment';

const REPO = 'Aljodor21/camino-del-guerrero';
const ARCHIVO = 'camino-del-guerrero.apk';

/** Siempre apunta al APK del último release: no hay que actualizarlo al sacar versiones. */
export const APK_URL = `https://github.com/${REPO}/releases/latest/download/${ARCHIVO}`;

export interface VersionApk {
  version: string;
  publicada: Date;
  bytes: number;
}

export type EstadoApk = 'cargando' | 'lista' | 'no-disponible';
export type Plataforma = 'android' | 'ios' | 'otra';

const CLAVE_INVITACION = 'cdg_apk_invitacion';

function detectarPlataforma(): Plataforma {
  const ua = navigator.userAgent;
  if (/android/i.test(ua)) return 'android';
  if (/iphone|ipad|ipod/i.test(ua)) return 'ios';
  return 'otra';
}

function invitacionYaCerrada(): boolean {
  try {
    return localStorage.getItem(CLAVE_INVITACION) === '1';
  } catch {
    return false;
  }
}

/** La última versión de la app de Android (se lee del release de GitHub). */
@Injectable({ providedIn: 'root' })
export class ApkService {
  /** Dentro de la app instalada no tiene sentido ofrecerla. */
  readonly enLaApp = Capacitor.isNativePlatform();
  readonly plataforma = detectarPlataforma();
  readonly estado = signal<EstadoApk>('cargando');
  readonly version = signal<VersionApk | null>(null);
  private cerrada = signal(invitacionYaCerrada());
  private pedida = false;
  private http = inject(HttpClient);

  /** El aviso de arriba solo sale donde se puede instalar y mientras no se haya cerrado. */
  readonly invitacion = computed(
    () =>
      !this.enLaApp && this.plataforma !== 'ios' && this.estado() === 'lista' && !this.cerrada(),
  );

  cerrarInvitacion(): void {
    this.cerrada.set(true);
    try {
      localStorage.setItem(CLAVE_INVITACION, '1');
    } catch {
      /* sin almacenamiento: se muestra de nuevo en la próxima visita */
    }
  }

  /**
   * Pide la última versión a nuestro servidor, que a su vez la lee de GitHub. No se le pregunta a
   * GitHub desde el navegador: Cloudflare le pone al sitio una regla (`connect-src 'self'`) que lo
   * prohíbe. Si no hay datos pero sí enlace, el botón de descarga se muestra igual, sin versión.
   */
  async cargar(forzar = false): Promise<void> {
    if (this.pedida && !forzar) return;
    this.pedida = true;
    this.estado.set('cargando');
    try {
      const r = await firstValueFrom(
        this.http.get<{
          disponible: boolean | null;
          version?: string;
          publicada?: string;
          bytes?: number;
        }>(`${environment.apiUrl}/app/version/`),
      );
      if (r.disponible === false) {
        this.version.set(null);
        this.estado.set('no-disponible');
        return;
      }
      this.version.set(
        r.disponible && r.version && r.publicada && r.bytes
          ? { version: r.version, publicada: new Date(r.publicada), bytes: r.bytes }
          : null,
      );
    } catch {
      this.version.set(null);
    }
    // Sin datos (servidor o GitHub sin responder) el enlace sigue sirviendo: se ofrece igual.
    this.estado.set('lista');
  }
}
