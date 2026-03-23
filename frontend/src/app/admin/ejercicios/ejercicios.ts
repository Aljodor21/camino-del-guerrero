import { Component, ChangeDetectionStrategy, inject, signal, OnInit } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { ReactiveFormsModule, FormBuilder } from '@angular/forms';
import { DialogModule } from 'primeng/dialog';
import { InputTextModule } from 'primeng/inputtext';
import { ButtonModule } from 'primeng/button';
import { MessageModule } from 'primeng/message';
import { ProgressSpinnerModule } from 'primeng/progressspinner';
import { TooltipModule } from 'primeng/tooltip';

import { Ejercicio } from '../../core/models/rutina.model';

const API = 'http://localhost:8000/api';

@Component({
  selector: 'app-ejercicios',
  templateUrl: './ejercicios.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [ReactiveFormsModule, DialogModule, InputTextModule, ButtonModule, MessageModule, ProgressSpinnerModule, TooltipModule],
})
export class Ejercicios implements OnInit {
  private http = inject(HttpClient);
  private fb = inject(FormBuilder);

  protected ejercicios = signal<Ejercicio[]>([]);
  protected loading = signal(true);
  protected saving = signal(false);
  protected error = signal('');
  protected dialogVisible = signal(false);
  protected editandoId = signal<number | null>(null);
  protected editandoNombre = signal('');

  protected urlControl = this.fb.nonNullable.control('');

  ngOnInit(): void {
    this.cargar();
  }

  private cargar(): void {
    this.loading.set(true);
    this.http.get<Ejercicio[]>(`${API}/rutinas/ejercicios/`).subscribe({
      next: data => {
        this.ejercicios.set(data);
        this.loading.set(false);
      },
    });
  }

  protected abrirVideo(ej: Ejercicio): void {
    this.error.set('');
    this.editandoId.set(ej.id);
    this.editandoNombre.set(ej.nombre);
    this.urlControl.setValue(ej.url_youtube ?? '');
    this.dialogVisible.set(true);
  }

  protected guardarVideo(): void {
    const id = this.editandoId();
    if (!id) return;
    this.saving.set(true);
    this.http.patch(`${API}/rutinas/ejercicios/${id}/video/`, { url_youtube: this.urlControl.value }).subscribe({
      next: () => { this.saving.set(false); this.dialogVisible.set(false); this.cargar(); },
      error: () => { this.error.set('Error al guardar.'); this.saving.set(false); },
    });
  }
}
