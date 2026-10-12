import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  OnInit,
  inject,
  signal,
} from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { ButtonModule } from 'primeng/button';
import { MessageModule } from 'primeng/message';

import { environment } from '../../../environments/environment';
import { VisorService } from '../../core/services/visor';
import { mensajeError } from '../../shared/errores';
import { formatearFecha, formatearNumero } from '../../shared/fechas';

const API = `${environment.apiUrl}/nutricion/ilustraciones`;

interface Ilustracion {
  id: number;
  creada: string;
  peso_base: number;
  cambio_kg: number;
  peso_final: number;
  limitado: boolean;
  dias: number;
  /** La foto de frente de la que parte; null si ya se borró. */
  foto_origen: number | null;
}

interface EstadoIlustraciones {
  disponible: boolean;
  restantes_hoy: number;
  ilustraciones: Ilustracion[];
}

/**
 * Una imagen orientativa del cambio estimado, hecha por OpenAI a partir de la foto de frente.
 * La foto solo se envía si la persona lo acepta; las imágenes son privadas.
 */
@Component({
  selector: 'app-ilustracion',
  templateUrl: './ilustracion.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [ButtonModule, MessageModule],
})
export class IlustracionCambio implements OnInit {
  private http = inject(HttpClient);
  private visor = inject(VisorService);

  protected estado = signal<EstadoIlustraciones | null>(null);
  /** Imágenes privadas ya pedidas: `i<id>` la ilustración, `f<id>` la foto de la que parte. */
  protected imagenes = signal<Record<string, string>>({});
  protected pidiendo = signal(false);
  protected acepta = signal(false);
  protected generando = signal(false);
  protected error = signal('');
  protected fecha = formatearFecha;
  protected num = formatearNumero;

  constructor() {
    inject(DestroyRef).onDestroy(() => Object.values(this.imagenes()).forEach(URL.revokeObjectURL));
  }

  ngOnInit(): void {
    this.cargar();
  }

  private cargar(): void {
    this.http.get<EstadoIlustraciones>(`${API}/`).subscribe({
      next: (e) => {
        this.estado.set(e);
        e.ilustraciones.forEach((i) => {
          this.traerImagen(`i${i.id}`, `${API}/${i.id}/imagen/`);
          if (i.foto_origen) {
            this.traerImagen(
              `f${i.foto_origen}`,
              `${environment.apiUrl}/progreso/fotos/${i.foto_origen}/`,
            );
          }
        });
      },
      error: () => this.estado.set(null),
    });
  }

  private traerImagen(clave: string, url: string): void {
    if (this.imagenes()[clave]) return;
    this.http.get(url, { responseType: 'blob' }).subscribe({
      next: (blob) => this.imagenes.update((m) => ({ ...m, [clave]: URL.createObjectURL(blob) })),
    });
  }

  protected ampliar(titulo: string, url: string): void {
    this.visor.abrirUrl(titulo, url);
  }

  protected generar(): void {
    if (!this.acepta()) return;
    this.generando.set(true);
    this.error.set('');
    this.http.post<Ilustracion>(`${API}/`, { consentimiento: true }).subscribe({
      next: () => {
        this.generando.set(false);
        this.pidiendo.set(false);
        this.acepta.set(false);
        this.cargar();
      },
      error: (err) => {
        this.error.set(mensajeError(err, 'No pudimos generar la imagen. Intenta de nuevo.'));
        this.generando.set(false);
      },
    });
  }

  protected borrar(id: number): void {
    this.http.delete(`${API}/${id}/imagen/`).subscribe({
      next: () => {
        const url = this.imagenes()[`i${id}`];
        if (url) URL.revokeObjectURL(url);
        this.imagenes.update(({ [`i${id}`]: _, ...resto }) => resto);
        this.cargar();
      },
    });
  }

  /** "+3,0 kg" o "−1,2 kg". */
  protected cambio(kg: number): string {
    return `${kg > 0 ? '+' : kg < 0 ? '−' : ''}${formatearNumero(Math.abs(kg), 1)} kg`;
  }
}
