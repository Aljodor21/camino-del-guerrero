import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

import {
  AreaCrecimiento,
  NotaCrecimiento,
  ProcesoCrecimiento,
  ProgramaCrecimiento,
  ProcesoPayload,
  ProyectoCrecimiento,
  ProyectoPayload,
  ResumenCrecimiento,
} from '../models/crecimiento.model';
import { environment } from '../../../environments/environment';

const API = `${environment.apiUrl}/crecimiento`;

/** Crecimiento personal: áreas, procesos (con su fuente), proyectos y notas de cada persona. */
@Injectable({ providedIn: 'root' })
export class CrecimientoService {
  private http = inject(HttpClient);

  areas(): Observable<AreaCrecimiento[]> {
    return this.http.get<AreaCrecimiento[]>(`${API}/areas/`);
  }
  crearArea(nombre: string): Observable<AreaCrecimiento> {
    return this.http.post<AreaCrecimiento>(`${API}/areas/`, { nombre });
  }
  renombrarArea(id: number, nombre: string): Observable<AreaCrecimiento> {
    return this.http.patch<AreaCrecimiento>(`${API}/areas/${id}/`, { nombre });
  }
  borrarArea(id: number): Observable<void> {
    return this.http.delete<void>(`${API}/areas/${id}/`);
  }

  area(id: number): Observable<AreaCrecimiento> {
    return this.http.get<AreaCrecimiento>(`${API}/areas/${id}/`);
  }

  /** El catálogo de programas ya armados (por ejemplo, un libro con sus ejercicios). */
  programas(): Observable<ProgramaCrecimiento[]> {
    return this.http.get<ProgramaCrecimiento[]>(`${API}/programas/`);
  }

  proceso(id: number): Observable<ProcesoCrecimiento> {
    return this.http.get<ProcesoCrecimiento>(`${API}/procesos/${id}/`);
  }

  proyecto(id: number): Observable<ProyectoCrecimiento> {
    return this.http.get<ProyectoCrecimiento>(`${API}/proyectos/${id}/`);
  }

  /** Los procesos de un área, o todos los de la persona si no se dice cuál. */
  procesos(area?: number): Observable<ProcesoCrecimiento[]> {
    return this.http.get<ProcesoCrecimiento[]>(`${API}/procesos/`, {
      params: area === undefined ? {} : { area: String(area) },
    });
  }
  crearProceso(datos: ProcesoPayload): Observable<ProcesoCrecimiento> {
    return this.http.post<ProcesoCrecimiento>(`${API}/procesos/`, datos);
  }
  actualizarProceso(id: number, datos: ProcesoPayload): Observable<ProcesoCrecimiento> {
    return this.http.patch<ProcesoCrecimiento>(`${API}/procesos/${id}/`, datos);
  }
  borrarProceso(id: number): Observable<void> {
    return this.http.delete<void>(`${API}/procesos/${id}/`);
  }

  proyectos(proceso: number): Observable<ProyectoCrecimiento[]> {
    return this.http.get<ProyectoCrecimiento[]>(`${API}/proyectos/`, {
      params: { proceso: String(proceso) },
    });
  }
  actualizarProyecto(id: number, datos: ProyectoPayload): Observable<ProyectoCrecimiento> {
    return this.http.patch<ProyectoCrecimiento>(`${API}/proyectos/${id}/`, datos);
  }

  /** Una acción propia del tipo del proyecto (por ejemplo, «hoy ya las leí»). */
  accion(id: number, accion: string): Observable<ProyectoCrecimiento> {
    return this.http.post<ProyectoCrecimiento>(`${API}/proyectos/${id}/accion/${accion}/`, {});
  }

  notas(proyecto: number): Observable<NotaCrecimiento[]> {
    return this.http.get<NotaCrecimiento[]>(`${API}/notas/`, {
      params: { proyecto: String(proyecto) },
    });
  }
  crearNota(proyecto: number, texto: string, titulo = ''): Observable<NotaCrecimiento> {
    return this.http.post<NotaCrecimiento>(`${API}/notas/`, { proyecto, texto, titulo });
  }
  borrarNota(id: number): Observable<void> {
    return this.http.delete<void>(`${API}/notas/${id}/`);
  }

  /** Lo que la app principal puede traer: avance por área y las últimas notas. */
  resumen(): Observable<ResumenCrecimiento> {
    return this.http.get<ResumenCrecimiento>(`${API}/resumen/`);
  }
}
