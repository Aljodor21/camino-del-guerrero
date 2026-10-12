import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  OnInit,
  computed,
  inject,
  signal,
} from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { ButtonModule } from 'primeng/button';
import { InputTextModule } from 'primeng/inputtext';
import { MessageModule } from 'primeng/message';

import { Aviso, TipoAviso } from '../core/models/avisos.model';
import { AvisosService } from '../core/services/avisos';
import { PushService } from '../core/services/push';
import { TIEMPOS_COMIDA } from '../core/constants/nutricion';
import { TiempoComida } from '../core/models/minuta.model';
import { clasesChip } from '../shared/chip';
import { TamanoVaso, vasoValido } from '../shared/tamano-vaso';
import { parsearDecimal } from '../shared/decimal-input';
import { mensajeError } from '../shared/errores';
import { formatearHora, formatearNumero } from '../shared/fechas';
import { Pestana, Pestanas } from '../shared/pestanas/pestanas';
import { guardarSeccionEnUrl } from '../shared/seccion-en-url';

const ICONOS: Record<TipoAviso, string> = {
  agua: 'pi pi-circle-fill',
  toma: 'pi pi-box',
  dormir: 'pi pi-moon',
  entreno: 'pi pi-bolt',
  recordatorio: 'pi pi-calendar',
  comida: 'pi pi-camera',
  proceso: 'pi pi-flag',
};

/** El color de cada tipo de aviso: así se distingue de un vistazo qué es cada uno. */
const ESTILOS: Record<TipoAviso, string> = {
  agua: 'bg-sky-500/15 text-sky-600 dark:text-sky-400',
  toma: 'bg-amber-500/15 text-amber-600 dark:text-amber-400',
  dormir: 'bg-indigo-500/15 text-indigo-600 dark:text-indigo-400',
  entreno: 'bg-guerrero-red/15 text-guerrero-red',
  recordatorio: 'bg-violet-500/15 text-violet-600 dark:text-violet-400',
  comida: 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400',
  proceso: 'bg-slate-500/15 text-slate-600 dark:text-slate-300',
};

const TIPOS: { id: TipoAviso; label: string }[] = [
  { id: 'agua', label: 'Agua' },
  { id: 'toma', label: 'Proteína' },
  { id: 'dormir', label: 'Dormir' },
  { id: 'entreno', label: 'Entreno' },
  { id: 'recordatorio', label: 'Agenda' },
  { id: 'comida', label: 'Comidas' },
  { id: 'proceso', label: 'Control' },
];

/** La bandeja: lo pendiente solo sale cuando se confirma. Además, cómo va el día y los ajustes. */
import { Ayuda } from '../shared/ayuda/ayuda';
import { CumplimientoGlobalVista } from './cumplimiento-global/cumplimiento-global';

type Seccion = 'pendientes' | 'dia' | 'cumplimiento' | 'ajustes';
const SECCIONES: Seccion[] = ['pendientes', 'dia', 'cumplimiento', 'ajustes'];

@Component({
  selector: 'app-avisos',
  templateUrl: './avisos.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    Ayuda,
    CumplimientoGlobalVista,
    Pestanas,
    RouterLink,
    ButtonModule,
    InputTextModule,
    MessageModule,
    TamanoVaso,
  ],
})
export class Avisos implements OnInit {
  private destroyRef = inject(DestroyRef);
  private ruta = inject(ActivatedRoute);

  protected seccion = signal<Seccion>(
    SECCIONES.find((x) => x === this.ruta.snapshot.queryParamMap.get('seccion')) ?? 'pendientes',
  );
  protected pestanas = computed((): Pestana<Seccion>[] => [
    {
      id: 'pendientes',
      label: 'Pendientes',
      icon: 'pi pi-inbox',
      contador: this.pendientes().length,
    },
    { id: 'dia', label: 'Tu día', icon: 'pi pi-sun' },
    { id: 'cumplimiento', label: 'Cumplimiento', icon: 'pi pi-chart-pie' },
    { id: 'ajustes', label: 'Ajustes', icon: 'pi pi-sliders-h' },
  ]);

  constructor() {
    guardarSeccionEnUrl(this.seccion);
  }
  protected servicio = inject(AvisosService);
  protected push = inject(PushService);

  protected iconos = ICONOS;
  protected estilos = ESTILOS;
  protected tipos = TIPOS;
  protected comidas = TIEMPOS_COMIDA;
  protected clasesChip = clasesChip;
  protected hora = formatearHora;
  protected num = formatearNumero;

  protected error = signal('');
  protected guardando = signal(false);
  protected confirmando = signal<number | null>(null);
  protected guardado = signal(false);

  // ── Ajustes (agua, horas y qué avisos llegan) ─────────────────────
  protected litros = signal<number | null>(null);
  protected vasoMl = signal<number | null>(250);
  /** Qué se anotó con el último clic ("Vaso anotado a las 8:15 a. m."). */
  protected anotado = signal('');
  protected levantarse = signal('');
  protected dormir = signal('');
  protected entreno = signal('');
  protected apagados = signal<TipoAviso[]>([]);

  protected vasosMeta = computed(() => {
    const l = this.litros();
    return l === null || Number.isNaN(l) || !vasoValido(this.vasoMl())
      ? null
      : Math.ceil((l * 1000) / (this.vasoMl() as number));
  });
  protected ajustesValidos = computed(() => {
    const l = this.litros();
    const aguaBien = l === null || (!Number.isNaN(l) && l >= 0.25 && l <= 8);
    return (
      aguaBien &&
      vasoValido(this.vasoMl()) &&
      !(this.dormir() && this.dormir() === this.levantarse())
    );
  });

  /** Se actualiza cada minuto para que "hace 5 min" no se quede viejo. */
  private ahora = signal(Date.now());
  /** Lo más nuevo arriba, como una bandeja de notificaciones. */
  protected pendientes = computed(() =>
    [...this.servicio.avisos()].sort(
      (a, b) => new Date(b.programada_para).getTime() - new Date(a.programada_para).getTime(),
    ),
  );
  protected hoy = this.servicio.hoy;
  protected faltanVasos = computed(() => {
    const a = this.hoy()?.agua;
    return a ? Math.max(0, a.meta - a.vasos) : 0;
  });

  ngOnInit(): void {
    const reloj = window.setInterval(() => this.ahora.set(Date.now()), 60000);
    this.destroyRef.onDestroy(() => window.clearInterval(reloj));
    this.servicio.cargar().subscribe({
      error: (e) => this.error.set(mensajeError(e, 'No pudimos cargar tus avisos.')),
    });
    this.servicio.cargarHoy().subscribe({ error: () => undefined });
    this.servicio.cargarHabitos().subscribe({
      next: (h) => {
        this.litros.set(h.agua_ml === null ? null : h.agua_ml / 1000);
        this.vasoMl.set(h.vaso_ml);
        this.levantarse.set(h.hora_levantarse?.slice(0, 5) ?? '');
        this.dormir.set(h.hora_dormir?.slice(0, 5) ?? '');
        this.entreno.set(h.hora_entreno?.slice(0, 5) ?? '');
        this.apagados.set(h.avisos_apagados);
      },
      error: () => undefined,
    });
    void this.push.iniciar();
  }

  /** "ahora", "hace 12 min", "hace 2 h" o la hora si ya pasó más de medio día. */
  protected cuando(aviso: Aviso): string {
    const minutos = Math.floor((this.ahora() - new Date(aviso.programada_para).getTime()) / 60000);
    if (minutos < 1) return 'Ahora';
    if (minutos < 60) return `Hace ${minutos} min`;
    if (minutos < 12 * 60) return `Hace ${Math.floor(minutos / 60)} h`;
    return this.tiempo(aviso);
  }

  protected tiempo(aviso: Aviso): string {
    return new Date(aviso.programada_para).toLocaleTimeString('es-CO', {
      hour: 'numeric',
      minute: '2-digit',
    });
  }

  protected nombreComida(tiempo: string, hora?: string | null): string {
    if (tiempo.startsWith('otro')) return `Otra toma${hora ? ` · ${formatearHora(hora)}` : ''}`;
    return this.comidas[tiempo as TiempoComida]?.label ?? tiempo;
  }

  protected confirmar(aviso: Aviso): void {
    this.confirmando.set(aviso.id);
    this.error.set('');
    this.servicio.confirmar(aviso).subscribe({
      next: () => {
        this.confirmando.set(null);
        this.servicio.cargarHoy().subscribe({ error: () => undefined });
      },
      error: (e) => {
        this.confirmando.set(null);
        this.error.set(mensajeError(e, 'No pudimos confirmarlo. Intenta de nuevo.'));
      },
    });
  }

  /** Un vaso que ya te tomaste, sin esperar el aviso. */
  protected unVaso(): void {
    this.error.set('');
    this.servicio.registrarAgua().subscribe({
      next: (r) => {
        this.anotado.set(`Vaso de ${r.ml} ml anotado a las ${this.horaDe(r.momento)}`);
        this.servicio.cargarHoy().subscribe({ error: () => undefined });
        this.servicio.cargar().subscribe({ error: () => undefined });
      },
      error: (e) => this.error.set(mensajeError(e, 'No pudimos anotar el vaso.')),
    });
  }

  /** Hora local de un instante ("8:15 a. m."). */
  protected horaDe(instante: string): string {
    return new Date(instante).toLocaleTimeString('es-CO', { hour: 'numeric', minute: '2-digit' });
  }

  protected leerLitros(texto: string): void {
    this.litros.set(parsearDecimal(texto));
  }

  protected alternarTipo(tipo: TipoAviso): void {
    this.apagados.update((l) => (l.includes(tipo) ? l.filter((t) => t !== tipo) : [...l, tipo]));
  }

  protected guardar(): void {
    if (!this.ajustesValidos()) return;
    this.guardando.set(true);
    this.guardado.set(false);
    this.error.set('');
    const l = this.litros();
    this.servicio
      .guardarHabitos({
        agua_ml: l === null ? null : Math.round(l * 1000),
        vaso_ml: this.vasoMl() ?? 250,
        hora_levantarse: this.levantarse() || null,
        hora_dormir: this.dormir() || null,
        hora_entreno: this.entreno() || null,
        avisos_apagados: this.apagados(),
      })
      .subscribe({
        next: () => {
          this.guardando.set(false);
          this.guardado.set(true);
          this.servicio.cargarHoy().subscribe({ error: () => undefined });
        },
        error: (e) => {
          this.guardando.set(false);
          this.error.set(mensajeError(e, 'No pudimos guardar tus ajustes.'));
        },
      });
  }

  protected async alternarPush(): Promise<void> {
    this.error.set('');
    try {
      if (this.push.estado() === 'activo') await this.push.desactivar();
      else await this.push.activar();
    } catch {
      this.error.set('No pudimos activar las notificaciones en este dispositivo.');
    }
  }
}
