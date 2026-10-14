import { Injectable, computed, inject, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, of } from 'rxjs';
import { tap } from 'rxjs/operators';

import { AuthService } from './auth';
import { Recordatorio, RecordatorioPayload } from '../models/agenda.model';
import { diasEntre, hoyISO } from '../../shared/fechas';
import { environment } from '../../../environments/environment';

const API = `${environment.apiUrl}/agenda/recordatorios`;
const VISTOS_KEY = 'cdg_agenda_vistos';

/** Días que faltan para un recordatorio (negativo si ya pasó). */
export function diasPara(r: Recordatorio): number {
  return diasEntre(hoyISO(), r.fecha);
}

/** Fechas importantes del usuario: controles, mediciones y lo que quiera recordar. */
@Injectable({ providedIn: 'root' })
export class AgendaService {
  private http = inject(HttpClient);
  private auth = inject(AuthService);

  private _recordatorios = signal<Recordatorio[]>([]);
  private cargadoPara: number | null = null;

  readonly recordatorios = this._recordatorios.asReadonly();
  readonly pendientes = computed(() => this._recordatorios().filter((r) => !r.completado_en));
  readonly completados = computed(() =>
    this._recordatorios()
      .filter((r) => r.completado_en)
      .reverse(),
  );
  readonly proximo = computed(() => this.pendientes().find((r) => diasPara(r) >= 0) ?? null);

  /** Pendientes que ya entraron en su ventana de aviso, incluidos los vencidos. */
  readonly porAvisar = computed(() =>
    this.pendientes().filter((r) => diasPara(r) <= r.avisar_dias_antes),
  );

  /** Recordatorios cuyo aviso ya se cerró hoy (por id). Vuelven a avisar al día siguiente. */
  private vistosHoy = signal<number[]>(this.leerVistos());

  /** El aviso a mostrar en la app: el más cercano que no se haya cerrado hoy. */
  readonly aviso = computed(
    () => this.porAvisar().find((r) => !this.vistosHoy().includes(r.id)) ?? null,
  );

  marcarVisto(id: number): void {
    const vistos = [...this.vistosHoy(), id];
    this.vistosHoy.set(vistos);
    try {
      localStorage.setItem(VISTOS_KEY, JSON.stringify({ fecha: hoyISO(), ids: vistos }));
    } catch {
      // Sin almacenamiento el aviso solo se oculta en esta sesión.
    }
  }

  private leerVistos(): number[] {
    try {
      const guardado = JSON.parse(localStorage.getItem(VISTOS_KEY) ?? 'null');
      return guardado?.fecha === hoyISO() ? guardado.ids : [];
    } catch {
      return [];
    }
  }

  cargar(forzar = false): Observable<Recordatorio[]> {
    const usuarioId = this.auth.usuario()?.id ?? null;
    if (!forzar && usuarioId !== null && this.cargadoPara === usuarioId) {
      return of(this._recordatorios());
    }
    return this.http.get<Recordatorio[]>(`${API}/`).pipe(
      tap((lista) => {
        this._recordatorios.set(lista);
        this.cargadoPara = usuarioId;
      }),
    );
  }

  crear(payload: RecordatorioPayload): Observable<Recordatorio> {
    return this.http.post<Recordatorio>(`${API}/`, payload).pipe(
      tap((r) => {
        this.guardarEnLista(r);
        // Repetido son varios: se trae la lista completa.
        if (payload.repetir) this.cargar(true).subscribe({ error: () => undefined });
      }),
    );
  }

  actualizar(
    id: number,
    cambios: Partial<RecordatorioPayload> & { completado?: boolean },
  ): Observable<Recordatorio> {
    return this.http
      .patch<Recordatorio>(`${API}/${id}/`, cambios)
      .pipe(tap((r) => this.guardarEnLista(r)));
  }

  /** `siguientes`: también borra los que se repitieron después de este. */
  eliminar(id: number, siguientes = false): Observable<void> {
    return this.http
      .delete<void>(`${API}/${id}/`, { params: siguientes ? { siguientes: '1' } : {} })
      .pipe(
        tap(() => {
          if (siguientes) this.cargar(true).subscribe({ error: () => undefined });
          else this._recordatorios.update((lista) => lista.filter((r) => r.id !== id));
        }),
      );
  }

  /** Inserta o reemplaza y mantiene el orden por fecha y hora, como la API. */
  private guardarEnLista(r: Recordatorio): void {
    const clave = (x: Recordatorio) => `${x.fecha} ${x.hora ?? ''}`;
    this._recordatorios.update((lista) =>
      [...lista.filter((x) => x.id !== r.id), r].sort(
        (a, b) => clave(a).localeCompare(clave(b)) || a.id - b.id,
      ),
    );
  }
}
