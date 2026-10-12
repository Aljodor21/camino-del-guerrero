import { ChangeDetectionStrategy, Component, inject } from '@angular/core';

import { ApkService } from '../core/services/apk';
import { DescargaApk } from '../shared/descarga-apk/descarga-apk';

/** "Descargar la app": la tarjeta de descarga y los pasos para instalarla. */
@Component({
  selector: 'app-descargar-app',
  templateUrl: './descargar-app.html',
  styleUrl: './descargar-app.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [DescargaApk],
})
export class DescargarApp {
  protected apk = inject(ApkService);
}
