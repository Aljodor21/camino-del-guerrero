import { Component, ChangeDetectionStrategy, computed, inject, output } from '@angular/core';
import { RouterLink } from '@angular/router';

import { AgendaService } from '../../core/services/agenda';
import { ProcesoService } from '../../core/services/proceso';
import { avanceProceso } from '../../shared/avance-proceso';
import { cuandoEs, diasEntre, formatearFecha, hoyISO } from '../../shared/fechas';

/** Dónde va el proceso en el tiempo y qué fecha importante sigue. */
@Component({
  selector: 'app-resumen-proceso',
  templateUrl: './resumen-proceso.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [RouterLink],
})
export class ResumenProceso {
  private procesos = inject(ProcesoService);
  private agenda = inject(AgendaService);

  readonly verAgenda = output<void>();

  protected formatearFecha = formatearFecha;
  protected cuandoEs = cuandoEs;

  protected proceso = this.procesos.vigente;
  protected proximo = this.agenda.proximo;

  protected avance = computed(() => {
    const p = this.proceso();
    return p ? avanceProceso(p) : null;
  });

  /** Semanas planeadas de un proceso que aún no inicia. */
  protected semanasPlan = computed(() => {
    const p = this.proceso();
    return p?.fecha_fin_plan ? Math.ceil((diasEntre(p.fecha_inicio, p.fecha_fin_plan) + 1) / 7) : null;
  });

  protected diasParaIniciar = computed(() => {
    const p = this.proceso();
    return p && p.estado === 'programado' ? diasEntre(hoyISO(), p.fecha_inicio) : null;
  });
}
