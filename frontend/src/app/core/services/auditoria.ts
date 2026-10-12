import { HttpClient } from '@angular/common/http';
import { Injectable, effect, inject, signal } from '@angular/core';
import { NavigationEnd, Router } from '@angular/router';
import { App } from '@capacitor/app';
import { Capacitor } from '@capacitor/core';
import { filter } from 'rxjs';

import { environment } from '../../../environments/environment';
import { AuthService } from './auth';

/**
 * Le dice al servidor desde dónde se usa la app (instalada o navegador, y su versión) y qué
 * pantalla abre la persona. No manda lo que escribe ni lo que ve: solo la ruta.
 */
@Injectable({ providedIn: 'root' })
export class AuditoriaService {
  private http = inject(HttpClient);
  private router = inject(Router);
  private auth = inject(AuthService);

  /** 'app' si es la app instalada; 'web' si es el navegador. */
  readonly cliente = Capacitor.isNativePlatform() ? 'app' : 'web';
  /** La versión con la que se instaló la app; vacía en el navegador. */
  readonly version = signal('');

  constructor() {
    if (this.cliente === 'app') {
      App.getInfo().then(
        (info) => this.version.set(info.version),
        () => undefined,
      );
    }
    this.router.events
      .pipe(filter((e): e is NavigationEnd => e instanceof NavigationEnd))
      .subscribe((e) => this.pantalla(e.urlAfterRedirects));
    // Al iniciar sesión (o abrir la app con la sesión ya puesta) se anota la pantalla actual.
    effect(() => {
      if (this.auth.isLoggedIn()) this.pantalla(this.router.url);
      else this.ultimaRuta = '';
    });
  }

  private ultimaRuta = '';

  private pantalla(url: string): void {
    const ruta = url.split(/[?#]/)[0];
    if (!this.auth.isLoggedIn() || !ruta.startsWith('/') || ruta.startsWith('/auth')) return;
    // Cambiar de pestaña (?seccion=) o iniciar sesión no es abrir otra pantalla.
    if (ruta === this.ultimaRuta) return;
    this.ultimaRuta = ruta;
    this.http.post(`${environment.apiUrl}/auditoria/pantalla/`, { ruta }).subscribe({
      error: () => undefined,
    });
  }
}
