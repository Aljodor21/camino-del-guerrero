import { ChangeDetectionStrategy, Component, computed, input, model } from '@angular/core';
import { InputTextModule } from 'primeng/inputtext';

import { UNIDADES_PESO } from '../../core/constants/proceso';
import { clasesChip } from '../chip';
import { parsearDecimal } from '../decimal-input';
import { formatearNumero } from '../fechas';
import { Etiqueta, erroresEtiqueta, gramosEnvase, porcionesPorEnvase } from '../suplementos';

/**
 * Los datos de la etiqueta: peso del envase, cuánto pesa una porción y en cuántos scoops
 * viene. Con eso se calcula para cuántas porciones (y días) alcanza el envase.
 */
@Component({
  selector: 'app-etiqueta-suplemento',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [InputTextModule],
  template: `
    <fieldset class="space-y-3">
      <legend class="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
        Lo que dice la etiqueta
      </legend>
      <p class="text-xs text-gray-500 dark:text-gray-400 -mt-1">
        La porción es la de todo el día, repartida en scoops.
      </p>

      <div class="flex flex-col gap-1">
        <label
          [for]="prefijo() + '-peso'"
          class="text-xs font-medium text-gray-600 dark:text-gray-400"
          >Peso del envase</label
        >
        <div class="flex gap-2">
          <input
            pInputText
            [id]="prefijo() + '-peso'"
            inputmode="decimal"
            placeholder="Ej. 3"
            [value]="numero(e().peso)"
            (change)="cambiar({ peso: leer($event) })"
            [attr.aria-invalid]="!!errores().peso"
            class="w-full min-w-0"
          />
          <div role="radiogroup" aria-label="Unidad del peso" class="flex gap-1 shrink-0">
            @for (u of unidades; track u.value) {
              <button
                type="button"
                role="radio"
                [attr.aria-checked]="e().unidad === u.value"
                (click)="cambiar({ unidad: u.value })"
                [class]="clasesChip(e().unidad === u.value)"
              >
                {{ u.label }}
              </button>
            }
          </div>
        </div>
        @if (errores().peso; as error) {
          <small class="text-xs text-red-600 dark:text-red-400">{{ error }}</small>
        }
      </div>

      <div class="grid grid-cols-2 gap-3">
        <div class="flex flex-col gap-1">
          <label
            [for]="prefijo() + '-porcion'"
            class="text-xs font-medium text-gray-600 dark:text-gray-400"
            >Porción (g)</label
          >
          <input
            pInputText
            [id]="prefijo() + '-porcion'"
            inputmode="decimal"
            placeholder="Ej. 150"
            [value]="numero(e().porcionG)"
            (change)="cambiar({ porcionG: leer($event) })"
            [attr.aria-invalid]="!!errores().porcionG"
            class="w-full"
          />
        </div>
        <div class="flex flex-col gap-1">
          <label
            [for]="prefijo() + '-scoops'"
            class="text-xs font-medium text-gray-600 dark:text-gray-400"
            >Scoops</label
          >
          <input
            pInputText
            [id]="prefijo() + '-scoops'"
            inputmode="decimal"
            placeholder="Ej. 3"
            [value]="numero(e().scoops)"
            (change)="cambiar({ scoops: leer($event) })"
            [attr.aria-invalid]="!!errores().scoops"
            class="w-full"
          />
        </div>
      </div>
      @for (error of erroresPorcion(); track error) {
        <small class="block text-xs text-red-600 dark:text-red-400 -mt-1">{{ error }}</small>
      }

      <div class="space-y-3">
        <p class="text-xs font-medium text-gray-600 dark:text-gray-400">
          ¿Con qué la mezclas? (opcional)
        </p>
        <div role="radiogroup" aria-label="Con qué se mezcla" class="flex flex-wrap gap-2">
          @for (l of liquidos; track l.value) {
            <button
              type="button"
              role="radio"
              [attr.aria-checked]="e().liquido === l.value"
              (click)="elegirLiquido(l.value)"
              [class]="clasesChip(e().liquido === l.value)"
            >
              {{ l.label }}
            </button>
          }
        </div>

        @if (e().liquido) {
          <div class="flex flex-col gap-1">
            <label
              [for]="prefijo() + '-liquido'"
              class="text-xs font-medium text-gray-600 dark:text-gray-400"
              >Líquido de la porción del día (ml)</label
            >
            <input
              pInputText
              [id]="prefijo() + '-liquido'"
              inputmode="decimal"
              [placeholder]="sugerencia() ? 'Ej. ' + sugerencia() : 'Ej. 600'"
              [value]="numero(e().liquidoMl)"
              (change)="cambiar({ liquidoMl: leer($event) })"
              [attr.aria-invalid]="!!errores().liquidoMl"
              class="w-full"
            />
            @if (errores().liquidoMl; as error) {
              <small class="text-xs text-red-600 dark:text-red-400">{{ error }}</small>
            } @else if (e().liquidoMl === null && sugerencia(); as sug) {
              <small class="text-xs text-gray-500 dark:text-gray-400">
                Un punto de partida: unos 200 ml por scoop, o sea
                {{ sug }} ml para tus {{ n(e().scoops ?? 0) }} scoops. Tu etiqueta puede decir otra
                cosa.
                <button
                  type="button"
                  class="font-semibold text-guerrero-red underline ml-1"
                  (click)="cambiar({ liquidoMl: sug })"
                >
                  Usar {{ sug }} ml
                </button>
              </small>
            }
          </div>
        }

        @if (e().liquido === 'mezcla') {
          <div class="flex flex-col gap-1">
            <label
              [for]="prefijo() + '-leche'"
              class="text-xs font-medium text-gray-600 dark:text-gray-400"
              >De ese líquido, cuánta es leche (ml)</label
            >
            <input
              pInputText
              [id]="prefijo() + '-leche'"
              inputmode="decimal"
              placeholder="Ej. 500"
              [value]="numero(e().lecheMl)"
              (change)="cambiar({ lecheMl: leer($event) })"
              [attr.aria-invalid]="!!errores().lecheMl"
              class="w-full"
            />
            @if (errores().lecheMl; as error) {
              <small class="text-xs text-red-600 dark:text-red-400">{{ error }}</small>
            } @else if (agua() !== null) {
              <small class="text-xs text-gray-500 dark:text-gray-400"
                >El resto, {{ agua() }} ml, es agua.</small
              >
            }
          </div>
        }

        @if (e().liquido === 'leche' || e().liquido === 'mezcla') {
          <fieldset class="space-y-2">
            <legend class="text-xs font-medium text-gray-600 dark:text-gray-400">
              Tabla nutricional de la leche <span class="font-normal text-gray-400">opcional</span>
            </legend>
            <div class="grid grid-cols-3 gap-2">
              <div class="flex flex-col gap-1">
                <label
                  [for]="prefijo() + '-lt-ml'"
                  class="text-[11px] text-gray-500 dark:text-gray-400"
                  >Porción (ml)</label
                >
                <input
                  pInputText
                  [id]="prefijo() + '-lt-ml'"
                  inputmode="decimal"
                  placeholder="250"
                  [value]="numero(e().lechePorcionMl)"
                  (change)="cambiar({ lechePorcionMl: leer($event) })"
                  class="w-full"
                />
              </div>
              <div class="flex flex-col gap-1">
                <label
                  [for]="prefijo() + '-lt-kcal'"
                  class="text-[11px] text-gray-500 dark:text-gray-400"
                  >Calorías</label
                >
                <input
                  pInputText
                  [id]="prefijo() + '-lt-kcal'"
                  inputmode="decimal"
                  placeholder="150"
                  [value]="numero(e().lecheKcal)"
                  (change)="cambiar({ lecheKcal: leer($event) })"
                  class="w-full"
                />
              </div>
              <div class="flex flex-col gap-1">
                <label
                  [for]="prefijo() + '-lt-prot'"
                  class="text-[11px] text-gray-500 dark:text-gray-400"
                  >Proteína (g)</label
                >
                <input
                  pInputText
                  [id]="prefijo() + '-lt-prot'"
                  inputmode="decimal"
                  placeholder="8"
                  [value]="numero(e().lecheProteina)"
                  (change)="cambiar({ lecheProteina: leer($event) })"
                  class="w-full"
                />
              </div>
            </div>
            @if (errores().lecheKcal; as error) {
              <small class="text-xs text-red-600 dark:text-red-400">{{ error }}</small>
            } @else {
              <small class="text-xs text-gray-500 dark:text-gray-400">
                Con ella, la estimación de tu cambio cuenta lo que aporta la leche.
              </small>
            }
          </fieldset>
        }
      </div>

      <p
        class="text-sm rounded-lg px-3 py-2.5 bg-gray-100 text-gray-700 dark:bg-dark-700 dark:text-gray-300"
        aria-live="polite"
      >
        {{ resumen() }}
      </p>
    </fieldset>
  `,
})
export class EtiquetaSuplemento {
  /** Prefijo de los id de los campos, para que no choquen si hay varias en pantalla. */
  readonly prefijo = input.required<string>();
  readonly e = model.required<Etiqueta>({ alias: 'etiqueta' });

  protected unidades = UNIDADES_PESO;
  protected liquidos: { value: Etiqueta['liquido']; label: string }[] = [
    { value: '', label: 'No sé' },
    { value: 'agua', label: 'Agua' },
    { value: 'leche', label: 'Leche' },
    { value: 'mezcla', label: 'Leche y agua' },
  ];
  protected clasesChip = clasesChip;

  protected n = (v: number) => formatearNumero(v, 1);

  protected errores = computed(() => erroresEtiqueta(this.e()));

  /** Un punto de partida cuando se conocen los scoops: unos 200 ml por scoop. */
  protected sugerencia = computed(() => {
    const scoops = this.e().scoops;
    return scoops && !Number.isNaN(scoops) ? Math.round(scoops * 200) : null;
  });

  /** El agua que completa el líquido cuando se mezcla con leche. */
  protected agua = computed(() => {
    const e = this.e();
    return e.liquido === 'mezcla' && e.liquidoMl && e.lecheMl && e.lecheMl < e.liquidoMl
      ? e.liquidoMl - e.lecheMl
      : null;
  });

  protected elegirLiquido(liquido: Etiqueta['liquido']): void {
    this.cambiar({
      liquido,
      liquidoMl: liquido ? this.e().liquidoMl : null,
      lecheMl: liquido === 'mezcla' ? this.e().lecheMl : null,
      ...(liquido === 'leche' || liquido === 'mezcla'
        ? {}
        : { lechePorcionMl: null, lecheKcal: null, lecheProteina: null }),
    });
  }
  protected erroresPorcion = computed(() => {
    const e = this.errores();
    return [e.porcionG, e.scoops].filter((x): x is string => !!x);
  });

  /** "1 porción = 3 scoops (150 g). El envase trae 20 porciones: con 2 al día te dura 10 días." */
  protected resumen = computed(() => {
    const e = this.e();
    const n = (v: number) => formatearNumero(v, 1);
    const partes: string[] = [];
    if (e.porcionG && e.scoops) {
      partes.push(
        `1 porción = ${n(e.scoops)} ${e.scoops === 1 ? 'scoop' : 'scoops'} (${n(e.porcionG)} g).`,
      );
    } else if (e.porcionG) {
      partes.push(`1 porción = ${n(e.porcionG)} g.`);
    }
    const porciones = porcionesPorEnvase(e);
    const gramos = gramosEnvase(e);
    if (porciones && Object.keys(this.errores()).length === 0) {
      const dias = porciones;
      const peso = e.unidad === 'lb' && gramos ? ` (${n(gramos / 1000)} kg)` : '';
      partes.push(
        `El envase${peso} trae ${porciones} ${porciones === 1 ? 'porción' : 'porciones'}: a una por día te dura ${dias} ${dias === 1 ? 'día' : 'días'}.`,
      );
    } else {
      partes.push('Con el peso del envase y el de la porción calculamos cuánto te dura.');
    }
    const leche = e.liquido === 'leche' ? e.liquidoMl : e.liquido === 'mezcla' ? e.lecheMl : null;
    if (leche && !this.errores().liquidoMl && !this.errores().lecheMl) {
      const agua =
        e.liquido === 'mezcla' && this.agua() !== null ? ` y ${this.agua()} ml de agua` : '';
      partes.push(
        `Al día: ${leche} ml de leche${agua}. Por semana son ${n((leche * 7) / 1000)} L de leche: van a tu lista de mercado.`,
      );
    }
    return partes.join(' ');
  });

  protected numero(v: number | null): string {
    if (v === null || Number.isNaN(v)) return '';
    return v.toLocaleString('es-CO', { maximumFractionDigits: 3, useGrouping: false });
  }

  protected leer(evento: Event): number | null {
    return parsearDecimal((evento.target as HTMLInputElement).value);
  }

  protected cambiar(cambios: Partial<Etiqueta>): void {
    this.e.update((e) => ({ ...e, ...cambios }));
  }
}
