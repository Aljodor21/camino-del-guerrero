import { Injectable, inject, signal } from '@angular/core';
import { Capacitor } from '@capacitor/core';
import { firstValueFrom } from 'rxjs';

import { AvisosService } from './avisos';

export type EstadoPush = 'no-soportado' | 'sin-servidor' | 'denegado' | 'inactivo' | 'activo';

function aBytes(base64: string): Uint8Array<ArrayBuffer> {
  const relleno = '='.repeat((4 - (base64.length % 4)) % 4);
  const crudo = atob((base64 + relleno).replace(/-/g, '+').replace(/_/g, '/'));
  return Uint8Array.from(crudo, (c) => c.charCodeAt(0));
}

/** Notificaciones al celular: registra el service worker y suscribe este navegador. */
@Injectable({ providedIn: 'root' })
export class PushService {
  private avisos = inject(AvisosService);
  private _estado = signal<EstadoPush>('inactivo');
  private clave: string | null = null;
  readonly estado = this._estado.asReadonly();

  private get soportado(): boolean {
    // En la app instalada el web push no existe: ahí los avisos viven dentro de la app.
    if (Capacitor.isNativePlatform()) return false;
    return 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window;
  }

  /** Mira cómo está este navegador y, si ya aceptó antes, deja la suscripción al día. */
  async iniciar(): Promise<void> {
    if (!this.soportado) return this._estado.set('no-soportado');
    try {
      const { clave } = await firstValueFrom(this.avisos.llavePush());
      if (!clave) return this._estado.set('sin-servidor');
      this.clave = clave;
      const registro = await navigator.serviceWorker.register('/sw.js');
      if (Notification.permission === 'denied') return this._estado.set('denegado');
      const actual = await registro.pushManager.getSubscription();
      if (actual && Notification.permission === 'granted') {
        await firstValueFrom(this.avisos.suscribirPush(actual.toJSON()));
        return this._estado.set('activo');
      }
      this._estado.set('inactivo');
    } catch {
      this._estado.set('inactivo');
    }
  }

  /** Pide permiso y suscribe. Debe llamarse desde un toque del usuario. */
  async activar(): Promise<void> {
    if (!this.soportado || !this.clave) return;
    const permiso = await Notification.requestPermission();
    if (permiso !== 'granted') return this._estado.set('denegado');
    const registro = await navigator.serviceWorker.ready;
    const suscripcion =
      (await registro.pushManager.getSubscription()) ??
      (await registro.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: aBytes(this.clave),
      }));
    await firstValueFrom(this.avisos.suscribirPush(suscripcion.toJSON()));
    this._estado.set('activo');
  }

  async desactivar(): Promise<void> {
    const registro = await navigator.serviceWorker.ready;
    const suscripcion = await registro.pushManager.getSubscription();
    if (suscripcion) {
      await firstValueFrom(this.avisos.desuscribirPush(suscripcion.endpoint)).catch(
        () => undefined,
      );
      await suscripcion.unsubscribe();
    }
    this._estado.set('inactivo');
  }
}
