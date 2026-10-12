import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  effect,
  input,
  model,
  viewChild,
} from '@angular/core';

export interface Pestana<T extends string = string> {
  id: T;
  label: string;
  icon: string;
}

/**
 * La barra de pestañas de una sección. Si no caben todas se desplaza hacia el lado (en vez de
 * apretarlas), y la pestaña activa siempre queda a la vista.
 */
@Component({
  selector: 'app-pestanas',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: { class: 'block' },
  template: `
    <div
      #barra
      class="sin-barra flex overflow-x-auto snap-x gap-1 bg-gray-100 dark:bg-dark-700 rounded-xl p-1"
      role="tablist"
      [attr.aria-label]="etiqueta()"
    >
      @for (p of items(); track p.id) {
        <button
          type="button"
          role="tab"
          [attr.id]="'pestana-' + p.id"
          [attr.aria-selected]="activa() === p.id"
          (click)="activa.set(p.id)"
          [class]="
            'flex-1 shrink-0 snap-start whitespace-nowrap px-3.5 py-2 text-sm rounded-lg transition-all focus-visible:outline-2 focus-visible:outline-guerrero-red ' +
            (activa() === p.id
              ? 'font-semibold bg-white dark:bg-dark-800 text-guerrero-red shadow-sm'
              : 'font-medium text-gray-500 dark:text-gray-400')
          "
        >
          <i [class]="p.icon + ' text-xs mr-1.5'" aria-hidden="true"></i>{{ p.label }}
        </button>
      }
    </div>
  `,
})
export class Pestanas<T extends string = string> {
  readonly items = input.required<Pestana<T>[]>();
  readonly etiqueta = input('Secciones');
  readonly activa = model.required<T>();

  private barra = viewChild.required<ElementRef<HTMLElement>>('barra');

  constructor() {
    // La pestaña elegida (o la que llegó por la URL) se centra en la barra.
    effect(() => {
      const id = this.activa();
      queueMicrotask(() => {
        const boton = this.barra().nativeElement.querySelector<HTMLElement>(`#pestana-${id}`);
        const barra = this.barra().nativeElement;
        if (!boton || barra.scrollWidth <= barra.clientWidth) return;
        barra.scrollTo({
          left: boton.offsetLeft - (barra.clientWidth - boton.clientWidth) / 2,
          behavior: 'smooth',
        });
      });
    });
  }
}
