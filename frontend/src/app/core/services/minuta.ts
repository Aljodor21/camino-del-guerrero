import { Injectable, computed, inject, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { switchMap, tap, map } from 'rxjs/operators';

import { MenuService } from './menu';
import { Minuta, MinutaCalculada, MinutaPayload, PreferenciasComida } from '../models/minuta.model';
import { environment } from '../../../environments/environment';

const API = `${environment.apiUrl}/nutricion`;

/** Minuta del proceso: la vigente y las anteriores. */
@Injectable({ providedIn: 'root' })
export class MinutaService {
  private http = inject(HttpClient);
  private menus = inject(MenuService);

  private _minutas = signal<Minuta[] | null>(null);

  /** null mientras no se ha cargado. La primera es la vigente. */
  readonly minutas = this._minutas.asReadonly();
  readonly vigente = computed(() => this._minutas()?.[0] ?? null);
  readonly anteriores = computed(() => (this._minutas() ?? []).slice(1));

  cargar(): Observable<Minuta[]> {
    return this.http
      .get<Minuta[]>(`${API}/minutas/`)
      .pipe(tap((lista) => this._minutas.set(lista)));
  }

  /** Lee un PDF que la app reconoce (como el de Comfama) para llenar la plantilla. No guarda. */
  leerPdf(archivo: File): Observable<MinutaPayload> {
    const datos = new FormData();
    datos.append('archivo', archivo);
    return this.http.post<MinutaPayload>(`${API}/minutas/leer-pdf/`, datos);
  }

  /** Minuta calculada para quien no tiene nutricionista. No guarda. */
  calcular(proceso?: number): Observable<MinutaCalculada> {
    return this.http.post<MinutaCalculada>(`${API}/minutas/calcular/`, proceso ? { proceso } : {});
  }

  /** Guarda la minuta (con el original adjunto, si lo hay). Desde ahí no cambia. */
  guardar(minuta: MinutaPayload, original: File | null): Observable<Minuta> {
    let cuerpo: MinutaPayload | FormData = minuta;
    if (original) {
      const datos = new FormData();
      Object.entries(minuta).forEach(([clave, valor]) => {
        if (valor === undefined) return;
        if (valor === null) {
          // Sin definir solo importa en la fecha del periodo; en lo demás, vacío es no mandarlo.
          if (clave === 'fecha_fin_plan') datos.append(clave, '');
          return;
        }
        datos.append(clave, typeof valor === 'object' ? JSON.stringify(valor) : String(valor));
      });
      datos.append('archivo', original);
      cuerpo = datos;
    }
    return this.http.post<Minuta>(`${API}/minutas/`, cuerpo).pipe(
      switchMap((minuta) => this.cargar().pipe(map(() => minuta))),
      tap(() => this.menus.olvidar()),
    );
  }

  /** El original (PDF o foto); va con el token, por eso no sirve un enlace directo. */
  archivo(id: number): Observable<Blob> {
    return this.http.get(`${API}/minutas/${id}/archivo/`, { responseType: 'blob' });
  }

  preferencias(): Observable<PreferenciasComida> {
    return this.http.get<PreferenciasComida>(`${API}/preferencias/`);
  }

  guardarPreferencias(preferencias: PreferenciasComida): Observable<PreferenciasComida> {
    return this.http
      .patch<PreferenciasComida>(`${API}/preferencias/`, preferencias)
      .pipe(tap(() => this.menus.olvidar()));
  }
}
