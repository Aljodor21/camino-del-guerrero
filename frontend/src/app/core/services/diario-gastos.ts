import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

import { ClaseGasto, EstadoDiario, RubroMes } from '../models/diario-gastos.model';
import { environment } from '../../../environments/environment';

const API = `${environment.apiUrl}/crecimiento/diario`;

/** El diario de gastos de un proyecto: cada llamada responde todo el mes de nuevo. */
@Injectable({ providedIn: 'root' })
export class DiarioGastosService {
  private http = inject(HttpClient);

  mes(proyecto: number, mes: string): Observable<EstadoDiario> {
    return this.http.get<EstadoDiario>(`${API}/${proyecto}/`, { params: { mes } });
  }

  guardarRubros(
    proyecto: number,
    mes: string,
    rubros: Pick<RubroMes, 'categoria' | 'nombre' | 'valor' | 'cerebral'>[],
  ): Observable<EstadoDiario> {
    return this.http.put<EstadoDiario>(`${API}/${proyecto}/`, { rubros }, { params: { mes } });
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

  /** `lista`: 'no-mensuales' o 'hormiga'. */
  crear(
    proyecto: number,
    lista: 'no-mensuales' | 'hormiga',
    datos: object,
    mes: string,
  ): Observable<EstadoDiario> {
    return this.http.post<EstadoDiario>(`${API}/${proyecto}/${lista}/`, datos, { params: { mes } });
  }

  borrar(
    proyecto: number,
    lista: 'no-mensuales' | 'hormiga',
    id: number,
    mes: string,
  ): Observable<EstadoDiario> {
    return this.http.delete<EstadoDiario>(`${API}/${proyecto}/${lista}/${id}/`, {
      params: { mes },
    });
  }
}
