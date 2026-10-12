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
import { InputTextModule } from 'primeng/inputtext';
import { MessageModule } from 'primeng/message';

import { Aviso, TipoAviso } from '../core/models/avisos.model';
import { AvisosService } from '../core/services/avisos';
import { PushService } from '../core/services/push';
import { TIEMPOS_COMIDA } from '../core/constants/nutricion';
import { TiempoComida } from '../core/models/minuta.model';
import { clasesChip } from '../shared/chip';
import { parsearDecimal } from '../shared/decimal-input';
import { mensajeError } from '../shared/errores';
import { formatearHora, formatearNumero } from '../shared/fechas';
import { Portada } from '../shared/portada/portada';

const ICONOS: Record<TipoAviso, string> = {
  agua: 'pi pi-circle-fill',
  toma: 'pi pi-box',
  dormir: 'pi pi-moon',
  entreno: 'pi pi-bolt',
  recordatorio: 'pi pi-calendar',
  comida: 'pi pi-camera',
  proceso: 'pi pi-flag',
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
@Component({
  selector: 'app-avisos',
  templateUrl: './avisos.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [Portada, RouterLink, ButtonModule, InputTextModule, MessageModule],
})
export class Avisos implements OnInit {
  protected servicio = inject(AvisosService);
  protected push = inject(PushService);

  protected iconos = ICONOS;
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
  protected levantarse = signal('');
  protected dormir = signal('');
  protected entreno = signal('');
  protected apagados = signal<TipoAviso[]>([]);

  protected vasosMeta = computed(() => {
    const l = this.litros();
    return l === null || Number.isNaN(l) ? null : Math.ceil((l * 1000) / (this.servicio.hoy()?.agua.ml_vaso ?? 250));
  });
  protected ajustesValidos = computed(() => {
    const l = this.litros();
    const aguaBien = l === null || (!Number.isNaN(l) && l >= 0.25 && l <= 8);
    return aguaBien && !(this.dormir() && this.dormir() === this.levantarse());
  });

  protected pendientes = this.servicio.avisos;
  protected hoy = this.servicio.hoy;
  protected faltanVasos = computed(() => {
    const a = this.hoy()?.agua;
    return a ? Math.max(0, a.meta - a.vasos) : 0;
  });

  ngOnInit(): void {
    this.servicio.cargar().subscribe({ error: (e) => this.error.set(mensajeError(e, 'No pudimos cargar tus avisos.')) });
    this.servicio.cargarHoy().subscribe({ error: () => undefined });
    this.servicio.cargarHabitos().subscribe({
      next: (h) => {
        this.litros.set(h.agua_ml === null ? null : h.agua_ml / 1000);
        this.levantarse.set(h.hora_levantarse?.slice(0, 5) ?? '');
        this.dormir.set(h.hora_dormir?.slice(0, 5) ?? '');
        this.entreno.set(h.hora_entreno?.slice(0, 5) ?? '');
        this.apagados.set(h.avisos_apagados);
      },
      error: () => undefined,
    });
    void this.push.iniciar();
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
      next: () => {
        this.servicio.cargarHoy().subscribe({ error: () => undefined });
        this.servicio.cargar().subscribe({ error: () => undefined });
      },
      error: (e) => this.error.set(mensajeError(e, 'No pudimos anotar el vaso.')),
    });
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
