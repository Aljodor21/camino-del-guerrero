import { HttpClient } from '@angular/common/http';
import { Injectable, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import { App } from '@capacitor/app';
import { Capacitor } from '@capacitor/core';
import { LocalNotifications } from '@capacitor/local-notifications';
import { firstValueFrom } from 'rxjs';

import { environment } from '../../../environments/environment';

export type EstadoLocales = 'no-soportado' | 'inactivo' | 'denegado' | 'activo';

interface AvisoProximo {
  clave: string;
  tipo: string;
  titulo: string;
  cuerpo: string;
  programada_para: string;
}

const CANAL = 'avisos';
const DIAS = 7;
/** Cada cuánto como máximo se vuelve a programar (abrir la app varias veces seguidas no la recarga). */
const ENTRE_SINCRONIZACIONES_MS = 60_000;
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

/** Un número estable para cada aviso: así Android reemplaza el mismo en vez de repetirlo. */
function idDe(clave: string): number {
  let h = 0;
  for (let i = 0; i < clave.length; i++) h = (Math.imul(31, h) + clave.charCodeAt(i)) | 0;
  return Math.abs(h) % 2_000_000_000 || 1;
}

/**
 * Los avisos en el celular, con la app instalada. El servidor dice qué toca en los próximos días y
 * el propio celular los programa: suenan a su hora aunque la app esté cerrada, sin depender de que
 * el servidor esté encendido ni de una cuenta de terceros. Se vuelve a programar cada vez que se
 * abre la app (y al cambiar los ajustes), así que si pasan muchos días sin abrirla se acaban.
 * El web push solo existe en el navegador, no en la app (ver `PushService`).
 */
@Injectable({ providedIn: 'root' })
export class NotificacionesLocalesService {
  private http = inject(HttpClient);
  private router = inject(Router);

  readonly soportado = Capacitor.isNativePlatform();
  private _estado = signal<EstadoLocales>(this.soportado ? 'inactivo' : 'no-soportado');
  readonly estado = this._estado.asReadonly();
  /** Cuántos avisos quedaron programados la última vez. */
  readonly programados = signal(0);

  private iniciado = false;
  private ultima = 0;

  /** Revisa el permiso y deja los avisos al día. Seguro de llamar más de una vez. */
  async iniciar(): Promise<void> {
    if (!this.soportado) return;
    try {
      if (!this.iniciado) {
        this.iniciado = true;
        // Los oyentes no se esperan: que se registren o no no debe frenar el resto.
        void LocalNotifications.addListener('localNotificationActionPerformed', () =>
          this.router.navigateByUrl('/avisos'),
        ).catch(() => undefined);
        void App.addListener('resume', () => void this.sincronizar()).catch(() => undefined);
      }
      await this.revisarPermiso();
      await this.sincronizar();
    } catch {
      // Si el celular no tiene el componente de notificaciones, la app sigue como antes.
      this._estado.set('no-soportado');
    }
  }

  /** Pide el permiso (debe salir de un toque de la persona) y programa los avisos. */
  async activar(): Promise<void> {
    if (!this.soportado) return;
    guardar(APAGADAS, null);
    const { display } = await LocalNotifications.requestPermissions();
    this._estado.set(display === 'granted' ? 'activo' : 'denegado');
    await this.sincronizar(true);
  }

  async desactivar(): Promise<void> {
    if (!this.soportado) return;
    guardar(APAGADAS, '1');
    await this.cancelarTodo();
    this.programados.set(0);
    this._estado.set('inactivo');
  }

  /** Al cerrar sesión: lo programado era de esa persona, no debe sonar para nadie más. */
  async limpiar(): Promise<void> {
    if (!this.soportado) return;
    this.ultima = 0;
    this.programados.set(0);
    this._estado.set('inactivo');
    await this.cancelarTodo().catch(() => undefined);
  }

  /** Cancela lo programado y programa lo que viene en los próximos días. */
  async sincronizar(forzar = false): Promise<void> {
    if (!this.soportado || this._estado() !== 'activo') return;
    if (!forzar && Date.now() - this.ultima < ENTRE_SINCRONIZACIONES_MS) return;
    this.ultima = Date.now();
    try {
      const avisos = await firstValueFrom(
        this.http.get<AvisoProximo[]>(`${environment.apiUrl}/agenda/avisos/proximos/`, {
          params: { dias: DIAS },
        }),
      );
      await LocalNotifications.createChannel({
        id: CANAL,
        name: 'Avisos',
        description: 'Agua, proteína, comidas, entreno y dormir',
        importance: 4,
        visibility: 1,
        vibration: true,
      });
      await this.cancelarTodo();
      if (avisos.length) {
        await LocalNotifications.schedule({
          notifications: avisos.map((a) => ({
            id: idDe(a.clave),
            title: a.titulo,
            body: a.cuerpo,
            channelId: CANAL,
            schedule: { at: new Date(a.programada_para), allowWhileIdle: true },
            extra: { tipo: a.tipo },
          })),
        });
      }
      this.programados.set(avisos.length);
    } catch {
      // Sin conexión no se toca lo ya programado: sigue sonando lo de antes.
    }
  }

  private async revisarPermiso(): Promise<void> {
    const { display } = await LocalNotifications.checkPermissions();
    if (display === 'denied') this._estado.set('denegado');
    else if (display === 'granted' && !leer(APAGADAS)) this._estado.set('activo');
    else this._estado.set('inactivo');
  }

  private async cancelarTodo(): Promise<void> {
    const { notifications } = await LocalNotifications.getPending();
    if (notifications.length) await LocalNotifications.cancel({ notifications });
  }
}
