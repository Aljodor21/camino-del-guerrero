import { Component, ChangeDetectionStrategy, inject, signal, computed, OnInit } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { ReactiveFormsModule, FormBuilder, Validators } from '@angular/forms';
import { InputTextModule } from 'primeng/inputtext';
import { TextareaModule } from 'primeng/textarea';
import { SelectModule } from 'primeng/select';
import { ButtonModule } from 'primeng/button';
import { MessageModule } from 'primeng/message';
import { ProgressSpinnerModule } from 'primeng/progressspinner';
import { TooltipModule } from 'primeng/tooltip';

import { Recomendacion } from '../../core/models/rutina.model';
import { environment } from '../../../environments/environment';

const API = environment.apiUrl;

@Component({
  selector: 'app-admin-recomendaciones',
  templateUrl: './recomendaciones.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [ReactiveFormsModule, InputTextModule, TextareaModule, SelectModule,
            ButtonModule, MessageModule, ProgressSpinnerModule, TooltipModule],
})
export class AdminRecomendaciones implements OnInit {
  private http = inject(HttpClient);
  private fb   = inject(FormBuilder);

  protected recomendaciones = signal<Recomendacion[]>([]);
  protected loading         = signal(true);
  protected saving          = signal(false);
  protected error           = signal('');
  protected editandoId      = signal<number | null>(null);
  protected mostrandoForm   = signal(false);

  protected total   = computed(() => this.recomendaciones().length);
  protected activas = computed(() => this.recomendaciones().filter(r => r.activa).length);

  protected categorias = [
    { label: 'Técnica',    value: 'tecnica'   },
    { label: 'Físico',     value: 'fisico'    },
    { label: 'Nutrición',  value: 'nutricion' },
    { label: 'Mental',     value: 'mental'    },
    { label: 'General',    value: 'general'   },
  ];

  protected form = this.fb.nonNullable.group({
    titulo:      ['', Validators.required],
    descripcion: [''],
    url_video:   [''],
    categoria:   ['general' as string],
    orden:       [0],
  });

  ngOnInit(): void { this.cargar(); }

  private cargar(): void {
    this.loading.set(true);
    this.http.get<Recomendacion[]>(`${API}/rutinas/admin/recomendaciones/`).subscribe({
      next: data => { this.recomendaciones.set(data); this.loading.set(false); },
      error: ()   => this.loading.set(false),
    });
  }

  protected abrir(rec?: Recomendacion): void {
    this.error.set('');
    if (rec) {
      this.editandoId.set(rec.id);
      this.form.setValue({
        titulo: rec.titulo, descripcion: rec.descripcion,
        url_video: rec.url_video, categoria: rec.categoria, orden: rec.orden,
      });
    } else {
      this.editandoId.set(null);
      this.form.reset({ titulo: '', descripcion: '', url_video: '', categoria: 'general', orden: 0 });
    }
    this.mostrandoForm.set(true);
  }

  protected cancelar(): void {
    this.mostrandoForm.set(false);
    this.editandoId.set(null);
    this.error.set('');
  }

  protected guardar(): void {
    if (this.form.invalid) return;
    this.saving.set(true);
    const id  = this.editandoId();
    const req = id
      ? this.http.patch<Recomendacion>(`${API}/rutinas/admin/recomendaciones/${id}/`, this.form.getRawValue())
      : this.http.post<Recomendacion>(`${API}/rutinas/admin/recomendaciones/`, this.form.getRawValue());

    req.subscribe({
      next: () => { this.saving.set(false); this.mostrandoForm.set(false); this.cargar(); },
      error: () => { this.error.set('Error al guardar.'); this.saving.set(false); },
    });
  }

  protected toggleActiva(rec: Recomendacion): void {
    this.http.patch<Recomendacion>(`${API}/rutinas/admin/recomendaciones/${rec.id}/`, { activa: !rec.activa }).subscribe({
      next: actualizada => this.recomendaciones.update(lista =>
        lista.map(r => r.id === actualizada.id ? actualizada : r)
      ),
    });
  }

  protected eliminar(rec: Recomendacion): void {
    if (!confirm(`¿Eliminar "${rec.titulo}"?`)) return;
    this.http.delete(`${API}/rutinas/admin/recomendaciones/${rec.id}/`).subscribe({
      next: () => this.recomendaciones.update(lista => lista.filter(r => r.id !== rec.id)),
    });
  }

  protected thumbnailUrl(url: string): string | null {
    if (!url) return null;
    const m = url.match(/(?:youtube\.com\/watch\?v=|youtu\.be\/)([^&\n?#]+)/);
    return m ? `https://img.youtube.com/vi/${m[1]}/mqdefault.jpg` : null;
  }

  protected categoriaBadge(cat: string): string {
    const map: Record<string, string> = {
      tecnica:   'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300',
      fisico:    'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300',
      nutricion: 'bg-orange-100 dark:bg-orange-900/30 text-orange-700 dark:text-orange-300',
      mental:    'bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300',
      general:   'bg-gray-100 dark:bg-dark-700 text-gray-600 dark:text-gray-400',
    };
    return map[cat] ?? map['general'];
  }

  protected categoriaLabel(cat: string): string {
    return this.categorias.find(c => c.value === cat)?.label ?? cat;
  }
}
