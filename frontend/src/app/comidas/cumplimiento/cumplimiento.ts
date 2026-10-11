import {
  ChangeDetectionStrategy,
  Component,
  OnInit,
  computed,
  inject,
  signal,
} from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { MessageModule } from 'primeng/message';

import { GRUPOS_MINUTA, TIEMPOS_COMIDA, porcionesDe } from '../../core/constants/nutricion';
import { Cumplimiento, PeriodoCumplimiento } from '../../core/models/comidas.model';
import { TiempoComida } from '../../core/models/minuta.model';
import { ComidasService } from '../../core/services/comidas';
import { clasesChip } from '../../shared/chip';
import { mensajeError } from '../../shared/errores';
import { diasDesde, formatearFecha, formatearNumero } from '../../shared/fechas';
import { Portada } from '../../shared/portada/portada';
import { FotoComida } from '../foto-comida';

const PERIODOS: { id: PeriodoCumplimiento; label: string }[] = [
  { id: 'hoy', label: 'Hoy' },
  { id: 'semana', label: 'Esta semana' },
  { id: 'mes', label: 'Este mes' },
];

/** Radio y perímetro de la torta (el trazo se dibuja sobre un círculo de 42 de radio). */
const RADIO = 42;
const PERIMETRO = 2 * Math.PI * RADIO;

/** Qué tanto se cumple la minuta según lo que se ha contado, en una torta con el porcentaje. */
@Component({
  selector: 'app-cumplimiento',
  templateUrl: './cumplimiento.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [Portada, RouterLink, MessageModule, FotoComida],
})
export class CumplimientoPlan implements OnInit {
  private comidas = inject(ComidasService);
  private ruta = inject(ActivatedRoute);

  protected periodos = PERIODOS;
  protected clasesChip = clasesChip;
  protected perimetro = PERIMETRO;
  protected radio = RADIO;
  protected fecha = formatearFecha;
  protected num = formatearNumero;
  protected porciones = porcionesDe;
  protected tiempos = TIEMPOS_COMIDA;
  protected grupos = GRUPOS_MINUTA;

  protected periodo = signal<PeriodoCumplimiento>('semana');
  protected datos = signal<Cumplimiento | null>(null);
  protected cargando = signal(true);
  protected error = signal('');
  protected recienContada = signal<TiempoComida | null>(null);

  /** Largo del trazo de lo cumplido sobre el total del círculo. */
  protected trazoCumplido = computed(() => ((this.datos()?.porcentaje ?? 0) / 100) * PERIMETRO);
  protected faltoPorciones = computed(() => {
    const d = this.datos();
    return d ? Math.max(0, d.porciones_pedidas - d.porciones_comidas) : 0;
  });
  /** Las que aún se pueden contar (hasta 7 días atrás) y cuántas ya no. */
  protected porContar = computed(() =>
    (this.datos()?.sin_contar ?? []).filter((s) => diasDesde(s.fecha) <= 7),
  );
  protected perdidas = computed(
    () => (this.datos()?.sin_contar.length ?? 0) - this.porContar().length,
  );
  protected tono = computed(() => {
    const p = this.datos()?.porcentaje ?? null;
    if (p === null) return 'text-gray-400';
    return p >= 90 ? 'text-green-600 dark:text-green-400' : p >= 60 ? 'text-amber-600 dark:text-amber-400' : 'text-guerrero-red';
  });

  ngOnInit(): void {
    const listo = this.ruta.snapshot.queryParamMap.get('listo') as TiempoComida | null;
    if (listo && listo in TIEMPOS_COMIDA) this.recienContada.set(listo);
    this.cargar();
  }

  protected elegir(periodo: PeriodoCumplimiento): void {
    this.periodo.set(periodo);
    this.cargar();
  }

  private cargar(): void {
    this.cargando.set(true);
    this.error.set('');
    this.comidas.cumplimiento(this.periodo()).subscribe({
      next: (d) => {
        this.datos.set(d);
        this.cargando.set(false);
      },
      error: (e) => {
        this.cargando.set(false);
        this.error.set(mensajeError(e, 'No pudimos calcular tu cumplimiento.'));
      },
    });
  }
}
