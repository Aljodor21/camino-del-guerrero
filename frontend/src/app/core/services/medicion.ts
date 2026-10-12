import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

import { Medicion, MedicionPayload } from '../models/proceso.model';
import { environment } from '../../../environments/environment';

const API = `${environment.apiUrl}/progreso/mediciones`;

@Injectable({ providedIn: 'root' })
export class MedicionService {
  private http = inject(HttpClient);

  listar(): Observable<Medicion[]> {
    return this.http.get<Medicion[]>(`${API}/`);
  }

  registrar(medicion: MedicionPayload): Observable<Medicion> {
    return this.http.post<Medicion>(`${API}/`, medicion);
  }

  eliminar(id: number): Observable<void> {
    return this.http.delete<void>(`${API}/${id}/`);
  }
}
