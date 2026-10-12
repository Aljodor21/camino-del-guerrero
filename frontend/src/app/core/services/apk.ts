import { Injectable, computed, signal } from '@angular/core';
import { Capacitor } from '@capacitor/core';

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
   * Pregunta a GitHub por el último release. Va con fetch y no con HttpClient a propósito:
   * el interceptor del JWT le pondría el token de la sesión a cualquier petición.
   */
  async cargar(forzar = false): Promise<void> {
    if (this.enLaApp || (this.pedida && !forzar)) return;
    this.pedida = true;
    this.estado.set('cargando');
    try {
      const r = await fetch(`https://api.github.com/repos/${REPO}/releases/latest`, {
        headers: { Accept: 'application/vnd.github+json' },
        signal: AbortSignal.timeout(8000),
      });
      if (!r.ok) throw new Error(String(r.status));
      const json = (await r.json()) as {
        tag_name: string;
        published_at: string;
        assets: { name: string; size: number }[];
      };
      const apk = json.assets.find((a) => a.name === ARCHIVO);
      if (!apk) throw new Error('sin apk');
      this.version.set({
        version: json.tag_name.replace(/^v/, ''),
        publicada: new Date(json.published_at),
        bytes: apk.size,
      });
      this.estado.set('lista');
    } catch {
      this.version.set(null);
      this.estado.set('no-disponible');
    }
  }
}
