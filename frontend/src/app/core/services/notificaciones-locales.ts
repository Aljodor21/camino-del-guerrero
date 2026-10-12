import { HttpClient } from '@angular/common/http';
import { Injectable, inject, signal } from '@angular/core';
import { LocalNotifications } from '@capacitor/local-notifications';
import { firstValueFrom } from 'rxjs';

import { environment } from '../../../environments/environment';

interface AvisoProximo {
  clave: string;
  tipo: string;
  titulo: string;
  cuerpo: string;
  programada_para: string;
}

export const CANAL_AVISOS = {
  id: 'avisos',
  name: 'Avisos',
  description: 'Agua, proteína, comidas, entreno y dormir',
  importance: 4 as const,
  visibility: 1 as const,
  vibration: true,
};
const DIAS = 7;
/** Cada cuánto como máximo se vuelve a programar (abrir la app varias veces seguidas no la recarga). */
const ENTRE_SINCRONIZACIONES_MS = 60_000;

/** Un número estable para cada aviso: así Android reemplaza el mismo en vez de repetirlo. */
function idDe(clave: string): number {
  let h = 0;
  for (let i = 0; i < clave.length; i++) h = (Math.imul(31, h) + clave.charCodeAt(i)) | 0;
  return Math.abs(h) % 2_000_000_000 || 1;
}

/**
 * Avisos programados en el propio celular: el servidor dice qué toca en los próximos días y Android
 * los hace sonar a su hora aunque la app esté cerrada y el servidor apagado. Es el respaldo de
 * Firebase (ver `NotificacionesCelularService`, que decide cuál de los dos se usa).
 */
@Injectable({ providedIn: 'root' })
export class NotificacionesLocalesService {
  private http = inject(HttpClient);

  /** Cuántos avisos quedaron programados la última vez. */
  readonly programados = signal(0);
  private ultima = 0;

  async permiso(): Promise<'granted' | 'denied' | 'prompt'> {
    const { display } = await LocalNotifications.checkPermissions();
    return display === 'granted' || display === 'denied' ? display : 'prompt';
  }

  async pedirPermiso(): Promise<boolean> {
    return (await LocalNotifications.requestPermissions()).display === 'granted';
  }

  /** Cancela lo programado y programa lo que viene en los próximos días. */
  async programar(forzar = false): Promise<void> {
    if (!forzar && Date.now() - this.ultima < ENTRE_SINCRONIZACIONES_MS) return;
    this.ultima = Date.now();
    try {
      const avisos = await firstValueFrom(
        this.http.get<AvisoProximo[]>(`${environment.apiUrl}/agenda/avisos/proximos/`, {
          params: { dias: DIAS },
        }),
      );
      await LocalNotifications.createChannel(CANAL_AVISOS);
      await this.cancelar();
      if (avisos.length) {
        await LocalNotifications.schedule({
          notifications: avisos.map((a) => ({
            id: idDe(a.clave),
            title: a.titulo,
            body: a.cuerpo,
            channelId: CANAL_AVISOS.id,
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

  async cancelar(): Promise<void> {
    const { notifications } = await LocalNotifications.getPending();
    if (notifications.length) await LocalNotifications.cancel({ notifications });
    this.programados.set(0);
    this.ultima = 0;
  }

  /** Al tocar una notificación programada: se abre la bandeja. */
  alTocar(accion: () => void): void {
    void LocalNotifications.addListener('localNotificationActionPerformed', accion).catch(
      () => undefined,
    );
  }
}
