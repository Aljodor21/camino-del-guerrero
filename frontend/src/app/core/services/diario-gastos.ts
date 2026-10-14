import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

import { ClaseGasto, EstadoDiario, RubroPayload } from '../models/diario-gastos.model';
import { environment } from '../../../environments/environment';

const API = `${environment.apiUrl}/crecimiento/diario`;

/** El diario de gastos de un proyecto: cada llamada responde el diario entero. */
@Injectable({ providedIn: 'root' })
export class DiarioGastosService {
  private http = inject(HttpClient);

  cargar(proyecto: number): Observable<EstadoDiario> {
    return this.http.get<EstadoDiario>(`${API}/${proyecto}/`);
  }

  guardarRubros(proyecto: number, rubros: RubroPayload[]): Observable<EstadoDiario> {
    return this.http.put<EstadoDiario>(`${API}/${proyecto}/`, { rubros });
  }

  anotar(
    proyecto: number,
    gasto: {
      fecha: string;
      valor: number;
      descripcion: string;
      categoria: string;
      clase: ClaseGasto;
    },
  ): Observable<EstadoDiario> {
    return this.http.post<EstadoDiario>(`${API}/${proyecto}/gastos/`, gasto);
  }

  borrarGasto(proyecto: number, gasto: number): Observable<EstadoDiario> {
    return this.http.delete<EstadoDiario>(`${API}/${proyecto}/gastos/${gasto}/`);
  }

  sinGasto(proyecto: number, fecha: string): Observable<EstadoDiario> {
    return this.http.post<EstadoDiario>(`${API}/${proyecto}/sin-gasto/`, { fecha });
  }
}
