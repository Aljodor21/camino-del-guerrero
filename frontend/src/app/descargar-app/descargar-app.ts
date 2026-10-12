import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { DatePipe, DecimalPipe } from '@angular/common';

import { APK_URL, ApkService } from '../core/services/apk';

/**
 * "Descarga la app": la última versión del APK de Android, con su versión, peso y fecha, y los
 * pasos para instalarla. La cabecera es oscura siempre, como el home.
 */
@Component({
  selector: 'app-descargar-app',
  templateUrl: './descargar-app.html',
  styleUrl: './descargar-app.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [DatePipe, DecimalPipe],
})
export class DescargarApp {
  protected apk = inject(ApkService);

  protected url = APK_URL;
  protected copiado = signal(false);

  constructor() {
    void this.apk.cargar();
  }

  protected reintentar(): void {
    void this.apk.cargar(true);
  }

  protected megas(bytes: number): number {
    return bytes / 1_000_000; // MB como los muestra Android
  }

  protected async copiar(): Promise<void> {
    try {
      await navigator.clipboard.writeText(this.url);
    } catch {
      // Sin permiso de portapapeles (HTTP o navegador viejo): se selecciona en un campo temporal.
      const campo = document.createElement('textarea');
      campo.value = this.url;
      document.body.appendChild(campo);
      campo.select();
      document.execCommand('copy');
      campo.remove();
    }
    this.copiado.set(true);
    setTimeout(() => this.copiado.set(false), 2200);
  }
}
