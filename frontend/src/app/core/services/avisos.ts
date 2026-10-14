import { Injectable, computed, inject, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { tap } from 'rxjs/operators';

import {
  Aviso,
  CumplimientoGlobal,
  Habitos,
  HabitosPayload,
  HorasDelDia,
  ResumenHoy,
  SugerenciaDeHoras,
  Sueno,
} from '../models/avisos.model';
import { Capitulo, Logros } from '../models/logros.model';
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

  /** `sondeo`: la revisión que la app hace sola cada minuto, para no mezclarla con lo que la persona hace. */
  cargar(sondeo = false): Observable<Aviso[]> {
    const headers = sondeo ? { 'X-Segundo-Plano': '1' } : undefined;
    return this.http
      .get<Aviso[]>(`${API}/avisos/`, { headers })
      .pipe(tap((a) => this._avisos.set(a)));
  }

  cargarHoy(): Observable<ResumenHoy> {
    return this.http.get<ResumenHoy>(`${API}/hoy/`).pipe(tap((h) => this._hoy.set(h)));
  }

  /** Cuánto se cumplió entre dos fechas (YYYY-MM-DD): agua, dormir y, con proceso, todo lo demás. */
  cumplimiento(desde: string, hasta: string): Observable<CumplimientoGlobal> {
    return this.http.get<CumplimientoGlobal>(`${API}/cumplimiento/`, { params: { desde, hasta } });
  }

  /** La racha, los hitos y cuáles son nuevos. */
  logros(): Observable<Logros> {
    return this.http.get<Logros>(`${API}/logros/`);
  }

  /** La persona ya vio celebrar estos hitos. */
  marcarHitosVistos(ids: string[]): Observable<{ vistos: number }> {
    return this.http.post<{ vistos: number }>(`${API}/logros/vistos/`, { ids });
  }

  /** La semana de lunes a domingo (YYYY-MM-DD del lunes); sin fecha, la de hoy. */
  capitulo(lunes?: string): Observable<Capitulo> {
    return this.http.get<Capitulo>(`${API}/capitulo/`, { params: lunes ? { lunes } : {} });
  }

  /** «Me levanté»: anota la hora de ahora. `hora` solo se acepta si no se anotó a tiempo (una vez). */
  registrarLevantar(hora?: string): Observable<{ momento: string }> {
    return this.http.post<{ momento: string }>(`${API}/registros/levantar/`, hora ? { hora } : {});
  }

  /** Empieza una siesta (no se puede desde que empieza la jornada de dormir). */
  iniciarSiesta(): Observable<{ momento: string }> {
    return this.http.post<{ momento: string }>(`${API}/registros/siesta/iniciar/`, {});
  }

  terminarSiesta(): Observable<{ momento: string }> {
    return this.http.post<{ momento: string }>(`${API}/registros/siesta/terminar/`, {});
  }

  /** «Me acosté», sin esperar el aviso. */
  registrarDormir(): Observable<{ momento: string }> {
    return this.http.post<{ momento: string }>(`${API}/registros/dormir/`, {});
  }

  /** Cambia las horas de levantarse y acostarse de un solo día; con las dos vacías vuelve a lo de siempre. */
  guardarHorario(
    fecha: string,
    horas: { hora_levantarse: string | null; hora_dormir: string | null },
  ): Observable<HorasDelDia & { fecha: string }> {
    return this.http.put<HorasDelDia & { fecha: string }>(`${API}/horario/${fecha}/`, horas);
  }

  /** Horas que podrían ajustarse según cómo usa la persona la app (solo propone). */
  sugerenciasDeHoras(): Observable<SugerenciaDeHoras[]> {
    return this.http.get<SugerenciaDeHoras[]>(`${API}/sugerencias/`);
  }

  /** Cuánto se durmió entre dos fechas; sin fechas, los últimos 7 días. */
  sueno(desde?: string, hasta?: string): Observable<Sueno> {
    const params: Record<string, string> = {};
    if (desde) params['desde'] = desde;
    if (hasta) params['hasta'] = hasta;
    return this.http.get<Sueno>(`${API}/sueno/`, { params });
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
      if (!document.hidden) this.cargar(true).subscribe({ error: () => undefined });
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
  llavePush(): Observable<{ clave: string | null; en_la_app: boolean }> {
    return this.http.get<{ clave: string | null; en_la_app: boolean }>(`${API}/avisos/push/`);
  }

  suscribirPush(suscripcion: PushSubscriptionJSON): Observable<void> {
    return this.http.post<void>(`${API}/avisos/push/`, suscripcion);
  }

  desuscribirPush(endpoint: string): Observable<void> {
    return this.http.request<void>('delete', `${API}/avisos/push/`, { body: { endpoint } });
  }
}
