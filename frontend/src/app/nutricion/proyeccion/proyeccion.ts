import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { RouterLink } from '@angular/router';
import { MessageModule } from 'primeng/message';
import { ProgressSpinnerModule } from 'primeng/progressspinner';

import { environment } from '../../../environments/environment';
import { mensajeError } from '../../shared/errores';
import { formatearFecha, formatearNumero } from '../../shared/fechas';
import { Portada } from '../../shared/portada/portada';
import { IlustracionCambio } from './ilustracion';

interface Escenario {
  nombre: string;
  porcentaje: number;
  cambio_kg: number;
  /** Cuánto del cambio sería músculo y cuánto grasa y agua (con signo). */
  musculo_kg: number;
  grasa_kg: number;
  /** El cuerpo no da ese ritmo: la estimación se quedó en el tope semanal. */
  limitado: boolean;
  peso_final_kg: number;
}

interface ProyeccionPeso {
  peso_actual_kg: number;
  dias: number;
  fecha_control: string | null;
  kcal_plan: number;
  gasto_kcal: number;
  balance_kcal: number;
  solo_alimentacion: boolean;
  entrenamiento: { nombre: string; dias: number; duracion: number; kcal_dia: number } | null;
  proteina: { kcal: number; proteina_g: number } | null;
  cumplimiento: number | null;
  escenarios: Escenario[];
  factores: string[];
  supuestos: string[];
  limitado: boolean;
  aviso: string;
}

/** Cuánto podría cambiar el peso hasta el próximo control, uniendo todo lo que ya se sabe. */
@Component({
  selector: 'app-proyeccion',
  templateUrl: './proyeccion.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [Portada, RouterLink, MessageModule, ProgressSpinnerModule, IlustracionCambio],
})
export class Proyeccion implements OnInit {
  private http = inject(HttpClient);

  protected datos = signal<ProyeccionPeso | null>(null);
  protected cargando = signal(true);
  protected error = signal('');
  protected num = formatearNumero;
  protected fecha = formatearFecha;

  ngOnInit(): void {
    this.http.get<ProyeccionPeso>(`${environment.apiUrl}/nutricion/proyeccion/`).subscribe({
      next: (d) => {
        this.datos.set(d);
        this.cargando.set(false);
      },
      error: (err) => {
        this.error.set(mensajeError(err, 'No pudimos hacer la estimación.'));
        this.cargando.set(false);
      },
    });
  }

  /** "+2,3 kg" o "−0,8 kg". */
  protected cambio(kg: number): string {
    const signo = kg > 0 ? '+' : kg < 0 ? '−' : '';
    return `${signo}${formatearNumero(Math.abs(kg), 1)} kg`;
  }
}
