import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { ButtonModule } from 'primeng/button';
import { MessageModule } from 'primeng/message';

import { ProcesoService } from '../core/services/proceso';
import { mensajeError } from '../shared/errores';
import { diasEntre, formatearFecha, hoyISO, sumarDias } from '../shared/fechas';
import { PeriodoPlan } from '../shared/periodo-plan/periodo-plan';
import { Portada } from '../shared/portada/portada';

type Paso = 'pregunta' | 'seguir' | 'cambios';

/** Llegó la fecha de control: ¿se sigue con el proceso o hay cambios? */
@Component({
  selector: 'app-control',
  templateUrl: './control.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [Portada, RouterLink, ButtonModule, MessageModule, PeriodoPlan],
})
export class Control {
  private procesos = inject(ProcesoService);
  private router = inject(Router);

  protected proceso = this.procesos.vigente;
  protected paso = signal<Paso>('pregunta');
  protected fecha = signal<string | null | undefined>(undefined);
  protected guardando = signal(false);
  protected error = signal('');
  protected formatearFecha = formatearFecha;

  /** Desde cuándo corría el periodo que acaba de terminar. */
  private inicioDelPeriodo = computed(() => {
    const p = this.proceso();
    if (!p) return hoyISO();
    return p.renovaciones.at(-1)?.cambiada_el ?? p.fecha_inicio;
  });

  /** Lo que se sugiere: otro periodo igual de largo. */
  protected sugerida = computed(() => {
    const p = this.proceso();
    if (!p?.fecha_fin_plan) return null;
    const dias = diasEntre(this.inicioDelPeriodo(), p.fecha_fin_plan);
    if (dias < 7) return null;
    const semanas = Math.round(dias / 7);
    return {
      titulo: `Igual: ${semanas} ${semanas === 1 ? 'semana' : 'semanas'}`,
      fecha: sumarDias(hoyISO(), dias),
    };
  });

  protected seguir(): void {
    const p = this.proceso();
    const fecha = this.fecha();
    if (!p || fecha === undefined) return;
    this.guardando.set(true);
    this.error.set('');
    this.procesos.renovar(p.id, fecha).subscribe({
      next: () => {
        this.guardando.set(false);
        void this.router.navigate(['/inicio']);
      },
      error: (err) => {
        this.error.set(mensajeError(err, 'No pudimos guardar el nuevo periodo.'));
        this.guardando.set(false);
      },
    });
  }
}
