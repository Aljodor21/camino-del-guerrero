import {
  ChangeDetectionStrategy,
  Component,
  OnInit,
  computed,
  inject,
  signal,
} from '@angular/core';
import { ButtonModule } from 'primeng/button';
import { MessageModule } from 'primeng/message';

import { Capitulo, Hito } from '../../core/models/logros.model';
import { AvisosService } from '../../core/services/avisos';
import { CelebracionesService } from '../../core/services/celebraciones';
import { mensajeError } from '../../shared/errores';
import { formatearFecha, hoyISO, sumarDias } from '../../shared/fechas';
import { Guerrero, estadoDe, pausaDeHoy } from '../../shared/guerrero/guerrero';
import { Medalla } from '../../shared/medalla/medalla';
import { QueEs } from '../../shared/que-es/que-es';

type Filtro = 'todos' | 'logrados' | 'pendientes';

const DIAS = ['L', 'M', 'M', 'J', 'V', 'S', 'D'];
/** Las siete estaciones del camino de la semana, zigzagueando de izquierda a derecha. */
const ESTACIONES = Array.from({ length: 7 }, (_, i) => ({
  x: 24 + i * (272 / 6),
  y: 42 + (i % 2 === 0 ? 14 : -14),
}));
const RUTA = ESTACIONES.map((p, i) => `${i ? 'L' : 'M'}${p.x.toFixed(1)} ${p.y}`).join(' ');

/** Tu racha, tus hitos y el capítulo de la semana: lo que se va construyendo al registrar. */
@Component({
  selector: 'app-logros',
  templateUrl: './logros.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [QueEs, ButtonModule, MessageModule, Guerrero, Medalla],
  styles: `
    .racha-numero {
      margin-top: 2px;
      font:
        700 clamp(120px, 40vw, 200px) / 0.8 'Barlow Condensed',
        'Barlow',
        sans-serif;
      letter-spacing: -0.02em;
      color: #d4af37;
      font-variant-numeric: tabular-nums;
      animation: llega 0.6s cubic-bezier(0.16, 1, 0.3, 1) backwards;
    }
    .racha-cero {
      color: #7b7067;
    }
    .racha-etiqueta {
      margin-top: 6px;
      font:
        600 26px / 1 'Barlow Condensed',
        'Barlow',
        sans-serif;
      color: #f6f1ea;
    }
    @keyframes llega {
      from {
        opacity: 0;
        transform: translateY(14px) scale(0.92);
      }
    }
    @media (prefers-reduced-motion: reduce) {
      .racha-numero {
        animation: none;
      }
    }
  `,
})
export class LogrosVista implements OnInit {
  private servicio = inject(AvisosService);
  protected celebraciones = inject(CelebracionesService);

  /** Los logros los trae el servicio de celebraciones: así hay una sola consulta y la misma foto en todas partes. */
  protected datos = this.celebraciones.logros;
  protected capitulo = signal<Capitulo | null>(null);
  protected lunes = signal<string | null>(null);
  protected error = signal('');
  protected filtro = signal<Filtro>('todos');

  protected dias = DIAS;
  protected estaciones = ESTACIONES;
  protected ruta = RUTA;

  protected estado = computed(() =>
    estadoDe(
      this.datos()?.hoy?.porcentaje,
      this.datos()?.racha.umbral,
      pausaDeHoy(this.datos()?.hoy, this.servicio.pausa() !== null),
    ),
  );
  /** El próximo hito de racha que aún no se logra. */
  protected proximoHito = computed(() =>
    (this.datos()?.hitos ?? []).find((h) => h.grupo === 'racha' && !h.logrado),
  );
  protected hoySalvaLaRacha = computed(() => {
    const d = this.datos();
    return !!d && (d.hoy?.porcentaje ?? 0) >= d.racha.umbral;
  });
  /** Qué falta hoy para que el día cuente: o que ya cuenta. */
  protected lineaDeHoy = computed(() => {
    const d = this.datos();
    const hoy = d?.hoy?.porcentaje;
    if (!d || hoy == null) return 'Cuando empieces a anotar, el día cuenta.';
    if (hoy >= d.racha.umbral) return `Hoy llevas ${hoy} %: el día de hoy cuenta para tu racha.`;
    return d.racha.actual > 0
      ? `Hoy llevas ${hoy} %. Te faltan ${d.racha.umbral - hoy} puntos para no perder tu racha.`
      : `Hoy llevas ${hoy} %. Llega al ${d.racha.umbral} % del día para empezar tu racha.`;
  });
  protected visibles = computed(() => {
    const hitos = this.datos()?.hitos ?? [];
    switch (this.filtro()) {
      case 'logrados':
        return hitos.filter((h) => h.logrado);
      case 'pendientes':
        return hitos.filter((h) => !h.logrado);
      default:
        return hitos;
    }
  });
  protected esActual = computed(() => this.capitulo()?.es_actual ?? true);

  ngOnInit(): void {
    void this.celebraciones.revisar(true);
    this.cargarCapitulo();
  }

  protected cargarCapitulo(lunes?: string): void {
    this.servicio.capitulo(lunes).subscribe({
      next: (c) => {
        this.capitulo.set(c);
        this.lunes.set(c.lunes);
      },
      error: (e) => this.error.set(mensajeError(e, 'No pudimos cargar el capítulo.')),
    });
  }

  protected semana(sentido: -1 | 1): void {
    const lunes = this.lunes();
    if (lunes) this.cargarCapitulo(sumarDias(lunes, 7 * sentido));
  }

  protected hayMasAdelante(): boolean {
    const c = this.capitulo();
    return !!c && c.domingo < hoyISO();
  }

  protected rotulo(c: Capitulo): string {
    return `${formatearFecha(c.lunes, 'grafica')} – ${formatearFecha(c.domingo, 'grafica')}`;
  }

  protected dia(iso: string): string {
    return formatearFecha(iso, 'dia');
  }

  protected progreso(h: Hito): string {
    return `${h.actual} de ${h.meta}`;
  }

  protected tono(p: number | null): string {
    if (p === null) return '#4a4039';
    const umbral = this.datos()?.racha.umbral ?? 50;
    if (p >= umbral) return '#27ae60';
    return p >= umbral / 2 ? '#f39c12' : '#c0392b';
  }

  protected diferencia(c: Capitulo): string {
    const d = c.diferencia;
    if (d === null || d === 0) return '';
    return d > 0
      ? `Subiste ${d} ${d === 1 ? 'punto' : 'puntos'} frente a la semana anterior.`
      : `Bajaste ${-d} ${d === -1 ? 'punto' : 'puntos'} frente a la semana anterior.`;
  }
}
