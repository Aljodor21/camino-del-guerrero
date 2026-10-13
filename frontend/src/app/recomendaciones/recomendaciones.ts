import { Component, ChangeDetectionStrategy, inject, signal, computed, OnInit } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { DomSanitizer, SafeResourceUrl } from '@angular/platform-browser';
import { ProgressSpinnerModule } from 'primeng/progressspinner';

import { Recomendacion } from '../core/models/rutina.model';
import { environment } from '../../environments/environment';
import { Portada } from '../shared/portada/portada';
import { QueEs } from '../shared/que-es/que-es';

const API = environment.apiUrl;

const CATEGORIAS: Record<string, { label: string; badge: string }> = {
  tecnica:   { label: 'Técnica',   badge: 'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300' },
  fisico:    { label: 'Físico',    badge: 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300' },
  nutricion: { label: 'Nutrición', badge: 'bg-orange-100 dark:bg-orange-900/30 text-orange-700 dark:text-orange-300' },
  mental:    { label: 'Mental',    badge: 'bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300' },
  general:   { label: 'General',   badge: 'bg-gray-100 dark:bg-dark-700 text-gray-600 dark:text-gray-400' },
};

@Component({
  selector: 'app-recomendaciones',
  templateUrl: './recomendaciones.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [QueEs, Portada, ProgressSpinnerModule],
})
export class Recomendaciones implements OnInit {
  private http      = inject(HttpClient);
  private sanitizer = inject(DomSanitizer);

  protected reproduciendo = signal<number | null>(null);

  protected recomendaciones = signal<Recomendacion[]>([]);
  protected loading         = signal(true);
  protected filtro          = signal<string>('todos');

  protected filtros = [
    { label: 'Todos',      value: 'todos'    },
    { label: 'Técnica',    value: 'tecnica'  },
    { label: 'Físico',     value: 'fisico'   },
    { label: 'Nutrición',  value: 'nutricion'},
    { label: 'Mental',     value: 'mental'   },
    { label: 'General',    value: 'general'  },
  ];

  protected filtradas = computed(() => {
    const f = this.filtro();
    return f === 'todos'
      ? this.recomendaciones()
      : this.recomendaciones().filter(r => r.categoria === f);
  });

  ngOnInit(): void {
    this.http.get<Recomendacion[]>(`${API}/rutinas/recomendaciones/`).subscribe({
      next: data => { this.recomendaciones.set(data); this.loading.set(false); },
      error: ()   => this.loading.set(false),
    });
  }

  protected thumbnailUrl(url: string): string | null {
    if (!url) return null;
    const m = url.match(/(?:youtube\.com\/watch\?v=|youtu\.be\/)([^&\n?#]+)/);
    return m ? `https://img.youtube.com/vi/${m[1]}/mqdefault.jpg` : null;
  }

  protected embedUrl(url: string): SafeResourceUrl | null {
    if (!url) return null;
    const m = url.match(/(?:youtube\.com\/watch\?v=|youtu\.be\/)([^&\n?#]+)/);
    if (!m) return null;
    return this.sanitizer.bypassSecurityTrustResourceUrl(
      `https://www.youtube.com/embed/${m[1]}?autoplay=1&rel=0`
    );
  }

  protected reproducir(id: number): void {
    this.reproduciendo.set(id);
  }

  protected badge(cat: string): string {
    return CATEGORIAS[cat]?.badge ?? CATEGORIAS['general'].badge;
  }

  protected label(cat: string): string {
    return CATEGORIAS[cat]?.label ?? cat;
  }
}
