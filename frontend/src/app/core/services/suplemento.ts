import { Injectable, computed, inject, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, forkJoin } from 'rxjs';
import { map, switchMap, tap } from 'rxjs/operators';

import { AgendaService } from './agenda';
import {
  AccionSuplemento,
  CrearSuplementoPayload,
  Suplemento,
  SuplementoPayload,
  TablaNutricional,
} from '../models/suplemento.model';
import { environment } from '../../../environments/environment';

const API = `${environment.apiUrl}/nutricion/suplementos`;

/**
 * Suplementos del proceso vigente. Cada cambio recalcula en el servidor los
 * recordatorios sugeridos, así que después de cada uno se recarga la agenda.
 */
@Injectable({ providedIn: 'root' })
export class SuplementoService {
  private http = inject(HttpClient);
  private agenda = inject(AgendaService);

  private _suplementos = signal<Suplemento[]>([]);

  readonly suplementos = this._suplementos.asReadonly();
  readonly activos = computed(() => this._suplementos().filter((s) => !s.fecha_fin));
  readonly terminados = computed(() => this._suplementos().filter((s) => s.fecha_fin));

  porId(id: number): Suplemento | undefined {
    return this._suplementos().find((s) => s.id === id);
  }

  cargar(): Observable<Suplemento[]> {
    return this.http
      .get<Suplemento[]>(`${API}/`)
      .pipe(tap((lista) => this._suplementos.set(lista)));
  }

  crear(payload: CrearSuplementoPayload): Observable<Suplemento> {
    return this.conAgenda(this.http.post<Suplemento>(`${API}/`, payload));
  }

  actualizar(id: number, cambios: Partial<SuplementoPayload>): Observable<Suplemento> {
    return this.conAgenda(this.http.patch<Suplemento>(`${API}/${id}/`, cambios));
  }

  accion(
    id: number,
    accion: AccionSuplemento,
    datos: { dias?: number } | SuplementoPayload = {},
  ): Observable<Suplemento> {
    return this.conAgenda(this.http.post<Suplemento>(`${API}/${id}/${accion}/`, datos));
  }

  /** Sube la foto o el PDF de la etiqueta (reemplaza al anterior). */
  subirInfo(id: number, archivo: File): Observable<Suplemento> {
    const cuerpo = new FormData();
    cuerpo.append('archivo', archivo);
    return this.recargando(this.http.post<Suplemento>(`${API}/${id}/info/`, cuerpo));
  }

  quitarInfo(id: number): Observable<Suplemento> {
    return this.recargando(this.http.delete<Suplemento>(`${API}/${id}/info/`));
  }

  /** El archivo es privado: se pide con el token. */
  verInfo(id: number): Observable<Blob> {
    return this.http.get(`${API}/${id}/info/`, { responseType: 'blob' });
  }

  /** Sube la foto del producto (reemplaza a la anterior). */
  subirFoto(id: number, archivo: File): Observable<Suplemento> {
    const cuerpo = new FormData();
    cuerpo.append('archivo', archivo);
    return this.recargando(this.http.post<Suplemento>(`${API}/${id}/foto/`, cuerpo));
  }

  quitarFoto(id: number): Observable<Suplemento> {
    return this.recargando(this.http.delete<Suplemento>(`${API}/${id}/foto/`));
  }

  /** La foto es privada: se pide con el token. */
  verFoto(id: number): Observable<Blob> {
    return this.http.get(`${API}/${id}/foto/`, { responseType: 'blob' });
  }

  /** La IA propone la tabla leyendo la etiqueta subida. No guarda: el usuario la revisa y la confirma. */
  leerTabla(id: number): Observable<{ tabla: TablaNutricional; nota: string }> {
    return this.http.post<{ tabla: TablaNutricional; nota: string }>(
      `${API}/${id}/tabla/leer/`,
      {},
    );
  }

  eliminar(id: number): Observable<void> {
    return this.conAgenda(this.http.delete<void>(`${API}/${id}/`));
  }

  private recargando(peticion: Observable<Suplemento>): Observable<Suplemento> {
    return peticion.pipe(switchMap((s) => this.cargar().pipe(map(() => s))));
  }

  /** Recarga la lista (una acción puede tocar dos suplementos) y la agenda. */
  private conAgenda<T>(peticion: Observable<T>): Observable<T> {
    return peticion.pipe(
      switchMap((resultado) =>
        forkJoin([this.cargar(), this.agenda.cargar(true)]).pipe(map(() => resultado)),
      ),
    );
  }
}
