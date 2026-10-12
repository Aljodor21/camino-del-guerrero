import { Injectable, computed, signal } from '@angular/core';
import { PluginListenerHandle, registerPlugin } from '@capacitor/core';

import { APK_URL } from './apk';

interface ActualizadorNativo {
  descargarEInstalar(opciones: { url: string }): Promise<{ estado: 'instalando' | 'permiso' }>;
  addListener(
    evento: 'progreso',
    escuchar: (p: { bytes: number; total: number }) => void,
  ): Promise<PluginListenerHandle>;
}

/** El plugin nativo de Android (ActualizadorPlugin.java): solo existe dentro de la app instalada. */
const Actualizador = registerPlugin<ActualizadorNativo>('Actualizador');

export type FaseActualizacion = 'quieto' | 'descargando' | 'permiso' | 'instalando' | 'error';

/**
 * Actualiza la app desde adentro, sin abrir el navegador: baja el APK, el sistema abre su instalador
 * y la persona toca "Instalar". Si algo falla, queda el enlace de siempre para bajarlo con el navegador.
 */
@Injectable({ providedIn: 'root' })
export class ActualizadorService {
  readonly fase = signal<FaseActualizacion>('quieto');
  /** De 0 a 100; null si no se sabe el tamaño total. */
  readonly porcentaje = signal<number | null>(0);
  readonly error = signal('');
  readonly ocupado = computed(() => this.fase() === 'descargando' || this.fase() === 'instalando');

  async actualizar(): Promise<void> {
    if (this.ocupado()) return;
    this.error.set('');
    this.porcentaje.set(0);
    this.fase.set('descargando');
    let escucha: PluginListenerHandle | null = null;
    try {
      escucha = await Actualizador.addListener('progreso', ({ bytes, total }) =>
        this.porcentaje.set(total > 0 ? Math.min(100, Math.round((bytes / total) * 100)) : null),
      );
      const { estado } = await Actualizador.descargarEInstalar({ url: APK_URL });
      // 'permiso': Android abrió sus ajustes para que se active "instalar apps de esta fuente".
      this.fase.set(estado === 'permiso' ? 'permiso' : 'instalando');
    } catch (e) {
      this.error.set(e instanceof Error ? e.message : 'No pudimos descargar la actualización.');
      this.fase.set('error');
    } finally {
      await escucha?.remove();
    }
  }

  /** Después de aceptar el permiso, o si la persona cerró el instalador, se puede volver a intentar. */
  reiniciar(): void {
    this.fase.set('quieto');
    this.error.set('');
  }
}
