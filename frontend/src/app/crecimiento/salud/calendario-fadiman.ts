import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';

import { DiaCalendario, EstadoSalud } from '../../core/models/salud.model';
import { diasEntre, fechaLocal, formatearFecha } from '../../shared/fechas';

/** Los tres días del ciclo, como en la infografía del protocolo. */
const ETAPAS = [
  { dia: 1, nombre: 'Toma', detalle: 'Por la mañana', icono: 'pi pi-sun' },
  { dia: 2, nombre: 'Transición', detalle: 'Observas ánimo y energía', icono: 'pi pi-eye' },
  { dia: 3, nombre: 'Normal', detalle: 'Vuelves a tu estado basal', icono: 'pi pi-moon' },
];

const DESCRIPCION_TOMA: Record<string, string> = {
  hecha: 'toma anotada',
  perdida: 'toma sin anotar',
  pendiente: 'toca la toma',
  antes: 'toma de antes de registrarte',
};

/**
 * El dibujo del protocolo: desde cuándo va, la vuelta en curso (ciclo y descanso) con su línea de tiempo, los
 * tres días del ciclo y el calendario día por día con lo que tocaba y lo que se hizo.
 */
@Component({
  selector: 'app-calendario-fadiman',
  templateUrl: './calendario-fadiman.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class CalendarioFadiman {
  readonly estado = input.required<EstadoSalud>();

  protected etapas = ETAPAS;
  protected fecha = (iso: string) => formatearFecha(iso, 'corta');
  protected corta = (iso: string) => formatearFecha(iso, 'grafica');

  protected cal = computed(() => this.estado().calendario ?? null);
  protected yaEmpezo = computed(() => {
    const e = this.estado();
    return !!e.empezo && e.empezo <= e.hoy;
  });
  protected diaDeHoy = computed(() =>
    this.estado().dia?.fase === 'ciclo' ? this.estado().dia!.dia : null,
  );
  protected diasDesdeQueEmpezo = computed(() => {
    const e = this.estado();
    return e.empezo ? diasEntre(e.empezo, e.hoy) + 1 : 0;
  });

  protected hayAntes = computed(() => (this.cal()?.dias ?? []).some((d) => d.toma === 'antes'));

  /** Las semanas de la vuelta, de 7 en 7, con su nombre. */
  protected semanas = computed(() => {
    const c = this.cal();
    if (!c) return [];
    const ciclo = this.estado().ajustes?.semanas_ciclo ?? 4;
    const filas: { nombre: string; descanso: boolean; dias: DiaCalendario[] }[] = [];
    for (let i = 0; i < c.dias.length; i += 7) {
      const n = i / 7 + 1;
      filas.push({
        nombre: n <= ciclo ? `Semana ${n}` : `Descanso ${n - ciclo}`,
        descanso: n > ciclo,
        dias: c.dias.slice(i, i + 7),
      });
    }
    return filas;
  });

  /** Dónde va hoy en la línea de la vuelta (0 a 100) y cuánto ocupa el ciclo. */
  protected linea = computed(() => {
    const c = this.cal();
    if (!c) return null;
    const total = c.dias.length;
    const ciclo = diasEntre(c.desde, c.fin_ciclo) + 1;
    const hoy = diasEntre(c.desde, this.estado().hoy);
    return {
      ciclo: (100 * ciclo) / total,
      hoy: hoy >= 0 && hoy < total ? (100 * (hoy + 0.5)) / total : null,
    };
  });

  protected numero(iso: string): number {
    return fechaLocal(iso).getDate();
  }

  protected claseDia(d: DiaCalendario): string {
    const base =
      'relative aspect-square rounded-md flex items-center justify-center text-[11px] tabular-nums';
    const anillo = d.hoy ? ' ring-2 ring-guerrero-red ring-offset-1 dark:ring-offset-dark-800' : '';
    if (d.fase === 'descanso')
      return `${base}${anillo} bg-gray-100 dark:bg-dark-700 text-gray-400 dark:text-gray-500`;
    switch (d.toma) {
      case 'hecha':
        return `${base}${anillo} bg-emerald-600 text-white font-semibold`;
      case 'perdida':
        return `${base}${anillo} bg-red-50 dark:bg-red-500/10 text-red-700 dark:text-red-300 border border-red-300 dark:border-red-500/40`;
      case 'pendiente':
        return `${base}${anillo} border-2 border-emerald-600 text-emerald-700 dark:text-emerald-300 font-semibold`;
      case 'antes':
        return `${base}${anillo} bg-gray-200 dark:bg-dark-600 text-gray-500 dark:text-gray-400`;
    }
    return d.dia === 2
      ? `${base}${anillo} bg-sky-100 dark:bg-sky-500/15 text-sky-800 dark:text-sky-200`
      : `${base}${anillo} bg-sky-50 dark:bg-sky-500/5 text-sky-700 dark:text-sky-300`;
  }

  protected etiquetaDia(d: DiaCalendario): string {
    const partes = [formatearFecha(d.fecha, 'larga')];
    if (d.fase === 'descanso') partes.push('descanso');
    else partes.push(`día ${d.dia}`);
    if (d.toma) partes.push(DESCRIPCION_TOMA[d.toma]);
    if (d.observacion) partes.push('anotaste cómo estabas');
    if (d.hoy) partes.push('hoy');
    return partes.join(', ');
  }
}
