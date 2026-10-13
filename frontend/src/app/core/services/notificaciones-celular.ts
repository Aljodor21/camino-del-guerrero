import { Injectable, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import { App } from '@capacitor/app';
import { Capacitor } from '@capacitor/core';

import { NotificacionesLocalesService } from './notificaciones-locales';
import { PushFirebaseService } from './push-firebase';

export type EstadoCelular = 'no-soportado' | 'inactivo' | 'denegado' | 'activo';
/** Por dónde llegan los avisos: Firebase (el servidor los manda) o programados en el celular (respaldo). */
export type ModoCelular = 'firebase' | 'local' | null;

const APAGADAS = 'cdg_avisos_celular_apagados';

function leer(clave: string): string | null {
  try {
    return localStorage.getItem(clave);
  } catch {
    return null;
  }
}

function guardar(clave: string, valor: string | null): void {
  try {
    if (valor === null) localStorage.removeItem(clave);
    else localStorage.setItem(clave, valor);
  } catch {
    // Sin almacenamiento solo se pierde recordar que la persona los apagó.
  }
}

/**
 * Los avisos en la app instalada. Prefiere Firebase (el servidor manda cada aviso a su hora, sin
 * límite de días) y, si no se puede (el servidor sin Firebase, un celular sin servicios de Google o
 * sin conexión al activar), deja los avisos de los próximos 7 días programados en el celular.
 * El web push solo existe en el navegador (ver `PushService`).
 */
@Injectable({ providedIn: 'root' })
export class NotificacionesCelularService {
  private locales = inject(NotificacionesLocalesService);
  private firebase = inject(PushFirebaseService);
  private router = inject(Router);

  readonly soportado = Capacitor.isNativePlatform();
  private _estado = signal<EstadoCelular>(this.soportado ? 'inactivo' : 'no-soportado');
  private _modo = signal<ModoCelular>(null);
  readonly estado = this._estado.asReadonly();
  readonly modo = this._modo.asReadonly();
  readonly programados = this.locales.programados;
  private iniciado = false;

  /** Revisa el permiso y deja todo al día. Seguro de llamar más de una vez. */
  async iniciar(): Promise<void> {
    if (!this.soportado) return;
    try {
      if (!this.iniciado) {
        this.iniciado = true;
        this.locales.alTocar(() => void this.router.navigateByUrl('/avisos'));
        void App.addListener('resume', () => void this.actualizar()).catch(() => undefined);
        // Tocar una notificación abre la app en su pantalla (con la app abierta o cerrada).
        void App.addListener('appUrlOpen', (e) => this.abrir(e.url)).catch(() => undefined);
        void App.getLaunchUrl().then(
          (l) => l && this.abrir(l.url),
          () => undefined,
        );
      }
      const permiso = await this.locales.permiso();
      if (permiso === 'denied') return this._estado.set('denegado');
      if (permiso !== 'granted' || leer(APAGADAS)) return this._estado.set('inactivo');
      await this.prender();
    } catch {
      // Si el celular no tiene el componente de notificaciones, la app sigue como antes.
      this._estado.set('no-soportado');
    }
  }

  /** Pide el permiso (debe salir de un toque de la persona) y activa los avisos. */
  async activar(): Promise<void> {
    if (!this.soportado) return;
    guardar(APAGADAS, null);
    if (!(await this.locales.pedirPermiso())) return this._estado.set('denegado');
    await this.prender();
  }

  async desactivar(): Promise<void> {
    if (!this.soportado) return;
    guardar(APAGADAS, '1');
    await this.firebase.quitar();
    await this.locales.cancelar().catch(() => undefined);
    this._modo.set(null);
    this._estado.set('inactivo');
  }

  /** Al cambiar los ajustes de avisos: con el respaldo local hay que volver a programarlos. */
  async actualizar(): Promise<void> {
    if (this._estado() === 'activo' && this._modo() === 'local') await this.locales.programar(true);
  }

  /** Una notificación de prueba por Firebase; devuelve cuántos celulares la recibieron. */
  async probar(): Promise<number> {
    return this.firebase.probar();
  }

  /** Al cerrar sesión: lo registrado y programado era de esa persona, no debe llegarle a nadie más. */
  async limpiar(): Promise<void> {
    if (!this.soportado) return;
    await this.firebase.quitar();
    await this.locales.cancelar().catch(() => undefined);
    this._modo.set(null);
    this._estado.set('inactivo');
  }

  /** La pantalla a la que lleva una notificación: solo rutas de la propia app. */
  private abrir(url: string): void {
    try {
      const { pathname, search } = new URL(url);
      if (pathname.startsWith('/') && pathname !== '/')
        void this.router.navigateByUrl(pathname + search);
    } catch {
      // Una dirección que no es de la app no se abre.
    }
  }

  private async prender(): Promise<void> {
    this._estado.set('activo');
    if (await this.firebase.registrar()) {
      // Firebase cubre todo: lo programado en el celular sobraría y sonaría repetido.
      await this.locales.cancelar().catch(() => undefined);
      this._modo.set('firebase');
    } else {
      this._modo.set('local');
      await this.locales.programar();
    }
  }
}
