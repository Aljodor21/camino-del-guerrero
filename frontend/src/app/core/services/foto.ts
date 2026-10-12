import { Injectable, computed, effect, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, forkJoin, of } from 'rxjs';
import { map, shareReplay } from 'rxjs/operators';

import { AuthService } from './auth';
import { FotoProgreso, Pose } from '../models/proceso.model';
import { environment } from '../../../environments/environment';

const API = `${environment.apiUrl}/progreso`;
const LADO_MAXIMO = 1600;

export type TamanoFoto = 'mini' | 'completa';
export type FotosPorPose = Partial<Record<Pose, Blob>>;

/**
 * Prepara una foto del dispositivo antes de subirla: respeta la orientación de la cámara,
 * la reduce a 1600 px y la vuelve JPEG. Así sube rápido y sin los metadatos del teléfono.
 */
export async function prepararFoto(archivo: File): Promise<Blob> {
  const bitmap = await createImageBitmap(archivo, { imageOrientation: 'from-image' });
  const escala = Math.min(1, LADO_MAXIMO / Math.max(bitmap.width, bitmap.height));
  const canvas = document.createElement('canvas');
  canvas.width = Math.round(bitmap.width * escala);
  canvas.height = Math.round(bitmap.height * escala);
  canvas.getContext('2d')!.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  bitmap.close();
  return new Promise((resolve, reject) =>
    canvas.toBlob((blob) => (blob ? resolve(blob) : reject(new Error('foto'))), 'image/jpeg', 0.92),
  );
}

/**
 * Fotos de progreso. Son privadas: la API las entrega solo con el token del usuario,
 * por eso se descargan como blob y se muestran con una URL local.
 */
@Injectable({ providedIn: 'root' })
export class FotoService {
  private http = inject(HttpClient);
  private auth = inject(AuthService);
  private urls = new Map<string, Observable<string>>();
  private creadas: string[] = [];

  private usuarioId = computed(() => this.auth.usuario()?.id ?? null);

  constructor() {
    // Al cambiar de usuario se descartan las fotos del anterior.
    let anterior: number | null | undefined;
    effect(() => {
      const id = this.usuarioId();
      if (anterior !== undefined && anterior !== id) this.limpiar();
      anterior = id;
    });
  }

  url(id: number, tamano: TamanoFoto): Observable<string> {
    const clave = `${id}-${tamano}`;
    let url$ = this.urls.get(clave);
    if (!url$) {
      const params = tamano === 'mini' ? { tamano } : undefined;
      url$ = this.http.get(`${API}/fotos/${id}/`, { params, responseType: 'blob' }).pipe(
        map((blob) => {
          const url = URL.createObjectURL(blob);
          this.creadas.push(url);
          return url;
        }),
        shareReplay(1),
      );
      this.urls.set(clave, url$);
    }
    return url$;
  }

  subir(medicionId: number, pose: Pose, foto: Blob): Observable<FotoProgreso> {
    const datos = new FormData();
    datos.append('pose', pose);
    datos.append('imagen', foto, `${pose}.jpg`);
    return this.http.post<FotoProgreso>(`${API}/mediciones/${medicionId}/fotos/`, datos);
  }

  subirVarias(medicionId: number, fotos: FotosPorPose): Observable<FotoProgreso[]> {
    const envios = (Object.entries(fotos) as [Pose, Blob][]).map(([pose, foto]) =>
      this.subir(medicionId, pose, foto),
    );
    return envios.length ? forkJoin(envios) : of([]);
  }

  eliminar(id: number): Observable<void> {
    return this.http.delete<void>(`${API}/fotos/${id}/`);
  }

  private limpiar(): void {
    this.creadas.forEach((url) => URL.revokeObjectURL(url));
    this.creadas = [];
    this.urls.clear();
  }
}
