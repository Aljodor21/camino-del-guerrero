import { Component, ChangeDetectionStrategy, inject, signal, computed, OnInit } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { ReactiveFormsModule, FormBuilder } from '@angular/forms';
import { InputTextModule } from 'primeng/inputtext';
import { ButtonModule } from 'primeng/button';
import { MessageModule } from 'primeng/message';
import { ProgressSpinnerModule } from 'primeng/progressspinner';
import { TooltipModule } from 'primeng/tooltip';

import { Ejercicio } from '../../core/models/rutina.model';

import { environment } from '../../../environments/environment';
const API = environment.apiUrl;

@Component({
  selector: 'app-ejercicios',
  templateUrl: './ejercicios.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [ReactiveFormsModule, InputTextModule, ButtonModule, MessageModule, ProgressSpinnerModule, TooltipModule],
})
export class Ejercicios implements OnInit {
  private http = inject(HttpClient);
  private fb   = inject(FormBuilder);

  protected ejercicios      = signal<Ejercicio[]>([]);
  protected loading         = signal(true);
  protected saving          = signal(false);
  protected error           = signal('');
  protected busqueda        = signal('');
  protected soloSinVideo    = signal(false);
  protected editandoId      = signal<number | null>(null);

  protected urlControl = this.fb.nonNullable.control('');

  protected conVideo    = computed(() => this.ejercicios().filter(e => e.url_youtube).length);
  protected totalActual = computed(() => this.ejercicios().length);

  protected ejerciciosFiltrados = computed(() => {
    const q    = this.busqueda().toLowerCase();
    const solo = this.soloSinVideo();
    return this.ejercicios()
      .filter(e => (!solo || !e.url_youtube) && (!q || e.nombre.toLowerCase().includes(q)))
      .sort((a, b) => {
        // Sin video primero
        if (!a.url_youtube && b.url_youtube) return -1;
        if (a.url_youtube && !b.url_youtube) return 1;
        return a.nombre.localeCompare(b.nombre);
      });
  });

  ngOnInit(): void {
    this.cargar();
  }

  private cargar(): void {
    this.loading.set(true);
    this.http.get<Ejercicio[]>(`${API}/rutinas/ejercicios/`).subscribe({
      next: data => { this.ejercicios.set(data); this.loading.set(false); },
    });
  }

  protected iniciarEdicion(ej: Ejercicio): void {
    this.error.set('');
    this.editandoId.set(ej.id);
    this.urlControl.setValue(ej.url_youtube ?? '');
  }

  protected cancelarEdicion(): void {
    this.editandoId.set(null);
    this.urlControl.setValue('');
    this.error.set('');
  }

  protected guardar(ej: Ejercicio): void {
    this.saving.set(true);
    this.http.patch<Ejercicio>(`${API}/rutinas/ejercicios/${ej.id}/video/`, { url_youtube: this.urlControl.value }).subscribe({
      next: actualizado => {
        this.ejercicios.update(lista => lista.map(e => e.id === actualizado.id ? actualizado : e));
        this.editandoId.set(null);
        this.saving.set(false);
      },
      error: () => { this.error.set('Error al guardar.'); this.saving.set(false); },
    });
  }
}
