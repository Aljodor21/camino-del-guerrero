import { Injectable, computed, inject, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, of } from 'rxjs';
import { map, tap } from 'rxjs/operators';

import { AuthService } from './auth';
import {
  ActualizarProcesoPayload,
  CrearProcesoPayload,
  EstadoProcesos,
  MedicionPayload,
  Modulo,
  Proceso,
} from '../models/proceso.model';
import { environment } from '../../../environments/environment';

const API = `${environment.apiUrl}/usuarios/procesos`;

/** Estado del proceso del usuario: de él dependen la navegación y los módulos visibles. */
@Injectable({ providedIn: 'root' })
export class ProcesoService {
  private http = inject(HttpClient);
  private auth = inject(AuthService);

  private _estado = signal<EstadoProcesos>({ actual: null, programado: null });
  private cargadoPara: number | null = null;

  readonly actual = computed(() => this._estado().actual);
  readonly programado = computed(() => this._estado().programado);

  /** El proceso que manda en la app: el que está en curso o, si aún no empieza, el programado. */
  readonly vigente = computed(() => this.actual() ?? this.programado());
  readonly tieneProceso = computed(() => this.vigente() !== null);
  readonly medicionInicialPendiente = computed(() => {
    const actual = this.actual();
    return actual !== null && actual.medicion_inicial === null;
  });

  tieneModulo(modulo: Modulo): boolean {
    const p = this.vigente();
    if (!p) return false;
    return modulo === 'alimentacion' ? p.incluye_alimentacion : p.incluye_entrenamiento;
  }

  /** Carga el estado una vez por usuario; `forzar` lo vuelve a pedir. */
  cargar(forzar = false): Observable<EstadoProcesos> {
    const usuarioId = this.auth.usuario()?.id ?? null;
    if (!forzar && usuarioId !== null && this.cargadoPara === usuarioId) {
      return of(this._estado());
    }
    return this.http.get<EstadoProcesos>(`${API}/estado/`).pipe(
      tap((estado) => {
        this._estado.set(estado);
        this.cargadoPara = usuarioId;
      }),
    );
  }

  historial(): Observable<Proceso[]> {
    return this.http.get<Proceso[]>(`${API}/`);
  }

  crear(payload: CrearProcesoPayload): Observable<Proceso> {
    return this.http.post<Proceso>(`${API}/`, payload).pipe(tap(() => this.invalidar()));
  }

  actualizar(id: number, payload: ActualizarProcesoPayload): Observable<Proceso> {
    return this.http.patch<Proceso>(`${API}/${id}/`, payload).pipe(tap((p) => this.reemplazar(p)));
  }

  cancelarProgramado(id: number): Observable<void> {
    return this.http.delete<void>(`${API}/${id}/`).pipe(tap(() => this.invalidar()));
  }

  /** Borra el proceso y todo lo que armó con él; solo quedan sus datos personales. */
  eliminarTodo(id: number): Observable<void> {
    return this.http.delete<void>(`${API}/${id}/`).pipe(tap(() => this.invalidar()));
  }

  /** Quita la alimentación o el entrenamiento y borra lo que se armó con él. */
  quitarModulo(id: number, modulo: Modulo): Observable<Proceso> {
    return this.http
      .post<Proceso>(`${API}/${id}/quitar-modulo/`, { modulo })
      .pipe(tap((p) => this.reemplazar(p)));
  }

  /** Al llegar el control: sigue el proceso hasta otra fecha, o sin definir (null). */
  renovar(id: number, fechaFinPlan: string | null): Observable<Proceso> {
    return this.http
      .post<Proceso>(`${API}/${id}/renovar/`, { fecha_fin_plan: fechaFinPlan })
      .pipe(tap((p) => this.reemplazar(p)));
  }

  registrarMedicionInicial(id: number, medicion: MedicionPayload): Observable<Proceso> {
    return this.http
      .post<Proceso>(`${API}/${id}/medicion-inicial/`, medicion)
      .pipe(tap((p) => this.reemplazar(p)));
  }

  /** Vuelve a pedir el estado (tras crear o cancelar cambian actual y programado). */
  refrescar(): Observable<void> {
    return this.cargar(true).pipe(map(() => undefined));
  }

  private invalidar(): void {
    this.cargadoPara = null;
  }

  private reemplazar(p: Proceso): void {
    this._estado.update((e) => ({
      actual: e.actual?.id === p.id ? p : e.actual,
      programado: e.programado?.id === p.id ? p : e.programado,
    }));
  }
}
