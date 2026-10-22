import { ChangeDetectionStrategy, Component, inject, output, signal } from '@angular/core';
import { ButtonModule } from 'primeng/button';
import { InputTextModule } from 'primeng/inputtext';
import { MessageModule } from 'primeng/message';

import { DuracionPausa } from '../../core/models/avisos.model';
import { AvisosService } from '../../core/services/avisos';
import { CelebracionesService } from '../../core/services/celebraciones';
import { clasesChip } from '../../shared/chip';
import { mensajeError } from '../../shared/errores';

const OPCIONES: { id: string; label: string; duracion: DuracionPausa; cantidad?: number }[] = [
  { id: 'horas', label: 'Unas horas', duracion: 'horas', cantidad: 4 },
  { id: 'hoy', label: 'Hoy', duracion: 'hoy' },
  { id: '3', label: '3 días', duracion: 'dias', cantidad: 3 },
  { id: '7', label: 'Una semana', duracion: 'dias', cantidad: 7 },
  { id: 'abierta', label: 'Hasta que vuelva', duracion: 'indefinida' },
];

/** «hasta mañana», «hasta el jueves 16 de octubre», «hasta las 3:40 p. m.»; vacío si es hasta que vuelva. */
export function hastaCuando(hasta: string | null): string {
  if (!hasta) return '';
  const fin = new Date(hasta);
  const medianoche = fin.getHours() === 0 && fin.getMinutes() === 0;
  // Una pausa que acaba a la medianoche cubre todo el día anterior.
  const ultimo = new Date(fin.getTime() - (medianoche ? 60_000 : 0));
  const hoy = new Date();
  const mismoDia = ultimo.toDateString() === hoy.toDateString();
  if (!medianoche) {
    const hora = fin.toLocaleTimeString('es-CO', { hour: 'numeric', minute: '2-digit' });
    return mismoDia
      ? `hasta las ${hora}`
      : `hasta el ${fin.toLocaleDateString('es-CO', { weekday: 'long', day: 'numeric', month: 'long' })}, ${hora}`;
  }
  if (mismoDia) return 'hasta que termine el día';
  return `hasta el ${ultimo.toLocaleDateString('es-CO', { weekday: 'long', day: 'numeric', month: 'long' })}`;
}

/**
 * «Voy a estar desconectado»: no llega ningún aviso y los días que cubra (al menos 8 horas del día) no cuentan ni
 * rompen la racha. Para cuando la vida se desordena (un bebé, un viaje, una semana pesada).
 */
@Component({
  selector: 'app-modo-pausa',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [ButtonModule, InputTextModule, MessageModule],
  template: `
    @if (servicio.pausa(); as p) {
      <section
        class="rounded-xl bg-indigo-500/10 border border-indigo-500/30 p-4 space-y-2"
        aria-label="Estás en pausa"
      >
        <p class="flex items-center gap-2 font-semibold text-gray-900 dark:text-white">
          <i class="pi pi-pause-circle text-indigo-500" aria-hidden="true"></i>
          Estás en pausa {{ hastaCuando(p.hasta) }}
        </p>
        @if (p.motivo) {
          <p class="text-sm text-gray-700 dark:text-gray-200">{{ p.motivo }}</p>
        }
        <p class="text-xs text-gray-600 dark:text-gray-300">
          No te llegan avisos y estos días no cuentan ni rompen tu racha. Cuando puedas, aquí
          seguimos.
        </p>
        <p-button
          label="Ya volví"
          icon="pi pi-play"
          size="small"
          [loading]="trabajando()"
          (onClick)="volver()"
        />
      </section>
    } @else if (abierto()) {
      <section class="rounded-xl bg-white dark:bg-dark-800 shadow-sm p-4 space-y-3">
        <h3 class="font-semibold text-gray-900 dark:text-white">
          ¿Cuánto vas a estar desconectado?
        </h3>
        <div class="flex flex-wrap gap-2" role="radiogroup" aria-label="Cuánto tiempo">
          @for (o of opciones; track o.id) {
            <button
              type="button"
              role="radio"
              [attr.aria-checked]="elegida() === o.id"
              [class]="clasesChip(elegida() === o.id)"
              (click)="elegida.set(o.id)"
            >
              {{ o.label }}
            </button>
          }
        </div>
        <label class="flex flex-col gap-1 text-sm font-medium text-gray-600 dark:text-gray-400">
          ¿Qué pasa? <span class="text-xs font-normal text-gray-400">opcional</span>
          <input
            pInputText
            maxlength="120"
            placeholder="Ej. Nació mi bebé"
            [value]="motivo()"
            (input)="motivo.set($any($event.target).value)"
          />
        </label>
        <p class="text-xs text-gray-500 dark:text-gray-400">
          Mientras dure no te llega ningún aviso. Los días que cubra no cuentan en tu cumplimiento
          ni rompen tu racha (tampoco la suman). Una pausa de unas horas solo calla los avisos.
        </p>
        @if (error()) {
          <p-message severity="error" [text]="error()" styleClass="w-full" />
        }
        <div class="flex justify-end gap-2">
          <p-button
            label="Cancelar"
            variant="outlined"
            severity="secondary"
            (onClick)="abierto.set(false)"
          />
          <p-button
            label="Pausar"
            icon="pi pi-pause"
            [loading]="trabajando()"
            [disabled]="!elegida()"
            (onClick)="pausar()"
          />
        </div>
      </section>
    } @else {
      <button
        type="button"
        class="w-full flex items-center gap-3 rounded-xl border border-dashed border-gray-300 dark:border-dark-700 p-3 text-left text-sm text-gray-700 dark:text-gray-200 hover:border-indigo-400 focus-visible:outline-2 focus-visible:outline-guerrero-red"
        (click)="abierto.set(true)"
      >
        <i class="pi pi-pause-circle text-lg text-indigo-500" aria-hidden="true"></i>
        <span>
          <span class="block font-semibold">¿Vas a estar desconectado?</span>
          <span class="block text-xs text-gray-500 dark:text-gray-400"
            >Pon la app en pausa: sin avisos y sin perder tu racha.</span
          >
        </span>
      </button>
    }
  `,
})
export class ModoPausa {
  protected servicio = inject(AvisosService);
  private celebraciones = inject(CelebracionesService);
  /** Cambió la pausa: quien la usa vuelve a programar lo del celular y recarga el día. */
  readonly cambio = output<void>();

  protected opciones = OPCIONES;
  protected clasesChip = clasesChip;
  protected hastaCuando = hastaCuando;

  protected abierto = signal(false);
  protected elegida = signal<string | null>(null);
  protected motivo = signal('');
  protected trabajando = signal(false);
  protected error = signal('');

  protected pausar(): void {
    const o = OPCIONES.find((x) => x.id === this.elegida());
    if (!o) return;
    this.trabajando.set(true);
    this.error.set('');
    this.servicio
      .pausar({
        duracion: o.duracion,
        cantidad: o.cantidad,
        motivo: this.motivo().trim(),
      })
      .subscribe({
        next: () => {
          this.trabajando.set(false);
          this.abierto.set(false);
          this.elegida.set(null);
          this.motivo.set('');
          void this.celebraciones.revisar(true);
          this.cambio.emit();
        },
        error: (e) => {
          this.trabajando.set(false);
          this.error.set(mensajeError(e, 'No pudimos poner la pausa.'));
        },
      });
  }

  protected volver(): void {
    this.trabajando.set(true);
    this.servicio.volver().subscribe({
      next: () => {
        this.trabajando.set(false);
        // El guerrero se despierta con la persona.
        void this.celebraciones.revisar(true);
        this.cambio.emit();
      },
      error: (e) => {
        this.trabajando.set(false);
        this.error.set(mensajeError(e, 'No pudimos quitar la pausa.'));
      },
    });
  }
}
