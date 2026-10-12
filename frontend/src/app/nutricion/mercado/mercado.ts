import {
  ChangeDetectionStrategy,
  Component,
  OnInit,
  computed,
  inject,
  input,
  signal,
} from '@angular/core';
import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { ButtonModule } from 'primeng/button';
import { MessageModule } from 'primeng/message';
import { ProgressSpinnerModule } from 'primeng/progressspinner';

import { ItemMercado, ListaMercado, PeriodoMercado } from '../../core/models/nutricion.model';
import { clasesChip } from '../../shared/chip';
import { cuandoEs, formatearFecha } from '../../shared/fechas';
import { mensajeError } from '../../shared/errores';
import { environment } from '../../../environments/environment';

const API = `${environment.apiUrl}/nutricion/lista-mercado`;

/** Lista de mercado de la semana: sale del menú, sin las comidas que se hacen por fuera. */
import { Ayuda } from '../../shared/ayuda/ayuda';

@Component({
  selector: 'app-mercado',
  templateUrl: './mercado.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [Ayuda, ButtonModule, MessageModule, ProgressSpinnerModule],
})
export class Mercado implements OnInit {
  private http = inject(HttpClient);

  protected lista = signal<ListaMercado | null>(null);
  protected cargando = signal(true);
  protected generando = signal(false);
  protected error = signal('');
  protected numPersonas = signal(1);
  protected periodo = signal<PeriodoMercado>('semana');
  protected clasesChip = clasesChip;
  protected periodos: { id: PeriodoMercado; label: string }[] = [
    { id: 'semana', label: 'Una semana' },
    { id: 'quincena', label: '15 días' },
    { id: 'mes', label: 'Un mes' },
  ];
  protected cuandoEs = cuandoEs;
  protected formatearFecha = formatearFecha;

  protected categorias = computed(() => {
    const mapa = new Map<string, { nombre: string; items: ItemMercado[] }>();
    for (const item of this.lista()?.items ?? []) {
      if (!mapa.has(item.categoria))
        mapa.set(item.categoria, { nombre: item.categoria_nombre, items: [] });
      mapa.get(item.categoria)!.items.push(item);
    }
    return Array.from(mapa.values());
  });
  protected totalItems = computed(() => this.lista()?.items.length ?? 0);
  protected itemsComprados = computed(
    () => this.lista()?.items.filter((i) => i.comprado).length ?? 0,
  );

  ngOnInit(): void {
    this.http.get<ListaMercado>(`${API}/`).subscribe({
      next: (lista) => {
        this.lista.set(lista);
        this.numPersonas.set(lista.num_personas);
        this.periodo.set(lista.periodo);
        this.cargando.set(false);
      },
      error: (err: HttpErrorResponse) => {
        if (err.status !== 404) this.error.set(mensajeError(err, 'No pudimos cargar tu lista.'));
        this.cargando.set(false);
      },
    });
  }

  protected ajustarPersonas(delta: number): void {
    this.numPersonas.update((n) => Math.min(20, Math.max(1, n + delta)));
  }

  protected generar(): void {
    this.generando.set(true);
    this.error.set('');
    this.http
      .post<ListaMercado>(`${API}/`, { num_personas: this.numPersonas(), periodo: this.periodo() })
      .subscribe({
        next: (lista) => {
          this.lista.set(lista);
          this.numPersonas.set(lista.num_personas);
          this.periodo.set(lista.periodo);
          this.generando.set(false);
        },
        error: (err) => {
          this.error.set(mensajeError(err, 'No pudimos armar la lista. Intenta de nuevo.'));
          this.generando.set(false);
        },
      });
  }

  protected toggleItem(item: ItemMercado): void {
    this.http.patch<ItemMercado>(`${API}/items/${item.id}/toggle/`, {}).subscribe({
      next: (actualizado) =>
        this.lista.update((l) =>
          l ? { ...l, items: l.items.map((i) => (i.id === actualizado.id ? actualizado : i)) } : l,
        ),
    });
  }
}
