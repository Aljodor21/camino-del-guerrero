import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  ElementRef,
  afterNextRender,
  effect,
  inject,
  input,
  model,
  signal,
  viewChild,
} from '@angular/core';

export interface Pestana<T extends string = string> {
  id: T;
  label: string;
  icon: string;
  /** Un numerito rojo junto al nombre (ej. los avisos sin atender). Oculto si es 0. */
  contador?: number;
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
    <div class="relative">
      <div
        #barra
        (scroll)="medir()"
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
            @if (p.contador) {
              <span
                class="ml-1.5 inline-block min-w-5 h-5 px-1.5 rounded-full bg-guerrero-red text-white text-[11px] font-bold leading-5 text-center tabular-nums"
                >{{ p.contador }}</span
              >
            }
          </button>
        }
      </div>
      <!-- Flechas: aparecen solo cuando hay más pestañas hacia ese lado. -->
      @if (hayIzquierda()) {
        <button
          type="button"
          (click)="mover(-1)"
          aria-label="Ver las pestañas anteriores"
          class="absolute left-0 inset-y-0 w-9 flex items-center justify-start pl-1.5 rounded-l-xl bg-gradient-to-r from-gray-100 via-gray-100/90 to-transparent dark:from-dark-700 dark:via-dark-700/90 text-gray-600 dark:text-gray-300"
        >
          <i class="pi pi-chevron-left text-xs" aria-hidden="true"></i>
        </button>
      }
      @if (hayDerecha()) {
        <button
          type="button"
          (click)="mover(1)"
          aria-label="Ver más pestañas"
          class="absolute right-0 inset-y-0 w-9 flex items-center justify-end pr-1.5 rounded-r-xl bg-gradient-to-l from-gray-100 via-gray-100/90 to-transparent dark:from-dark-700 dark:via-dark-700/90 text-gray-600 dark:text-gray-300"
        >
          <i class="pi pi-chevron-right text-xs" aria-hidden="true"></i>
        </button>
      }
    </div>
  `,
})
export class Pestanas<T extends string = string> {
  readonly items = input.required<Pestana<T>[]>();
  readonly etiqueta = input('Secciones');
  readonly activa = model.required<T>();

  private destroyRef = inject(DestroyRef);
  private barra = viewChild.required<ElementRef<HTMLElement>>('barra');
  protected hayIzquierda = signal(false);
  protected hayDerecha = signal(false);

  /** Mira si queda algo por ver hacia cada lado de la barra. */
  protected medir(): void {
    const b = this.barra().nativeElement;
    this.hayIzquierda.set(b.scrollLeft > 4);
    this.hayDerecha.set(b.scrollLeft + b.clientWidth < b.scrollWidth - 4);
  }

  protected mover(sentido: -1 | 1): void {
    const b = this.barra().nativeElement;
    b.scrollBy({ left: sentido * b.clientWidth * 0.6, behavior: 'smooth' });
  }

  constructor() {
    afterNextRender(() => {
      this.medir();
      const observador = new ResizeObserver(() => this.medir());
      observador.observe(this.barra().nativeElement);
      this.destroyRef.onDestroy(() => observador.disconnect());
    });
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
