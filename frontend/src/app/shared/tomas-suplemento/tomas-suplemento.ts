import {
  ChangeDetectionStrategy,
  Component,
  computed,
  effect,
  input,
  model,
  untracked,
} from '@angular/core';

import { InputTextModule } from 'primeng/inputtext';

import { GrupoMinuta, PorcionesMinuta, TiempoComida } from '../../core/models/minuta.model';
import { Toma } from '../../core/models/suplemento.model';
import { GRUPOS_MINUTA, TIEMPOS_COMIDA, porcionesDe } from '../../core/constants/nutricion';
import { clasesChip } from '../chip';
import { formatearNumero } from '../fechas';
import { gruposEn, tiemposDe } from '../minuta';
import { repartirScoops, scoopsFaltantes } from '../suplementos';

/**
 * Dónde se toma la porción del día: se eligen las comidas, la porción se reparte entre
 * ellas en scoops y cada toma dice qué reemplaza de esa comida de la minuta.
 */
/** Una toma que va en una comida de la minuta (las otras llevan 'otro'). */
type TomaDeComida = Toma & { tiempo: TiempoComida };

@Component({
  selector: 'app-tomas-suplemento',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [InputTextModule],
  template: `
    <fieldset class="space-y-3">
      <legend class="text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
        ¿En qué comidas la tomas?
      </legend>
      <div class="flex flex-wrap gap-2" role="group" aria-label="Comidas">
        @for (t of tiempos(); track t) {
          <button
            type="button"
            [attr.aria-pressed]="!!toma(t)"
            [class]="clasesChip(!!toma(t))"
            (click)="alternar(t)"
          >
            {{ comidas[t].label }}
          </button>
        }
      </div>
      @if (!tomas().length) {
        <p class="text-xs text-gray-500 dark:text-gray-400">
          Si aún no sabes, déjalo así: lo cambias cuando tu nutricionista te lo indique.
        </p>
      }

      @for (t of deComida(); track t.tiempo) {
        <div class="rounded-xl border border-gray-200 dark:border-dark-700 p-3 space-y-3">
          <div class="flex items-center justify-between gap-3">
            <p class="text-sm font-semibold text-gray-900 dark:text-white">
              {{ comidas[t.tiempo].label }}
              <span class="font-normal text-gray-500 dark:text-gray-400"
                >· {{ comidas[t.tiempo].hora }}</span
              >
            </p>
            @if (scoopsPorcion()) {
              <div class="flex items-center gap-2" role="group" aria-label="Scoops en esta toma">
                <button
                  type="button"
                  class="w-8 h-8 rounded-full border border-gray-300 dark:border-dark-700 text-gray-700 dark:text-gray-200 disabled:opacity-40"
                  [disabled]="(t.scoops ?? 0) <= 0.5"
                  (click)="mover(t.tiempo, -0.5)"
                  aria-label="Un poco menos"
                >
                  −
                </button>
                <span class="min-w-[4.5rem] text-center text-sm tabular-nums">
                  {{ n(t.scoops ?? 0) }} {{ t.scoops === 1 ? 'scoop' : 'scoops' }}
                </span>
                <button
                  type="button"
                  class="w-8 h-8 rounded-full border border-gray-300 dark:border-dark-700 text-gray-700 dark:text-gray-200"
                  (click)="mover(t.tiempo, 0.5)"
                  aria-label="Un poco más"
                >
                  +
                </button>
              </div>
            }
          </div>

          @if (liquidoDe(t); as liquido) {
            <p class="text-xs text-gray-600 dark:text-gray-400">{{ liquido }}</p>
          }

          <div class="grid grid-cols-2 gap-3">
            <div class="flex flex-col gap-1">
              <label [for]="'tm-hora-' + t.tiempo" class="text-xs font-medium text-gray-600 dark:text-gray-400"
                >Hora <span class="font-normal text-gray-400">opcional</span></label
              >
              <input
                [id]="'tm-hora-' + t.tiempo"
                type="time"
                pInputText class="w-full"
                [value]="t.hora ?? ''"
                (change)="detalle(t.tiempo, { hora: $any($event.target).value })"
              />
            </div>
            <div class="flex flex-col gap-1">
              <label [for]="'tm-nota-' + t.tiempo" class="text-xs font-medium text-gray-600 dark:text-gray-400"
                >Cómo <span class="font-normal text-gray-400">opcional</span></label
              >
              <input
                [id]="'tm-nota-' + t.tiempo"
                type="text"
                maxlength="80"
                placeholder="Ej. después de entrenar"
                pInputText class="w-full"
                [value]="t.nota ?? ''"
                (change)="detalle(t.tiempo, { nota: $any($event.target).value })"
              />
            </div>
          </div>

          @if (grupos(t.tiempo).length) {
            <div class="space-y-1.5">
              <p class="text-xs font-medium text-gray-600 dark:text-gray-400">
                ¿Qué reemplaza en {{ comidas[t.tiempo].con }}?
              </p>
              <div class="flex flex-wrap gap-2">
                @for (g of grupos(t.tiempo); track g) {
                  <button
                    type="button"
                    [attr.aria-pressed]="!!t.reemplaza[g]"
                    [class]="clasesChip(!!t.reemplaza[g])"
                    (click)="alternarReemplazo(t.tiempo, g)"
                  >
                    {{ grupoNombre(g) }}
                  </button>
                }
              </div>
              @if (resumenReemplazo(t); as texto) {
                <p class="text-xs text-gray-500 dark:text-gray-400">{{ texto }}</p>
              } @else {
                <p class="text-xs text-gray-500 dark:text-gray-400">
                  Si no marcas nada, esa comida se arma completa además de la proteína. Marca lo
                  que la proteína reemplaza para que el menú no lo pida.
                </p>
              }
            </div>
          }
        </div>
      }

      @for (t of extras(); track $index; let i = $index) {
        <div class="rounded-xl border border-gray-200 dark:border-dark-700 p-3 space-y-3">
          <div class="flex items-center justify-between gap-3">
            <p class="text-sm font-semibold text-gray-900 dark:text-white">Otra toma</p>
            <div class="flex items-center gap-2">
              @if (scoopsPorcion()) {
                <div class="flex items-center gap-2" role="group" aria-label="Scoops en esta toma">
                  <button
                    type="button"
                    class="w-8 h-8 rounded-full border border-gray-300 dark:border-dark-700 text-gray-700 dark:text-gray-200 disabled:opacity-40"
                    [disabled]="(t.scoops ?? 0) <= 0.5"
                    (click)="moverExtra(i, -0.5)"
                    aria-label="Un poco menos"
                  >
                    −
                  </button>
                  <span class="min-w-[4.5rem] text-center text-sm tabular-nums">
                    {{ n(t.scoops ?? 0) }} {{ t.scoops === 1 ? 'scoop' : 'scoops' }}
                  </span>
                  <button
                    type="button"
                    class="w-8 h-8 rounded-full border border-gray-300 dark:border-dark-700 text-gray-700 dark:text-gray-200"
                    (click)="moverExtra(i, 0.5)"
                    aria-label="Un poco más"
                  >
                    +
                  </button>
                </div>
              }
              <button
                type="button"
                class="w-8 h-8 rounded-full text-gray-400 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-950/30"
                (click)="quitarExtra(i)"
                aria-label="Quitar esta toma"
              >
                <i class="pi pi-trash text-sm" aria-hidden="true"></i>
              </button>
            </div>
          </div>

          @if (liquidoDe(t); as liquido) {
            <p class="text-xs text-gray-600 dark:text-gray-400">{{ liquido }}</p>
          }

          <div class="grid grid-cols-2 gap-3">
            <div class="flex flex-col gap-1">
              <label [for]="'tm-extra-hora-' + i" class="text-xs font-medium text-gray-600 dark:text-gray-400">Hora</label>
              <input
                [id]="'tm-extra-hora-' + i"
                type="time"
                pInputText
                class="w-full"
                required
                [value]="t.hora ?? ''"
                (change)="detalleExtra(i, { hora: $any($event.target).value })"
              />
            </div>
            <div class="flex flex-col gap-1">
              <label [for]="'tm-extra-nota-' + i" class="text-xs font-medium text-gray-600 dark:text-gray-400"
                >Cómo <span class="font-normal text-gray-400">opcional</span></label
              >
              <input
                [id]="'tm-extra-nota-' + i"
                type="text"
                maxlength="80"
                placeholder="Ej. antes de dormir"
                pInputText
                class="w-full"
                [value]="t.nota ?? ''"
                (change)="detalleExtra(i, { nota: $any($event.target).value })"
              />
            </div>
          </div>
        </div>
      }

      @if (extras().length < maxExtras) {
        <button
          type="button"
          (click)="agregarExtra()"
          class="inline-flex items-center gap-1.5 text-sm font-medium text-guerrero-red hover:underline"
        >
          <i class="pi pi-plus text-xs" aria-hidden="true"></i>
          Agregar otra toma, a la hora que quieras
        </button>
      }

      @if (scoopsPorcion() && tomas().length) {
        <p
          class="text-sm rounded-lg px-3 py-2.5"
          [class]="
            faltan() === 0
              ? 'bg-gray-100 text-gray-700 dark:bg-dark-700 dark:text-gray-300'
              : 'bg-red-50 text-red-700 dark:bg-red-950/40 dark:text-red-300'
          "
          aria-live="polite"
        >
          @if (faltan() === 0) {
            Sumas los {{ n(scoopsPorcion()!) }} scoops de tu porción.
          } @else if (faltan() > 0) {
            Te faltan {{ n(faltan()) }} {{ faltan() === 1 ? 'scoop' : 'scoops' }} para completar
            la porción de {{ n(scoopsPorcion()!) }}.
          } @else {
            Te pasas por {{ n(-faltan()) }} {{ faltan() === -1 ? 'scoop' : 'scoops' }} de los
            {{ n(scoopsPorcion()!) }} de la porción.
          }
        </p>
      }
    </fieldset>
  `,
})
export class TomasSuplemento {
  /** La minuta, para saber qué comidas hay y qué porciones tiene cada una. */
  readonly porciones = input.required<PorcionesMinuta>();
  /** Scoops de la porción del día; null si aún no se sabe. */
  readonly scoopsPorcion = input<number | null>(null);
  /** El líquido de la porción del día y cuánto es leche, para decir cuánto lleva cada toma. */
  readonly liquidoMl = input<number | null>(null);
  readonly lecheMl = input<number | null>(null);
  readonly tomas = model.required<Toma[]>();

  protected comidas = TIEMPOS_COMIDA;
  protected clasesChip = clasesChip;
  protected readonly maxExtras = 4;
  /** Las tomas que van en una comida de la minuta, y las "otras" a la hora que se elige. */
  protected deComida = computed(() => this.tomas().filter((t): t is TomaDeComida => t.tiempo !== 'otro'));
  protected extras = computed(() => this.tomas().filter((t) => t.tiempo === 'otro'));
  protected tiempos = computed(() => tiemposDe(this.porciones()));
  protected faltan = computed(() => scoopsFaltantes(this.tomas(), this.scoopsPorcion()));

  constructor() {
    // Si cambian los scoops de la porción y las tomas ya no suman, se vuelven a repartir.
    effect(() => {
      const total = this.scoopsPorcion();
      const tomas = untracked(() => this.tomas());
      if (!total || !tomas.length || scoopsFaltantes(tomas, total) === 0) return;
      const scoops = repartirScoops(total, tomas.length);
      this.tomas.set(tomas.map((t, i) => ({ ...t, scoops: scoops[i] })));
    });
  }

  protected toma(tiempo: TiempoComida): Toma | undefined {
    return this.deComida().find((t) => t.tiempo === tiempo);
  }

  protected grupos(tiempo: TiempoComida): GrupoMinuta[] {
    return gruposEn(this.porciones(), tiempo);
  }

  protected grupoNombre(grupo: GrupoMinuta): string {
    return GRUPOS_MINUTA[grupo];
  }

  protected n(valor: number): string {
    return formatearNumero(valor, 1);
  }

  /** "1 porción de lácteos y 1 de cereales" de lo que reemplaza esa toma. */
  protected resumenReemplazo(t: TomaDeComida): string {
    const partes = this.grupos(t.tiempo)
      .filter((g) => t.reemplaza[g])
      .map((g) => porcionesDe(g, t.reemplaza[g]!));
    return partes.length ? `Esa comida lleva ${partes.join(' y ')} menos.` : '';
  }

  /** Reparte la porción del día en partes iguales entre todas las tomas. */
  private repartir(lista: Toma[]): Toma[] {
    const total = this.scoopsPorcion();
    if (!total) return lista;
    const scoops = repartirScoops(total, lista.length);
    return lista.map((t, i) => ({ ...t, scoops: scoops[i] }));
  }

  /** Al sumar o quitar una comida, la porción se vuelve a repartir en partes iguales. */
  protected alternar(tiempo: TiempoComida): void {
    const actuales = this.deComida();
    const orden = this.tiempos();
    const tiempos = orden.filter((t) => t === tiempo !== actuales.some((x) => x.tiempo === t));
    const comidas: Toma[] = tiempos.map((t) => ({
      ...(actuales.find((x) => x.tiempo === t) ?? { tiempo: t, scoops: null, reemplaza: {} }),
      tiempo: t,
    }));
    this.tomas.set(this.repartir([...comidas, ...this.extras()]));
  }

  /** Otra toma a una hora que la persona elige; la porción se reparte de nuevo. */
  protected agregarExtra(): void {
    const ocupadas = new Set(this.extras().map((t) => t.hora));
    const hora = ['21:00', '07:00', '13:00', '17:00', '10:00', '19:00'].find((h) => !ocupadas.has(h)) ?? '12:00';
    this.tomas.set(this.repartir([...this.tomas(), { tiempo: 'otro', scoops: null, reemplaza: {}, hora }]));
  }

  protected quitarExtra(indice: number): void {
    const quitada = this.extras()[indice];
    this.tomas.set(this.repartir(this.tomas().filter((t) => t !== quitada)));
  }

  private cambiarExtra(indice: number, fn: (t: Toma) => Toma): void {
    const objetivo = this.extras()[indice];
    this.tomas.update((lista) => lista.map((t) => (t === objetivo ? fn(t) : t)));
  }

  protected moverExtra(indice: number, paso: number): void {
    this.cambiarExtra(indice, (t) => ({
      ...t,
      scoops: Math.max(0.5, Math.round(((t.scoops ?? 0) + paso) * 2) / 2),
    }));
  }

  protected detalleExtra(indice: number, cambios: { hora?: string; nota?: string }): void {
    this.cambiarExtra(indice, (t) => {
      const siguiente: Toma = { ...t, ...cambios };
      // La hora es obligatoria en otra toma: si la borran, se queda la anterior.
      if (!siguiente.hora) siguiente.hora = t.hora;
      if (!siguiente.nota?.trim()) delete siguiente.nota;
      return siguiente;
    });
  }

  /** La hora y el cómo de una toma; vacíos se quitan. */
  protected detalle(tiempo: TiempoComida, cambios: { hora?: string; nota?: string }): void {
    this.tomas.update((lista) =>
      lista.map((t) => {
        if (t.tiempo !== tiempo) return t;
        const siguiente: Toma = { ...t, ...cambios };
        if (!siguiente.hora) delete siguiente.hora;
        if (!siguiente.nota?.trim()) delete siguiente.nota;
        return siguiente;
      }),
    );
  }

  /** "600 ml de líquido: 250 de leche y 350 de agua", repartido según los scoops de la toma. */
  protected liquidoDe(t: Toma): string {
    const total = this.liquidoMl();
    const porcion = this.scoopsPorcion();
    if (!total || !porcion || !t.scoops) return '';
    const parte = t.scoops / porcion;
    const ml = Math.round(total * parte);
    const leche = this.lecheMl();
    if (!leche) return `${ml} ml de líquido en esta toma`;
    const l = Math.round(leche * parte);
    return `${ml} ml de líquido en esta toma: ${l} de leche y ${ml - l} de agua`;
  }

  protected mover(tiempo: TiempoComida, paso: number): void {
    this.tomas.update((lista) =>
      lista.map((t) =>
        t.tiempo === tiempo
          ? { ...t, scoops: Math.max(0.5, Math.round(((t.scoops ?? 0) + paso) * 2) / 2) }
          : t,
      ),
    );
  }

  protected alternarReemplazo(tiempo: TiempoComida, grupo: GrupoMinuta): void {
    this.tomas.update((lista) =>
      lista.map((t) => {
        if (t.tiempo !== tiempo) return t;
        const reemplaza = { ...t.reemplaza };
        if (reemplaza[grupo]) delete reemplaza[grupo];
        else reemplaza[grupo] = 1;
        return { ...t, reemplaza };
      }),
    );
  }
}
