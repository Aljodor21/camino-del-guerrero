import { Component, ChangeDetectionStrategy, inject, signal, computed, OnInit } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { ReactiveFormsModule, FormBuilder, Validators } from '@angular/forms';
import { ButtonModule } from 'primeng/button';
import { DialogModule } from 'primeng/dialog';
import { InputNumberModule } from 'primeng/inputnumber';
import { TextareaModule } from 'primeng/textarea';
import { MessageModule } from 'primeng/message';
import { ProgressSpinnerModule } from 'primeng/progressspinner';

import { RegistroPeso, RegistroEntrenamiento } from '../core/models/progreso.model';

const API = 'http://localhost:8000/api';

@Component({
  selector: 'app-progreso',
  templateUrl: './progreso.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [ReactiveFormsModule, ButtonModule, DialogModule, InputNumberModule, TextareaModule, MessageModule, ProgressSpinnerModule],
})
export class Progreso implements OnInit {
  private http = inject(HttpClient);
  private fb = inject(FormBuilder);

  protected seccion = signal<'peso' | 'entrenamiento'>('peso');
  protected registrosPeso = signal<RegistroPeso[]>([]);
  protected registrosEntrenamiento = signal<RegistroEntrenamiento[]>([]);
  protected loading = signal(true);
  protected saving = signal(false);
  protected error = signal('');
  protected dialogVisible = signal(false);

  protected ultimoPeso = computed(() => this.registrosPeso()[0]?.peso_kg ?? null);
  protected cambioPeso = computed(() => {
    const r = this.registrosPeso();
    if (r.length < 2) return null;
    return +(r[0].peso_kg - r[r.length - 1].peso_kg).toFixed(1);
  });
  protected totalSesiones = computed(() => this.registrosEntrenamiento().length);
  protected totalMinutos = computed(() => this.registrosEntrenamiento().reduce((s, r) => s + r.duracion_minutos, 0));

  protected formPeso = this.fb.nonNullable.group({
    peso_kg: [null as unknown as number, [Validators.required, Validators.min(20), Validators.max(300)]],
    nota: [''],
  });

  protected formEntrenamiento = this.fb.nonNullable.group({
    rounds:            [0, [Validators.required, Validators.min(0)]],
    duracion_minutos:  [0, [Validators.required, Validators.min(0)]],
    notas:             [''],
  });

  ngOnInit(): void {
    this.cargarPeso();
    this.cargarEntrenamiento();
  }

  private cargarPeso(): void {
    this.loading.set(true);
    this.http.get<RegistroPeso[]>(`${API}/progreso/peso/`).subscribe({
      next: data => { this.registrosPeso.set(data); this.loading.set(false); },
      error: ()   => this.loading.set(false),
    });
  }

  private cargarEntrenamiento(): void {
    this.http.get<RegistroEntrenamiento[]>(`${API}/progreso/entrenamiento/`).subscribe({
      next: data => this.registrosEntrenamiento.set(data),
    });
  }

  protected abrirDialog(): void {
    this.error.set('');
    if (this.seccion() === 'peso') {
      this.formPeso.reset({ peso_kg: null as unknown as number, nota: '' });
    } else {
      this.formEntrenamiento.reset({ rounds: 0, duracion_minutos: 0, notas: '' });
    }
    this.dialogVisible.set(true);
  }

  protected guardar(): void {
    if (this.seccion() === 'peso' && this.formPeso.invalid) return;
    if (this.seccion() === 'entrenamiento' && this.formEntrenamiento.invalid) return;
    this.saving.set(true);
    this.error.set('');

    if (this.seccion() === 'peso') {
      this.http.post<RegistroPeso>(`${API}/progreso/peso/`, this.formPeso.getRawValue()).subscribe({
        next: () => { this.saving.set(false); this.dialogVisible.set(false); this.cargarPeso(); },
        error: () => { this.error.set('Error al guardar.'); this.saving.set(false); },
      });
    } else {
      this.http.post<RegistroEntrenamiento>(`${API}/progreso/entrenamiento/`, this.formEntrenamiento.getRawValue()).subscribe({
        next: () => { this.saving.set(false); this.dialogVisible.set(false); this.cargarEntrenamiento(); },
        error: () => { this.error.set('Error al guardar.'); this.saving.set(false); },
      });
    }
  }

  protected eliminarEntrenamiento(id: number): void {
    if (!confirm('¿Eliminar este registro?')) return;
    this.http.delete(`${API}/progreso/entrenamiento/${id}/`).subscribe({
      next: () => this.cargarEntrenamiento(),
    });
  }

  protected formatFecha(fecha: string): string {
    return new Date(fecha + 'T00:00:00').toLocaleDateString('es-CO', {
      day: 'numeric', month: 'short', year: 'numeric',
    });
  }
}
