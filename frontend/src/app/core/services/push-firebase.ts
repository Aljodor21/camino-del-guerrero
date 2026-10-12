import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Router } from '@angular/router';
import { PushNotifications } from '@capacitor/push-notifications';
import { firstValueFrom } from 'rxjs';

import { environment } from '../../../environments/environment';
import { AvisosService } from './avisos';
import { CANAL_AVISOS } from './notificaciones-locales';

const API = `${environment.apiUrl}/agenda/push/celular/`;
const ESPERA_TOKEN_MS = 15_000;

/**
 * Avisos por Firebase (FCM): el servidor se los entrega a Google y Google al celular, aunque la
 * app esté cerrada y sin límite de días. Aquí solo se registra este celular ante nuestro servidor
 * (con su "token") y se atiende lo que llega; los datos no pasan por Firebase.
 */
@Injectable({ providedIn: 'root' })
export class PushFirebaseService {
  private http = inject(HttpClient);
  private router = inject(Router);
  private avisos = inject(AvisosService);

  private token: string | null = null;
  private escuchando = false;
  private alRegistrar: ((token: string) => void) | null = null;

  /** El servidor ya tiene las credenciales de Firebase. */
  async disponible(): Promise<boolean> {
    try {
      return (await firstValueFrom(this.http.get<{ disponible: boolean }>(API))).disponible;
    } catch {
      return false;
    }
  }

  /** Registra este celular. true si quedó recibiendo por Firebase; false si hay que usar el respaldo. */
  async registrar(): Promise<boolean> {
    try {
      if (!(await this.disponible())) return false;
      this.escuchar();
      await PushNotifications.createChannel(CANAL_AVISOS);
      const recibido = new Promise<string>((ok, mal) => {
        this.alRegistrar = ok;
        setTimeout(() => mal(new Error('Firebase no respondió')), ESPERA_TOKEN_MS);
      });
      await PushNotifications.register();
      await this.guardarToken(await recibido);
      return true;
    } catch {
      return false;
    }
  }

  /** Al cerrar sesión: este celular deja de recibir los avisos de esa cuenta. */
  async quitar(): Promise<void> {
    const token = this.token;
    this.token = null;
    if (!token) return;
    await firstValueFrom(this.http.request('DELETE', API, { body: { token } })).catch(
      () => undefined,
    );
  }

  /** Una notificación de prueba a este celular; devuelve cuántos celulares la recibieron. */
  async probar(): Promise<number> {
    const r = await firstValueFrom(this.http.post<{ enviadas: number }>(`${API}probar/`, {}));
    return r.enviadas;
  }

  private async guardarToken(token: string): Promise<void> {
    this.token = token;
    await firstValueFrom(this.http.post<void>(API, { token }));
  }

  private escuchar(): void {
    if (this.escuchando) return;
    this.escuchando = true;
    // Firebase puede cambiar el token con los meses: cada vez que llega uno nuevo se vuelve a guardar.
    void PushNotifications.addListener('registration', (t) => {
      if (this.alRegistrar) {
        this.alRegistrar(t.value);
        this.alRegistrar = null;
      } else if (t.value !== this.token) {
        void this.guardarToken(t.value).catch(() => undefined);
      }
    }).catch(() => undefined);
    // Con la app abierta Android no muestra la notificación: se refresca la bandeja.
    void PushNotifications.addListener('pushNotificationReceived', () =>
      this.avisos.cargar().subscribe({ error: () => undefined }),
    ).catch(() => undefined);
    void PushNotifications.addListener('pushNotificationActionPerformed', (a) => {
      const ruta = String(a.notification.data?.['ruta'] ?? '/avisos');
      void this.router.navigateByUrl(ruta.startsWith('/') ? ruta : '/avisos');
    }).catch(() => undefined);
  }
}
