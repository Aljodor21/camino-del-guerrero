import { Injectable, signal, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';

import { AuthService } from './auth';
import { environment } from '../../../environments/environment';

const API = environment.apiUrl;
const DISMISS_KEY = 'cdg_peso_reminder_dismissed';

@Injectable({ providedIn: 'root' })
export class NotificacionService {
  private http = inject(HttpClient);
  private auth = inject(AuthService);

  private _recordatorioPeso = signal(false);
  readonly recordatorioPeso = this._recordatorioPeso.asReadonly();

  verificar(): void {
    const usuario = this.auth.usuario();
    if (!usuario || this.auth.isAdmin()) return;

    const dismissedDate = localStorage.getItem(DISMISS_KEY);
    if (dismissedDate === new Date().toDateString()) return;

    const frecuencia = usuario.frecuencia_peso ?? 30;

    this.http.get<{ fecha: string }[]>(`${API}/progreso/mediciones/`).subscribe({
      next: (records) => {
        if (!records.length) {
          this._recordatorioPeso.set(true);
          return;
        }
        const ultima = new Date(records[0].fecha + 'T00:00:00');
        const dias = Math.floor((Date.now() - ultima.getTime()) / (1000 * 60 * 60 * 24));
        this._recordatorioPeso.set(dias >= frecuencia);
      },
      error: () => {},
    });
  }

  dismiss(): void {
    localStorage.setItem(DISMISS_KEY, new Date().toDateString());
    this._recordatorioPeso.set(false);
  }
}
