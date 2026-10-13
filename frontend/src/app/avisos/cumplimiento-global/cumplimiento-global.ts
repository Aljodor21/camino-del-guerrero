import {
  ChangeDetectionStrategy,
  Component,
  OnInit,
  computed,
  inject,
  signal,
} from '@angular/core';
import { RouterLink } from '@angular/router';
import { ButtonModule } from 'primeng/button';
import { MessageModule } from 'primeng/message';

import { CumplimientoGlobal, DiaCumplimiento, Sueno } from '../../core/models/avisos.model';
import { AvisosService } from '../../core/services/avisos';
import { clasesChip } from '../../shared/chip';
import { mensajeError } from '../../shared/errores';
import { aISO, fechaLocal, formatearFecha, hoyISO, sumarDias } from '../../shared/fechas';

type Periodo = 'dia' | 'semana' | 'mes' | 'trimestre';

const PERIODOS: { id: Periodo; label: string }[] = [
  { id: 'dia', label: 'Día' },
  { id: 'semana', label: 'Semana' },
  { id: 'mes', label: 'Mes' },
  { id: 'trimestre', label: 'Trimestre' },
];

const RADIO = 42;
const PERIMETRO = 2 * Math.PI * RADIO;

/** Primer y último día del periodo que contiene `ancla`. */
function rangoDe(periodo: Periodo, ancla: string): { desde: string; hasta: string } {
  const f = fechaLocal(ancla);
  switch (periodo) {
    case 'dia':
      return { desde: ancla, hasta: ancla };
    case 'semana': {
      const lunes = sumarDias(ancla, -((f.getDay() + 6) % 7));
      return { desde: lunes, hasta: sumarDias(lunes, 6) };
    }
    case 'mes':
      return {
        desde: aISO(new Date(f.getFullYear(), f.getMonth(), 1)),
        hasta: aISO(new Date(f.getFullYear(), f.getMonth() + 1, 0)),
      };
    case 'trimestre': {
      const inicio = Math.floor(f.getMonth() / 3) * 3;
      return {
        desde: aISO(new Date(f.getFullYear(), inicio, 1)),
        hasta: aISO(new Date(f.getFullYear(), inicio + 3, 0)),
      };
    }
  }
}

/** Cuánto se cumplió: el día, la semana, el mes o el trimestre, y dónde se falló. */
@Component({
  selector: 'app-cumplimiento-global',
  templateUrl: './cumplimiento-global.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [ButtonModule, MessageModule, RouterLink],
})
export class CumplimientoGlobalVista implements OnInit {
  private servicio = inject(AvisosService);

  protected periodos = PERIODOS;
  protected clasesChip = clasesChip;
  protected radio = RADIO;
  protected perimetro = PERIMETRO;

  protected periodo = signal<Periodo>('dia');
  protected ancla = signal(hoyISO());
  protected datos = signal<CumplimientoGlobal | null>(null);
  /** Cuánto durmió en el mismo periodo, a partir de las horas de acostarse y levantarse. */
  protected sueno = signal<Sueno | null>(null);
  protected cargando = signal(false);
  protected error = signal('');
  protected elegido = signal<string | null>(null);

  protected rango = computed(() => rangoDe(this.periodo(), this.ancla()));
  protected esUnDia = computed(() => this.periodo() === 'dia');
  protected hayMasAdelante = computed(() => this.rango().hasta < hoyISO());

  protected titulo = computed(() => {
    const { desde, hasta } = this.rango();
    switch (this.periodo()) {
      case 'dia':
        return desde === hoyISO() ? 'Hoy' : formatearFecha(desde, 'larga');
      case 'semana':
        return `${formatearFecha(desde, 'grafica')} – ${formatearFecha(hasta, 'grafica')}`;
      case 'mes':
        return fechaLocal(desde).toLocaleDateString('es-CO', { month: 'long', year: 'numeric' });
      case 'trimestre':
        return `${fechaLocal(desde).toLocaleDateString('es-CO', { month: 'short' })} – ${fechaLocal(hasta).toLocaleDateString('es-CO', { month: 'short', year: 'numeric' })}`;
    }
  });

  /** Los días que tienen algo para medir. */
  protected dias = computed(() => this.datos()?.dias ?? []);
  protected diaElegido = computed<DiaCumplimiento | null>(() => {
    const dias = this.dias();
    const f = this.esUnDia() ? this.rango().desde : this.elegido();
    return dias.find((d) => d.fecha === f) ?? null;
  });
  /** Casillas vacías antes del primer día para que cada día caiga en su columna (lunes primero). */
  protected huecos = computed(() => {
    const primero = this.dias()[0];
    return primero ? Array.from({ length: (fechaLocal(primero.fecha).getDay() + 6) % 7 }) : [];
  });
  /** Dónde se falló, lo más reciente primero. */
  protected fallas = computed(() =>
    [...this.dias()].filter((d) => !d.es_hoy && d.bloques.some((b) => b.faltas.length)).reverse(),
  );
  /** Hay algún día ya cerrado: hoy no cuenta hasta que termine. */
  protected hayDiasCerrados = computed(() => this.dias().some((d) => !d.es_hoy));
  protected trazo = computed(() => {
    const p = this.datos()?.porcentaje;
    return p == null ? 0 : (Math.min(p, 100) / 100) * PERIMETRO;
  });

  ngOnInit(): void {
    this.cargar();
  }

  protected elegirPeriodo(p: Periodo): void {
    this.periodo.set(p);
    this.ancla.set(hoyISO());
    this.elegido.set(null);
    this.cargar();
  }

  protected mover(sentido: -1 | 1): void {
    const f = fechaLocal(this.rango().desde);
    switch (this.periodo()) {
      case 'dia':
      case 'semana':
        this.ancla.set(sumarDias(this.rango().desde, sentido * (this.esUnDia() ? 1 : 7)));
        break;
      case 'mes':
        this.ancla.set(aISO(new Date(f.getFullYear(), f.getMonth() + sentido, 1)));
        break;
      case 'trimestre':
        this.ancla.set(aISO(new Date(f.getFullYear(), f.getMonth() + sentido * 3, 1)));
        break;
    }
    this.elegido.set(null);
    this.cargar();
  }

  protected volverAHoy(): void {
    this.ancla.set(hoyISO());
    this.elegido.set(null);
    this.cargar();
  }

  protected elegirDia(fecha: string): void {
    this.elegido.set(this.elegido() === fecha ? null : fecha);
  }

  protected cargar(): void {
    const { desde, hasta } = this.rango();
    this.cargando.set(true);
    this.error.set('');
    this.servicio.sueno(desde, hasta).subscribe({
      next: (s) => this.sueno.set(s),
      error: () => this.sueno.set(null),
    });
    this.servicio.cumplimiento(desde, hasta).subscribe({
      next: (d) => {
        this.datos.set(d);
        this.cargando.set(false);
        // Hoy (o el último día) queda a la vista en vez de pedirle al usuario que toque uno.
        if (!this.esUnDia() && d.dias.length && this.elegido() === null) {
          this.elegido.set(d.dias.at(-1)!.fecha);
        }
      },
      error: (e) => {
        this.cargando.set(false);
        this.error.set(mensajeError(e, 'No pudimos calcular tu cumplimiento.'));
      },
    });
  }

  /** «30 min antes de lo previsto», «15 min después…» o «a la hora prevista». */
  protected frenteALoPrevisto(min: number): string {
    if (Math.abs(min) < 5) return 'a la hora prevista';
    const m = Math.abs(min);
    return `${m >= 60 ? this.duracion(m / 60) : m + ' min'} ${min < 0 ? 'antes' : 'después'} de lo previsto`;
  }

  /** 7,75 → «7 h 45 min». */
  protected duracion(horas: number): string {
    const minutos = Math.round(horas * 60);
    const h = Math.floor(minutos / 60);
    const m = minutos % 60;
    return m ? `${h} h ${m} min` : `${h} h`;
  }

  /** El alto de la barra de una noche: 10 horas llenan la barra. */
  protected altoNoche(horas: number): number {
    return Math.max(6, Math.min(100, (horas / 10) * 100));
  }

  protected fecha(iso: string): string {
    return formatearFecha(iso, 'dia');
  }

  protected numero(iso: string): number {
    return fechaLocal(iso).getDate();
  }

  /** Color según qué tan bien va: verde desde la meta, ámbar a medias, rojo si poco. */
  protected tono(p: number | null): string {
    if (p === null) return 'text-gray-400 dark:text-gray-500';
    if (p >= (this.datos()?.umbral_racha ?? 80)) return 'text-emerald-600 dark:text-emerald-400';
    return p >= 50 ? 'text-amber-600 dark:text-amber-400' : 'text-guerrero-red';
  }

  protected fondo(p: number | null): string {
    if (p === null) return 'bg-gray-200 dark:bg-dark-700';
    if (p >= (this.datos()?.umbral_racha ?? 80)) return 'bg-emerald-500';
    return p >= 50 ? 'bg-amber-500' : 'bg-guerrero-red';
  }

  protected trazoColor(p: number | null): string {
    if (p === null) return 'stroke-gray-300 dark:stroke-dark-600';
    if (p >= (this.datos()?.umbral_racha ?? 80)) return 'stroke-emerald-500';
    return p >= 50 ? 'stroke-amber-500' : 'stroke-guerrero-red';
  }

  protected mensaje(): string {
    const d = this.datos();
    if (!d) return '';
    if (d.porcentaje === null) {
      return this.esUnDia()
        ? 'Aún no hay nada que medir este día.'
        : 'Todavía no hay días para medir en este periodo.';
    }
    const solo = this.dias().length > 0 && this.dias().every((x) => !x.en_proceso);
    const previo = solo ? ' Tu proceso aún no empieza: por ahora cuentan el agua y dormir.' : '';
    if (this.esUnDia()) {
      const hoy = this.rango().desde === hoyISO();
      if (d.porcentaje >= 100) return `Día completo: lo cumpliste todo.${previo}`;
      return hoy
        ? `Llevas el ${d.porcentaje} % de lo que toca hoy.${previo}`
        : `Cumpliste el ${d.porcentaje} % de lo que tocaba ese día.${previo}`;
    }
    return `Cumpliste el ${d.porcentaje} % en promedio; ${d.dias_cumplidos} de ${d.dias.length} ${d.dias.length === 1 ? 'día llegó' : 'días llegaron'} al ${d.umbral_racha} % o más.${previo}`;
  }
}
