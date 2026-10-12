import { ChangeDetectionStrategy, Component, computed, inject, input, signal } from '@angular/core';
import { DatePipe, DecimalPipe } from '@angular/common';

import { APK_URL, ApkService } from '../../core/services/apk';

/**
 * La tarjeta para bajar la app de Android: titular, botón con la versión, el peso y la fecha del
 * último release, y un celular de muestra. Es oscura en cualquier tema, como el home. Dentro de la
 * app instalada sirve para actualizarla (se instala encima y conserva la sesión).
 */
@Component({
  selector: 'app-descarga-apk',
  templateUrl: './descarga-apk.html',
  styleUrl: './descarga-apk.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [DatePipe, DecimalPipe],
})
export class DescargaApk {
  protected apk = inject(ApkService);

  /** El titular es el h1 de la pantalla; en el home es un h2. */
  readonly titulo1 = input(false);

  protected url = APK_URL;
  protected copiado = signal(false);

  protected titular = computed(() =>
    this.apk.enLaApp ? 'Mantén tu app al día.' : 'Tu camino, en el bolsillo.',
  );
  protected bajada = computed(() =>
    this.apk.enLaApp
      ? 'Descarga la última versión: se instala encima de la que tienes y conservas tu sesión y tus datos.'
      : 'Instala Camino del Guerrero en tu celular Android. Se abre a pantalla completa, guarda tu sesión y trae lo mismo que ves en la web.',
  );

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
