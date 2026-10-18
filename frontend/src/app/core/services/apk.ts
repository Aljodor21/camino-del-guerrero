import { HttpClient } from '@angular/common/http';
import { Injectable, computed, inject, signal } from '@angular/core';
import { App } from '@capacitor/app';
import { Capacitor } from '@capacitor/core';
import { firstValueFrom } from 'rxjs';

import { environment } from '../../../environments/environment';

/**
 * Siempre baja el APK de la última versión: no hay que actualizarlo al sacar versiones. Sale de
 * nuestro propio dominio (el servidor guarda una copia) y no de GitHub: así el celular lo descarga
 * en el acto, sin saltar a otra página.
 */
export const APK_URL = `${environment.apiUrl}/app/descargar/`;

export interface VersionApk {
  version: string;
  publicada: Date;
  bytes: number;
}

export type EstadoApk = 'cargando' | 'lista' | 'no-disponible';
export type Plataforma = 'android' | 'ios' | 'otra';
/** Dentro de la app instalada: ¿es la última versión? (null = no se sabe) */
export type Actualizacion = 'actual' | 'atrasada' | null;

const CLAVE_INVITACION = 'cdg_apk_invitacion';
const CLAVE_ACTUALIZACION = 'cdg_apk_actualizacion';
/** Cada cuánto vuelve a preguntar si hay versión nueva mientras la app sigue abierta. */
const MINUTOS_REVISION = 10;

/** Compara "1.0.5" con "1.0.12" número a número: negativo si a es más vieja, 0 si iguales. */
export function compararVersiones(a: string, b: string): number {
  const pa = a.split('.').map((n) => parseInt(n, 10) || 0);
  const pb = b.split('.').map((n) => parseInt(n, 10) || 0);
  for (let i = 0; i < Math.max(pa.length, pb.length); i++) {
    const d = (pa[i] ?? 0) - (pb[i] ?? 0);
    if (d !== 0) return d;
  }
  return 0;
}

function actualizacionDescartada(): string | null {
  try {
    return localStorage.getItem(CLAVE_ACTUALIZACION);
  } catch {
    return null;
  }
}

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
  /** La versión de la app instalada ("1.0.5"); solo se conoce dentro de la app. */
  readonly instalada = signal<string | null>(null);
  private cerrada = signal(invitacionYaCerrada());
  private descartada = signal(actualizacionDescartada());
  private pedida = false;
  private vigilando = false;
  private http = inject(HttpClient);

  /** El aviso de arriba solo sale donde se puede instalar y mientras no se haya cerrado. */
  readonly invitacion = computed(
    () =>
      !this.enLaApp && this.plataforma !== 'ios' && this.estado() === 'lista' && !this.cerrada(),
  );

  /** ¿La app instalada es la última? Solo se sabe dentro de la app y con la versión a la mano. */
  readonly actualizacion = computed((): Actualizacion => {
    const mia = this.instalada();
    const ultima = this.version()?.version;
    if (!this.enLaApp || !mia || !ultima) return null;
    return compararVersiones(mia, ultima) >= 0 ? 'actual' : 'atrasada';
  });

  /** El aviso de "hay una versión nueva": una vez cerrado no vuelve hasta que salga otra. */
  readonly avisoActualizacion = computed(
    () => this.actualizacion() === 'atrasada' && this.descartada() !== this.version()?.version,
  );

  descartarActualizacion(): void {
    const v = this.version()?.version ?? null;
    this.descartada.set(v);
    try {
      if (v) localStorage.setItem(CLAVE_ACTUALIZACION, v);
    } catch {
      /* sin almacenamiento: vuelve a salir en la próxima visita */
    }
  }

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
    // Al revisar de nuevo no se vuelve a "cargando": la pantalla no parpadea.
    if (!forzar) this.estado.set('cargando');
    void this.leerInstalada();
    this.vigilar();
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
      const nueva =
        r.disponible && r.version && r.publicada && r.bytes
          ? { version: r.version, publicada: new Date(r.publicada), bytes: r.bytes }
          : null;
      // Una revisión sin datos no borra la versión que ya se conocía.
      if (nueva || !forzar) this.version.set(nueva);
    } catch {
      if (!forzar) this.version.set(null);
    }
    // Sin datos (servidor o GitHub sin responder) el enlace sigue sirviendo: se ofrece igual.
    this.estado.set('lista');
  }

  /**
   * La app suele quedar abierta días en segundo plano: sin esto solo sabría de una versión nueva al
   * cerrarla y abrirla de nuevo. Se vuelve a preguntar al regresar a ella y cada pocos minutos.
   */
  private vigilar(): void {
    if (!this.enLaApp || this.vigilando) return;
    this.vigilando = true;
    void App.addListener('appStateChange', ({ isActive }) => {
      if (isActive) void this.cargar(true);
    });
    setInterval(() => void this.cargar(true), MINUTOS_REVISION * 60_000);
  }

  /** La versión con la que se instaló la app (la lee el propio Android). */
  private async leerInstalada(): Promise<void> {
    if (!this.enLaApp) return;
    try {
      this.instalada.set((await App.getInfo()).version);
    } catch {
      this.instalada.set(null);
    }
  }
}
