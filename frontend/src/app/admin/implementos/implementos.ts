import { Component, ChangeDetectionStrategy, inject, signal, OnInit } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { ReactiveFormsModule, FormBuilder, Validators } from '@angular/forms';
import { DialogModule } from 'primeng/dialog';
import { InputTextModule } from 'primeng/inputtext';
import { CheckboxModule } from 'primeng/checkbox';
import { ButtonModule } from 'primeng/button';
import { MessageModule } from 'primeng/message';
import { ProgressSpinnerModule } from 'primeng/progressspinner';

import { Implemento } from '../../core/models/rutina.model';

import { environment } from '../../../environments/environment';
const API = environment.apiUrl;

@Component({
  selector: 'app-implementos',
  templateUrl: './implementos.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [ReactiveFormsModule, DialogModule, InputTextModule, CheckboxModule, ButtonModule, MessageModule, ProgressSpinnerModule],
})
export class Implementos implements OnInit {
  private http = inject(HttpClient);
  private fb = inject(FormBuilder);

  protected implementos = signal<Implemento[]>([]);
  protected loading = signal(true);
  protected saving = signal(false);
  protected error = signal('');
  protected dialogVisible = signal(false);
  protected editandoId = signal<number | null>(null);

  protected form = this.fb.nonNullable.group({
    nombre:           ['', Validators.required],
    descripcion:      [''],
    categoria:        [''],
    es_sin_implemento:[false],
  });

  ngOnInit(): void {
    this.cargar();
  }

  private cargar(): void {
    this.loading.set(true);
    this.http.get<Implemento[]>(`${API}/rutinas/implementos/`).subscribe({
      next: data => {
        this.implementos.set(data);
        this.loading.set(false);
      },
    });
  }

  protected abrir(imp?: Implemento): void {
    this.error.set('');
    if (imp) {
      this.editandoId.set(imp.id);
      this.form.setValue({
        nombre: imp.nombre, descripcion: imp.descripcion,
        categoria: imp.categoria, es_sin_implemento: imp.es_sin_implemento,
      });
    } else {
      this.editandoId.set(null);
      this.form.reset({ nombre: '', descripcion: '', categoria: '', es_sin_implemento: false });
    }
    this.dialogVisible.set(true);
  }

  protected guardar(): void {
    if (this.form.invalid) return;
    this.saving.set(true);
    const id = this.editandoId();
    const req = id
      ? this.http.patch<Implemento>(`${API}/rutinas/implementos/${id}/`, this.form.getRawValue())
      : this.http.post<Implemento>(`${API}/rutinas/implementos/`, this.form.getRawValue());

    req.subscribe({
      next: () => { this.saving.set(false); this.dialogVisible.set(false); this.cargar(); },
      error: () => { this.error.set('Error al guardar.'); this.saving.set(false); },
    });
  }

  protected eliminar(imp: Implemento): void {
    if (!confirm(`¿Eliminar "${imp.nombre}"?`)) return;
    this.http.delete(`${API}/rutinas/implementos/${imp.id}/`).subscribe({
      next: () => this.cargar(),
    });
  }
}
