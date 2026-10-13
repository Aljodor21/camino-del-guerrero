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
import { Anillo } from '../../shared/anillo/anillo';
import { mensajeError } from '../../shared/errores';
import { formatearFecha, hoyISO, sumarDias } from '../../shared/fechas';
import { Guerrero, estadoDe } from '../../shared/guerrero/guerrero';
import { Medalla } from '../../shared/medalla/medalla';

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
  imports: [ButtonModule, MessageModule, Anillo, Guerrero, Medalla],
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
    estadoDe(this.datos()?.hoy?.porcentaje, this.datos()?.racha.umbral),
  );
  protected frase = computed(() => {
    if (!this.datos()) return 'Cargando tus logros…';
    const p = this.datos()?.hoy?.porcentaje;
    if (p == null) return 'Cuando empieces a registrar, el guerrero se pone en marcha.';
    return {
      descansa: 'El guerrero descansa: aún queda día para sumar.',
      firme: 'Va firme. Un registro más y se acerca a la meta.',
      celebra: 'Meta del día cumplida. Así se camina.',
    }[this.estado()];
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
    if (p >= (this.datos()?.racha.umbral ?? 80)) return '#27ae60';
    return p >= 50 ? '#f39c12' : '#c0392b';
  }

  protected diferencia(c: Capitulo): string {
    const d = c.diferencia;
    if (d === null || d === 0) return '';
    return d > 0
      ? `Subiste ${d} ${d === 1 ? 'punto' : 'puntos'} frente a la semana anterior.`
      : `Bajaste ${-d} ${d === -1 ? 'punto' : 'puntos'} frente a la semana anterior.`;
  }
}
