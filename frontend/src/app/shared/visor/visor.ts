import { ChangeDetectionStrategy, Component, computed, inject } from '@angular/core';
import { DomSanitizer } from '@angular/platform-browser';
import { DialogModule } from 'primeng/dialog';
import { ProgressSpinnerModule } from 'primeng/progressspinner';

import { VisorService } from '../../core/services/visor';

/** La ventana donde se ve cualquier foto o PDF de la app. Va una sola vez, en el layout. */
@Component({
  selector: 'app-visor',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [DialogModule, ProgressSpinnerModule],
  template: `
    <p-dialog
      [header]="visor.contenido()?.titulo ?? 'Archivo'"
      [visible]="visor.abierto()"
      (visibleChange)="!$event && visor.cerrar()"
      [modal]="true"
      [draggable]="false"
      [dismissableMask]="true"
      [style]="{ width: '96vw', maxWidth: '720px' }"
    >
      @if (visor.cargando()) {
        <div class="flex justify-center py-16"><p-progressspinner styleClass="w-10 h-10" /></div>
      } @else if (visor.error()) {
        <p class="text-sm text-red-600 dark:text-red-400 py-6" role="alert">{{ visor.error() }}</p>
      } @else if (visor.contenido(); as c) {
        @if (c.tipo === 'pdf') {
          <iframe
            [src]="pdf()"
            title="Vista del PDF"
            class="w-full h-[70vh] rounded-lg bg-white"
          ></iframe>
        } @else {
          <img
            [src]="c.url"
            [alt]="c.titulo"
            class="mx-auto max-h-[75vh] w-auto max-w-full rounded-lg object-contain"
          />
        }
      }
    </p-dialog>
  `,
})
export class Visor {
  protected visor = inject(VisorService);
  private sanitizer = inject(DomSanitizer);
  protected pdf = computed(() =>
    this.sanitizer.bypassSecurityTrustResourceUrl(this.visor.contenido()?.url ?? ''),
  );
}
