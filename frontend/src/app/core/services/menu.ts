import { Injectable, inject, signal } from '@angular/core';
import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Observable, of, throwError } from 'rxjs';
import { catchError, tap } from 'rxjs/operators';

import { MenuSemanal, MotivoCambio, OpcionIntercambio } from '../models/minuta.model';
import { environment } from '../../../environments/environment';

const API = `${environment.apiUrl}/nutricion/menu`;

/** Menú de la semana armado con la minuta. Cada cambio devuelve el menú completo. */
@Injectable({ providedIn: 'root' })
export class MenuService {
  private http = inject(HttpClient);

  private _menu = signal<MenuSemanal | null>(null);
  readonly menu = this._menu.asReadonly();

  /** El menú de la semana de esa fecha, o null si aún no se ha armado. */
  cargar(semana?: string): Observable<MenuSemanal | null> {
    const params = semana ? { semana } : undefined;
    return this.http.get<MenuSemanal>(`${API}/`, { params }).pipe(
      catchError((err: HttpErrorResponse) =>
        err.status === 404 ? of(null) : throwError(() => err),
      ),
      tap((menu) => this._menu.set(menu)),
    );
  }

  generar(semana?: string): Observable<MenuSemanal> {
    return this.http
      .post<MenuSemanal>(`${API}/`, semana ? { semana } : {})
      .pipe(tap((m) => this._menu.set(m)));
  }

  opciones(comidaId: number, componenteId: number): Observable<OpcionIntercambio[]> {
    return this.http.get<OpcionIntercambio[]>(`${API}/comidas/${comidaId}/opciones/`, {
      params: { componente: componenteId },
    });
  }

  cambiarAlimento(
    comidaId: number,
    componenteId: number,
    alimentoId: number,
  ): Observable<MenuSemanal> {
    return this.accion(comidaId, 'cambiar', { componente: componenteId, alimento: alimentoId });
  }

  sugerir(comidaId: number, motivo: MotivoCambio): Observable<MenuSemanal> {
    return this.accion(comidaId, 'sugerir', { motivo });
  }

  porFuera(comidaId: number, porFuera: boolean): Observable<MenuSemanal> {
    return this.accion(comidaId, 'por-fuera', { por_fuera: porFuera });
  }

  /** Tras cambiar la minuta o las comidas por fuera, el menú en memoria ya no sirve. */
  olvidar(): void {
    this._menu.set(null);
  }

  private accion(comidaId: number, accion: string, datos: object): Observable<MenuSemanal> {
    return this.http
      .post<MenuSemanal>(`${API}/comidas/${comidaId}/${accion}/`, datos)
      .pipe(tap((m) => this._menu.set(m)));
  }
}
