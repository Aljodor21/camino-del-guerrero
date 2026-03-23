import { Component, ChangeDetectionStrategy, inject, signal, OnInit } from '@angular/core';
import { Router } from '@angular/router';
import { HttpClient } from '@angular/common/http';
import { ReactiveFormsModule, FormBuilder, Validators } from '@angular/forms';
import { firstValueFrom } from 'rxjs';
import { InputNumberModule } from 'primeng/inputnumber';
import { SelectButtonModule } from 'primeng/selectbutton';
import { ButtonModule } from 'primeng/button';
import { MessageModule } from 'primeng/message';
import { ProgressSpinnerModule } from 'primeng/progressspinner';

import { ThemeService } from '../core/services/theme';
import { Implemento } from '../core/models/rutina.model';

import { environment } from '../../environments/environment';
const API = environment.apiUrl;

@Component({
  selector: 'app-onboarding',
  templateUrl: './onboarding.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [ReactiveFormsModule, InputNumberModule, SelectButtonModule, ButtonModule, MessageModule, ProgressSpinnerModule],
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

  protected form = this.fb.nonNullable.group({
    peso_inicial:   [null as unknown as number, [Validators.required, Validators.min(20), Validators.max(300)]],
    peso_objetivo:  [null as number | null],
    objetivo:       ['bajar_peso', Validators.required],
    frecuencia_peso:[30, Validators.required],
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
    return c.peso_inicial.valid && c.objetivo.valid;
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
      const { peso_inicial, peso_objetivo, objetivo, frecuencia_peso } = this.form.getRawValue();
      try {
        await firstValueFrom(this.http.post(`${API}/usuarios/objetivo/`, {
          objetivo, peso_inicial,
          ...(peso_objetivo ? { peso_objetivo } : {}),
        }));
        await firstValueFrom(this.http.post(`${API}/progreso/peso/`, { peso_kg: peso_inicial }));
        await firstValueFrom(this.http.patch(`${API}/usuarios/perfil/`, { frecuencia_peso }));
        for (const id of this.seleccionados()) {
          await firstValueFrom(this.http.post(`${API}/rutinas/mis-implementos/`, { implemento: id }));
        }
        await firstValueFrom(this.http.post(`${API}/nutricion/generar-rutina/`, {}));
        await firstValueFrom(this.http.post(`${API}/nutricion/mi-plan/`, {}));
        this.router.navigate(['/rutinas']);
      } catch {
        this.error.set('Ocurrió un error al generar tu plan. Vuelve atrás e intenta de nuevo.');
      }
    }

}
