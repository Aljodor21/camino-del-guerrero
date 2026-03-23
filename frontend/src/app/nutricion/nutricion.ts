import { Component, ChangeDetectionStrategy, inject, signal, computed, OnInit } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { ButtonModule } from 'primeng/button';
import { ProgressSpinnerModule } from 'primeng/progressspinner';

import { PlanNutricional, DiaNutricional } from '../core/models/nutricion.model';

const API = 'http://localhost:8000/api';

@Component({
  selector: 'app-nutricion',
  templateUrl: './nutricion.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [ButtonModule, ProgressSpinnerModule],
})
export class Nutricion implements OnInit {
  private http = inject(HttpClient);

  protected loading            = signal(true);
  protected loadingRegenerar   = signal(false);
  protected plan               = signal<PlanNutricional | null>(null);
  protected sinPlan            = signal(false);
  protected diaSeleccionado    = signal(0);

  protected diaActual = computed(() => {
    const p = this.plan();
    if (!p?.dias.length) return null;
    return p.dias[this.diaSeleccionado()] ?? null;
  });

  ngOnInit(): void {
    this.cargarPlan();
  }

  private cargarPlan(): void {
    this.loading.set(true);
    this.http.get<PlanNutricional>(`${API}/nutricion/mi-plan/`).subscribe({
      next: plan => {
        this.plan.set(plan);
        const hoy = new Date().getDay();
        const hoyDjango = hoy === 0 ? 7 : hoy;
        const idx = plan.dias.findIndex(d => d.dia_semana === hoyDjango);
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
}
