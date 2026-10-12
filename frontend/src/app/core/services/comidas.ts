import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { map } from 'rxjs/operators';

import {
  Avances,
  Cumplimiento,
  PedidoComida,
  PeriodoCumplimiento,
  RegistroComida,
} from '../models/comidas.model';
import { TiempoComida } from '../models/minuta.model';
import { environment } from '../../../environments/environment';

const API = `${environment.apiUrl}/nutricion/comidas`;

/** Contar lo que se comió y ver cuánto se cumple de la minuta. */
@Injectable({ providedIn: 'root' })
export class ComidasService {
  private http = inject(HttpClient);

  pedido(tiempo: TiempoComida, fecha?: string): Observable<PedidoComida> {
    return this.http.get<PedidoComida>(`${API}/pedido/`, {
      params: fecha ? { tiempo, fecha } : { tiempo },
    });
  }

  contar(datos: {
    tiempo: TiempoComida;
    fecha?: string;
    avances: Avances;
    nota: string;
    foto: Blob | null;
  }): Observable<RegistroComida> {
    const cuerpo = new FormData();
    cuerpo.append('tiempo', datos.tiempo);
    if (datos.fecha) cuerpo.append('fecha', datos.fecha);
    cuerpo.append('avances', JSON.stringify(datos.avances));
    if (datos.nota) cuerpo.append('nota', datos.nota);
    if (datos.foto) cuerpo.append('foto', datos.foto, 'comida.jpg');
    return this.http.post<RegistroComida>(`${API}/registros/`, cuerpo);
  }

  cumplimiento(periodo: PeriodoCumplimiento): Observable<Cumplimiento> {
    return this.http.get<Cumplimiento>(`${API}/cumplimiento/`, { params: { periodo } });
  }

  /** La foto completa, como archivo, para verla en el visor de la app. */
  fotoBlob(id: number): Observable<Blob> {
    return this.http.get(`${API}/registros/${id}/foto/`, { responseType: 'blob' });
  }

  /** La foto es privada: se pide con el token y se muestra con una URL local. */
  foto(id: number, tamano: 'mini' | 'completa'): Observable<string> {
    const params = tamano === 'mini' ? { tamano } : undefined;
    return this.http
      .get(`${API}/registros/${id}/foto/`, { params, responseType: 'blob' })
      .pipe(map((blob) => URL.createObjectURL(blob)));
  }
}
