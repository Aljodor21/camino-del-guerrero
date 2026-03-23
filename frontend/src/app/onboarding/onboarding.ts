import { Component, ChangeDetectionStrategy, inject, signal, OnInit } from '@angular/core';
import { Router } from '@angular/router';
import { HttpClient } from '@angular/common/http';
import { ReactiveFormsModule, FormBuilder, Validators } from '@angular/forms';
import { firstValueFrom } from 'rxjs';
import { InputNumberModule } from 'primeng/inputnumber';
import { InputTextModule } from 'primeng/inputtext';
import { AutoCompleteModule } from 'primeng/autocomplete';
import { SelectButtonModule } from 'primeng/selectbutton';
import { ButtonModule } from 'primeng/button';
import { MessageModule } from 'primeng/message';
import { ProgressSpinnerModule } from 'primeng/progressspinner';

import { ThemeService } from '../core/services/theme';
import { Implemento } from '../core/models/rutina.model';
import { PAISES } from '../core/constants/paises';

import { environment } from '../../environments/environment';
const API = environment.apiUrl;

@Component({
  selector: 'app-onboarding',
  templateUrl: './onboarding.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [ReactiveFormsModule, InputNumberModule, InputTextModule, AutoCompleteModule, SelectButtonModule, ButtonModule, MessageModule, ProgressSpinnerModule],
})
export class Onboarding implements OnInit {
  private http = inject(HttpClient);
  private router = inject(Router);
  protected theme = inject(ThemeService);
  private fb = inject(FormBuilder);

  protected paso = signal(1);
  protected error = signal('');
  protected implementos = signal<Implemento[]>([]);
  protected seleccionados = signal<number[]>([]);

  protected loadingImplementos = signal(true);
  protected sinImplementos = signal(false);

  protected paisesFiltrados = signal<string[]>([]);

  protected filtrarPaises(query: string): void {
    const q = query.toLowerCase();
    this.paisesFiltrados.set(PAISES.filter(p => p.toLowerCase().includes(q)));
  }

  protected readonly objetivoOpciones = [
    { label: 'Bajar de peso',  value: 'bajar_peso',    icon: 'pi pi-arrow-down' },
    { label: 'Ganar músculo',  value: 'ganar_musculo', icon: 'pi pi-bolt'       },
    { label: 'Mantener',       value: 'mantener',      icon: 'pi pi-minus'      },
    { label: 'Resistencia',    value: 'resistencia',   icon: 'pi pi-heart'      },
  ];

  protected readonly frecuenciaOpciones = [
    { label: 'Cada 15 días', value: 15 },
    { label: 'Cada mes',     value: 30 },
  ];

  protected readonly nivelOpciones = [
    { label: 'Principiante', value: 'principiante' },
    { label: 'Intermedio',   value: 'intermedio'   },
    { label: 'Avanzado',     value: 'avanzado'      },
  ];

  protected readonly diasOpciones = [
    { label: '3 días', value: 3 },
    { label: '4 días', value: 4 },
    { label: '5 días', value: 5 },
  ];

  protected readonly duracionOpciones = [
    { label: '30 min', value: 30 },
    { label: '45 min', value: 45 },
    { label: '60 min', value: 60 },
  ];

  protected form = this.fb.nonNullable.group({
    peso_inicial:             [null as unknown as number, [Validators.required, Validators.min(20), Validators.max(300)]],
    peso_objetivo:            [null as number | null],
    objetivo:                 ['bajar_peso', Validators.required],
    frecuencia_peso:          [30, Validators.required],
    estatura:                 [null as unknown as number, [Validators.required, Validators.min(100), Validators.max(250)]],
    nivel_actividad:          ['principiante', Validators.required],
    dias_entrenamiento:       [3, Validators.required],
    duracion_sesion:          [45, Validators.required],
    nacionalidad:             ['', Validators.required],
    region:                   ['', Validators.required],
    preferencias_alimentarias:[''],
  });


  ngOnInit(): void {
    this.http.get<Implemento[]>(`${API}/rutinas/implementos/`).subscribe({
      next: data => {
        this.implementos.set(data);
        this.loadingImplementos.set(false);
      },
      error: () => {
        this.loadingImplementos.set(false);
        this.sinImplementos.set(true);
      },
    });
  }


  protected isSeleccionado(id: number): boolean {
    return this.seleccionados().includes(id);
  }

  protected clasesCard(activo: boolean): string {
    const base = 'flex items-center gap-2 p-3 rounded-xl border-2 text-left transition-all w-full';
    return activo
      ? `${base} border-guerrero-red bg-red-50 dark:bg-guerrero-red/10 text-guerrero-red`
      : `${base} border-gray-200 dark:border-dark-700 text-gray-600 dark:text-gray-400`;
  }

  protected toggleImplemento(id: number): void {
    const sinImplemento = this.implementos().find(i => i.es_sin_implemento)?.id;
    const actual = this.seleccionados();
    if (id === sinImplemento) {
      this.seleccionados.set(actual.includes(id) ? [] : [id]);
      return;
    }
    const filtrado = actual.filter(i => i !== sinImplemento);
    this.seleccionados.set(
      filtrado.includes(id) ? filtrado.filter(i => i !== id) : [...filtrado, id]
    );
  }

  protected paso1Valido(): boolean {
    const c = this.form.controls;
    return c.peso_inicial.valid && c.objetivo.valid && c.estatura.valid
        && c.nivel_actividad.valid && c.dias_entrenamiento.valid && c.duracion_sesion.valid
        && c.nacionalidad.valid && c.region.valid;
  }


  protected siguientePaso(): void {
    if (this.paso() === 2) {
      this.paso.set(3);
      this.generarPlan();
    } else {
      this.paso.update(v => v + 1);
    }
  }

  protected anteriorPaso(): void {
    this.paso.update(v => v - 1);
  }

    private async generarPlan(): Promise<void> {
      this.error.set('');
      const {
        peso_inicial, peso_objetivo, objetivo, frecuencia_peso, estatura,
        nivel_actividad, dias_entrenamiento, duracion_sesion, nacionalidad, region, preferencias_alimentarias,
      } = this.form.getRawValue();
      try {
        await firstValueFrom(this.http.post(`${API}/usuarios/objetivo/`, {
          objetivo, peso_inicial, nivel_actividad, dias_entrenamiento, duracion_sesion,
          ...(peso_objetivo ? { peso_objetivo } : {}),
        }));
        await firstValueFrom(this.http.post(`${API}/progreso/peso/`, { peso_kg: peso_inicial }));
        await firstValueFrom(this.http.patch(`${API}/usuarios/perfil/`, {
          frecuencia_peso, estatura,
          ...(nacionalidad             ? { nacionalidad }              : {}),
          ...(region                   ? { region }                    : {}),
          ...(preferencias_alimentarias ? { preferencias_alimentarias } : {}),
        }));
        const existentes = await firstValueFrom(this.http.get<{id: number}[]>(`${API}/rutinas/mis-implementos/`));
        for (const e of existentes) {
          await firstValueFrom(this.http.delete(`${API}/rutinas/mis-implementos/${e.id}/`));
        }
        for (const id of this.seleccionados()) {
          await firstValueFrom(this.http.post(`${API}/rutinas/mis-implementos/`, { implemento_id: id }));
        }
        await firstValueFrom(this.http.post(`${API}/nutricion/generar-rutina/`, {}));
        await firstValueFrom(this.http.post(`${API}/nutricion/mi-plan/`, {}));
        this.router.navigate(['/rutinas']);
      } catch {
        this.error.set('Ocurrió un error al generar tu plan. Vuelve atrás e intenta de nuevo.');
      }
    }

}
