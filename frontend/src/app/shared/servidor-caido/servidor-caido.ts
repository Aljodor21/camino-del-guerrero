import { ChangeDetectionStrategy, Component, inject } from '@angular/core';

import { ServidorService } from '../../core/services/servidor';

/**
 * El aviso de "no hay conexión con el servidor": una tarjeta tranquila sobre la barra de abajo
 * (no tapa lo que se está leyendo), que se retira sola cuando vuelve la conexión.
 */
@Component({
  selector: 'app-servidor-caido',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (servidor.caido()) {
      <div
        role="alert"
        class="aviso-entra fixed inset-x-3 bottom-20 z-[70] mx-auto max-w-md rounded-2xl bg-white dark:bg-dark-800 p-4 shadow-xl ring-1 ring-black/10 dark:ring-white/10"
      >
        <div class="flex items-start gap-3">
          <span
            class="w-11 h-11 shrink-0 rounded-2xl bg-amber-500/15 text-amber-600 dark:text-amber-400 flex items-center justify-center"
            aria-hidden="true"
          >
            <i [class]="servidor.sinInternet() ? 'pi pi-wifi text-lg' : 'pi pi-server text-lg'"></i>
          </span>
          <div class="min-w-0 flex-1">
            <p class="font-semibold text-gray-900 dark:text-white leading-snug">
              {{ servidor.sinInternet() ? 'Sin internet' : 'No podemos conectar con el servidor' }}
            </p>
            <p class="mt-0.5 text-sm text-gray-600 dark:text-gray-300">
              {{
                servidor.sinInternet()
                  ? 'Revisa tu conexión. Tus datos están a salvo y seguimos intentando.'
                  : 'Puede ser momentáneo. Tus datos están a salvo y seguimos intentando.'
              }}
            </p>
            <div class="mt-3 flex items-center gap-3">
              <button
                type="button"
                (click)="servidor.probar()"
                [disabled]="servidor.probando()"
                class="rounded-lg bg-guerrero-red px-3.5 py-1.5 text-sm font-semibold text-white hover:bg-guerrero-red-dark disabled:opacity-60 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-guerrero-red"
              >
                Reintentar
              </button>
              <span class="flex items-center gap-1.5 text-xs text-gray-500 dark:text-gray-400">
                <i class="pi pi-spin pi-spinner text-xs" aria-hidden="true"></i>
                Reintentando solos
              </span>
            </div>
          </div>
        </div>
      </div>
    } @else if (servidor.recuperado()) {
      <div
        role="status"
        class="aviso-entra fixed inset-x-3 bottom-20 z-[70] mx-auto flex max-w-md items-center gap-2 rounded-2xl bg-emerald-600 px-4 py-3 text-sm font-semibold text-white shadow-xl"
      >
        <i class="pi pi-check" aria-hidden="true"></i>
        Conexión recuperada
      </div>
    }
  `,
})
export class ServidorCaido {
  protected servidor = inject(ServidorService);
}
