import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

import { EstadoSalud, TomaPayload } from '../models/salud.model';
import { environment } from '../../../environments/environment';

const API = `${environment.apiUrl}/crecimiento/salud`;

/** El protocolo y los suplementos de un proyecto de Salud: cada llamada responde el estado entero. */
@Injectable({ providedIn: 'root' })
export class SaludService {
  private http = inject(HttpClient);

  cargar(proyecto: number): Observable<EstadoSalud> {
    return this.http.get<EstadoSalud>(`${API}/${proyecto}/`);
  }

  anotar(proyecto: number, toma: TomaPayload): Observable<EstadoSalud> {
    return this.http.post<EstadoSalud>(`${API}/${proyecto}/tomas/`, toma);
  }

  borrar(proyecto: number, toma: number): Observable<EstadoSalud> {
    return this.http.delete<EstadoSalud>(`${API}/${proyecto}/tomas/${toma}/`);
  }
}
