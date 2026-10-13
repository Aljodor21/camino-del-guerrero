import { ChangeDetectionStrategy, Component, input, signal } from '@angular/core';

/**
 * Una línea discreta que dice para qué sirve esta parte de la app y qué se puede hacer en ella. Va
 * cerrada: solo un «¿Para qué sirve?» pequeño; al tocarlo se abre con una frase y la lista de lo que
 * se puede hacer. No recuerda nada ni se abre sola: está ahí para quien la busque.
 */
@Component({
  selector: 'app-que-es',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: { class: 'block' },
  template: `
    <div class="text-gray-500 dark:text-gray-400">
      <button
        type="button"
        class="inline-flex items-center gap-1.5 text-xs font-medium hover:text-gray-700 dark:hover:text-gray-200 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-guerrero-red rounded"
        [attr.aria-expanded]="abierto()"
        [attr.aria-controls]="id"
        (click)="abierto.set(!abierto())"
      >
        <i class="pi pi-info-circle text-[13px]" aria-hidden="true"></i>
        {{ abierto() ? 'Cerrar' : titulo() }}
      </button>
      @if (abierto()) {
        <div
          [id]="id"
          class="mt-2 rounded-xl bg-gray-100/70 dark:bg-white/5 px-3.5 py-3 text-sm text-gray-700 dark:text-gray-300 space-y-2"
        >
          <p>{{ para() }}</p>
          @if (puedes().length) {
            <div>
              <p class="text-xs font-semibold text-gray-600 dark:text-gray-300">Aquí puedes</p>
              <ul class="mt-1 space-y-1 list-disc pl-5 marker:text-guerrero-red">
                @for (p of puedes(); track p) {
                  <li>{{ p }}</li>
                }
              </ul>
            </div>
          }
        </div>
      }
    </div>
  `,
})
export class QueEs {
  /** Lo que dice el enlace cerrado. */
  readonly titulo = input('¿Para qué sirve esto?');
  /** Para qué sirve, en una o dos frases. */
  readonly para = input.required<string>();
  /** Lo que se puede hacer aquí, una cosa por línea. */
  readonly puedes = input<string[]>([]);

  protected abierto = signal(false);
  protected id = `que-es-${Math.random().toString(36).slice(2, 8)}`;
}
