import {
  Component,
  ChangeDetectionStrategy,
  inject,
  signal,
  computed,
  OnInit,
} from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { ButtonModule } from 'primeng/button';
import { ProgressSpinnerModule } from 'primeng/progressspinner';

import { PlanNutricional, ListaMercado, ItemMercado } from '../core/models/nutricion.model';

import { environment } from '../../environments/environment';
const API = environment.apiUrl;

@Component({
  selector: 'app-nutricion',
  templateUrl: './nutricion.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [ButtonModule, ProgressSpinnerModule],
})
export class Nutricion implements OnInit {
  private http = inject(HttpClient);

  protected seccion = signal<'plan' | 'mercado'>('plan');

  // ── PLAN ──────────────────────────────────────────────────────────
  protected loading = signal(true);
  protected loadingRegenerar = signal(false);
  protected plan = signal<PlanNutricional | null>(null);
  protected sinPlan = signal(false);
  protected diaSeleccionado = signal(0);

  protected diaActual = computed(() => {
    const p = this.plan();
    if (!p?.dias.length) return null;
    return p.dias[this.diaSeleccionado()] ?? null;
  });

  // ── MERCADO ───────────────────────────────────────────────────────
  protected lista = signal<ListaMercado | null>(null);
  protected loadingLista = signal(false);
  protected sinLista = signal(false);

  protected categorias = computed(() => {
    const items = this.lista()?.items ?? [];
    const mapa = new Map<string, { nombre: string; items: ItemMercado[] }>();
    for (const item of items) {
      if (!mapa.has(item.categoria)) {
        mapa.set(item.categoria, { nombre: item.categoria_nombre, items: [] });
      }
      mapa.get(item.categoria)!.items.push(item);
    }
    return Array.from(mapa.values());
  });

  protected totalItems = computed(() => this.lista()?.items.length ?? 0);
  protected itemsComprados = computed(
    () => this.lista()?.items.filter((i) => i.comprado).length ?? 0,
  );

  // ── OVERLAY GLOBAL DE CARGA ───────────────────────────────────────
  protected mostrandoOverlay = computed(
    () => this.loadingRegenerar() || this.loadingLista() || this.loadingRechazo() !== null,
  );

  protected mensajeOverlay = computed(() => {
    if (this.loadingRechazo()) return 'Ajustando tu plan…';
    if (this.loadingRegenerar()) return 'Generando tu plan nutricional…';
    if (this.loadingLista()) return 'Generando tu lista de mercado…';
    return '';
  });

  ngOnInit(): void {
    this.cargarPlan();
    this.cargarLista();
  }

  // ── PLAN ──────────────────────────────────────────────────────────
  private cargarPlan(): void {
    this.loading.set(true);
    this.http.get<PlanNutricional>(`${API}/nutricion/mi-plan/`).subscribe({
      next: (plan) => {
        this.plan.set(plan);
        const hoy = new Date().getDay();
        const hoyDjango = hoy === 0 ? 7 : hoy;
        const idx = plan.dias.findIndex((d) => d.dia_semana === hoyDjango);
        this.diaSeleccionado.set(idx >= 0 ? idx : 0);
        this.loading.set(false);
        this.loadingRegenerar.set(false);
      },
      error: () => {
        this.sinPlan.set(true);
        this.loading.set(false);
        this.loadingRegenerar.set(false);
      },
    });
  }

  protected regenerar(): void {
    this.loadingRegenerar.set(true);
    this.sinPlan.set(false);
    this.http.post(`${API}/nutricion/mi-plan/`, {}).subscribe({
      next: () => this.cargarPlan(),
      error: () => this.loadingRegenerar.set(false),
    });
  }

  protected esHoy(diaSemana: number): boolean {
    const hoy = new Date().getDay();
    return (hoy === 0 ? 7 : hoy) === diaSemana;
  }

  protected loadingRechazo = signal<string | null>(null);

  protected rechazarComida(campo: 'desayuno' | 'almuerzo' | 'cena' | 'snacks'): void {
    const dia = this.diaActual();
    if (!dia || this.loadingRechazo()) return;
    this.loadingRechazo.set(campo);
    this.http
      .post<PlanNutricional>(`${API}/nutricion/mi-plan/dias/${dia.id}/rechazar/`, { campo })
      .subscribe({
        next: (plan) => {
          this.plan.set(plan);
          this.loadingRechazo.set(null);
        },
        error: () => this.loadingRechazo.set(null),
      });
  }

  // ── MERCADO ───────────────────────────────────────────────────────
  protected numPersonas = signal(1);

  private cargarLista(): void {
    this.http.get<ListaMercado>(`${API}/nutricion/lista-mercado/`).subscribe({
      next: (lista) => {
        this.lista.set(lista);
        this.numPersonas.set(lista.num_personas);
      },
      error: () => this.sinLista.set(true),
    });
  }

  protected ajustarPersonas(delta: number): void {
    this.numPersonas.update((n) => Math.min(20, Math.max(1, n + delta)));
  }

  protected generarLista(): void {
    this.loadingLista.set(true);
    this.sinLista.set(false);
    this.http
      .post<ListaMercado>(`${API}/nutricion/lista-mercado/`, { num_personas: this.numPersonas() })
      .subscribe({
        next: (lista) => {
          this.lista.set(lista);
          this.numPersonas.set(lista.num_personas);
          this.loadingLista.set(false);
        },
        error: () => this.loadingLista.set(false),
      });
  }

  protected toggleItem(item: ItemMercado): void {
    this.http
      .patch<ItemMercado>(`${API}/nutricion/lista-mercado/items/${item.id}/toggle/`, {})
      .subscribe({
        next: (actualizado) => {
          this.lista.update((l) =>
            l
              ? {
                  ...l,
                  items: l.items.map((i) => (i.id === actualizado.id ? actualizado : i)),
                }
              : l,
          );
        },
      });
  }
}
