import { Injectable, computed, inject, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { tap } from 'rxjs/operators';

import { Aviso, Habitos, HabitosPayload, ResumenHoy } from '../models/avisos.model';
import { environment } from '../../../environments/environment';

const API = `${environment.apiUrl}/agenda`;
/** Cada cuánto se revisa si llegó un aviso con la app abierta. */
const REVISION_MS = 60_000;

/** Bandeja de avisos, resumen del día y hábitos (agua, dormir). */
@Injectable({ providedIn: 'root' })
export class AvisosService {
  private http = inject(HttpClient);

  private _avisos = signal<Aviso[]>([]);
  private _hoy = signal<ResumenHoy | null>(null);
  private _habitos = signal<Habitos | null>(null);
  private temporizador: ReturnType<typeof setInterval> | null = null;

  readonly avisos = this._avisos.asReadonly();
  readonly hoy = this._hoy.asReadonly();
  readonly habitos = this._habitos.asReadonly();
  readonly pendientes = computed(() => this._avisos().length);

  cargar(): Observable<Aviso[]> {
    return this.http.get<Aviso[]>(`${API}/avisos/`).pipe(tap((a) => this._avisos.set(a)));
  }

  cargarHoy(): Observable<ResumenHoy> {
    return this.http.get<ResumenHoy>(`${API}/hoy/`).pipe(tap((h) => this._hoy.set(h)));
  }

  cargarHabitos(): Observable<Habitos> {
    return this.http.get<Habitos>(`${API}/habitos/`).pipe(tap((h) => this._habitos.set(h)));
  }

  guardarHabitos(cambios: HabitosPayload): Observable<Habitos> {
    return this.http
      .patch<Habitos>(`${API}/habitos/`, cambios)
      .pipe(tap((h) => this._habitos.set(h)));
  }

  /** Confirma lo que pide el aviso: el servidor guarda el dato y lo saca de la bandeja. */
  confirmar(aviso: Aviso): Observable<void> {
    return this.http
      .post<void>(`${API}/avisos/${aviso.id}/confirmar/`, {})
      .pipe(tap(() => this._avisos.update((lista) => lista.filter((a) => a.id !== aviso.id))));
  }

  /** Un vaso anotado a mano; devuelve cuántos ml fueron y la hora exacta en que se anotó. */
  registrarAgua(): Observable<{ momento: string; ml: number }> {
    return this.http.post<{ momento: string; ml: number }>(`${API}/registros/agua/`, {});
  }

  /** Revisa los avisos mientras la app está abierta y se detiene con `detener`. */
  iniciar(): void {
    if (this.temporizador) return;
    this.cargar().subscribe({ error: () => undefined });
    this.temporizador = setInterval(() => {
      if (!document.hidden) this.cargar().subscribe({ error: () => undefined });
    }, REVISION_MS);
  }

  detener(): void {
    if (this.temporizador) clearInterval(this.temporizador);
    this.temporizador = null;
    this._avisos.set([]);
    this._hoy.set(null);
    this._habitos.set(null);
  }

  // ── Notificaciones al celular ─────────────────────────────────────
  /** La llave pública del servidor; null si no manda al celular. */
  llavePush(): Observable<{ clave: string | null }> {
    return this.http.get<{ clave: string | null }>(`${API}/avisos/push/`);
  }

  suscribirPush(suscripcion: PushSubscriptionJSON): Observable<void> {
    return this.http.post<void>(`${API}/avisos/push/`, suscripcion);
  }

  desuscribirPush(endpoint: string): Observable<void> {
    return this.http.request<void>('delete', `${API}/avisos/push/`, { body: { endpoint } });
  }
}
