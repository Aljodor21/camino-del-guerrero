import { Injectable, computed, inject, signal } from '@angular/core';
import { firstValueFrom } from 'rxjs';

import { Hito, Logros } from '../models/logros.model';
import { hoyISO } from '../../shared/fechas';
import { AudioService } from './audio';
import { AuthService } from './auth';
import { AvisosService } from './avisos';

export type Fiesta = { tipo: 'dia' } | { tipo: 'hitos'; hitos: Hito[] };

const PREFS = 'cdg_efectos';
/** Cada cuánto como máximo se pregunta al servidor si hay algo que celebrar. */
const ENTRE_REVISIONES_MS = 20_000;

interface Prefs {
  sonido: boolean;
  vibracion: boolean;
}

function leerPrefs(): Prefs {
  try {
    const crudo = JSON.parse(localStorage.getItem(PREFS) ?? '{}') as Partial<Prefs>;
    return { sonido: crudo.sonido === true, vibracion: crudo.vibracion !== false };
  } catch {
    return { sonido: false, vibracion: true };
  }
}

/**
 * Lo que hace que anotar se sienta bien: un salto del anillo, una vibración y un sonido suaves
 * (el sonido viene apagado), y una celebración cuando se cierra el día al 100 % o se logra un hito.
 * Las celebraciones salen de lo registrado: nada se inventa ni se puede inflar.
 */
@Injectable({ providedIn: 'root' })
export class CelebracionesService {
  private avisos = inject(AvisosService);
  private audio = inject(AudioService);
  private auth = inject(AuthService);

  private _prefs = signal<Prefs>(leerPrefs());
  readonly sonido = computed(() => this._prefs().sonido);
  readonly vibracion = computed(() => this._prefs().vibracion);

  /** Cuánto lleva el día y la última foto de los logros. */
  readonly logros = signal<Logros | null>(null);
  readonly hoy = computed(() => this.logros()?.hoy?.porcentaje ?? null);
  /** Sube con cada registro para que el anillo dé un salto. */
  readonly pulso = signal(false);
  readonly fiesta = signal<Fiesta | null>(null);

  private ultima = 0;
  private enCurso = false;
  /** Los hitos que ya se pusieron en pantalla en esta sesión: no se repiten aunque se pregunte dos veces. */
  private mostrados = new Set<string>();
  private cola: Fiesta[] = [];

  fijar(cambio: Partial<Prefs>): void {
    const nuevo = { ...this._prefs(), ...cambio };
    this._prefs.set(nuevo);
    try {
      localStorage.setItem(PREFS, JSON.stringify(nuevo));
    } catch {
      // Sin almacenamiento solo se pierde recordar la preferencia.
    }
    if (cambio.sonido) this.audio.registro();
    if (cambio.vibracion) this.vibrar(30);
  }

  /** Algo se acaba de anotar: se siente y se revisa si hay algo que celebrar. */
  registro(): void {
    this.pulso.set(true);
    setTimeout(() => this.pulso.set(false), 700);
    this.vibrar([18]);
    if (this.sonido()) this.audio.registro();
    void this.revisar(true);
  }

  /** Pregunta al servidor cómo va el día y si hay hitos nuevos. */
  async revisar(forzar = false): Promise<void> {
    if (!this.auth.isLoggedIn() || this.auth.isAdmin()) return;
    if (this.enCurso || (!forzar && Date.now() - this.ultima < ENTRE_REVISIONES_MS)) return;
    this.ultima = Date.now();
    this.enCurso = true;
    try {
      const logros = await firstValueFrom(this.avisos.logros());
      this.logros.set(logros);
      const fiestas: Fiesta[] = [];
      if (logros.hoy?.porcentaje === 100 && !this.yaSeCelebroElDia()) {
        this.marcarDia();
        fiestas.push({ tipo: 'dia' });
      }
      const nuevos = logros.hitos.filter((h) => h.nuevo && !this.mostrados.has(h.id));
      nuevos.forEach((h) => this.mostrados.add(h.id));
      if (nuevos.length) fiestas.push({ tipo: 'hitos', hitos: nuevos });
      if (fiestas.length) this.encolar(fiestas);
    } catch {
      // Sin conexión no se celebra: no pasa nada, se revisa la próxima vez.
    } finally {
      this.enCurso = false;
    }
  }

  /** La persona cerró la celebración: si había hitos, quedan vistos y sale la siguiente. */
  cerrar(): void {
    const actual = this.fiesta();
    if (actual?.tipo === 'hitos') {
      this.avisos
        .marcarHitosVistos(actual.hitos.map((h) => h.id))
        .subscribe({ error: () => undefined });
    }
    this.fiesta.set(this.cola.shift() ?? null);
    if (this.fiesta()) this.sonar(this.fiesta()!);
  }

  private encolar(fiestas: Fiesta[]): void {
    this.cola.push(...fiestas);
    if (this.fiesta()) return;
    this.fiesta.set(this.cola.shift() ?? null);
    if (this.fiesta()) this.sonar(this.fiesta()!);
  }

  private sonar(fiesta: Fiesta): void {
    this.vibrar([40, 60, 40]);
    if (this.sonido()) fiesta.tipo === 'dia' ? this.audio.diaCompleto() : this.audio.registro();
  }

  private vibrar(patron: number | number[]): void {
    if (!this.vibracion()) return;
    try {
      navigator.vibrate?.(patron);
    } catch {
      // Sin vibración en este dispositivo.
    }
  }

  private llaveDia(): string {
    return `cdg_dia_completo_${this.auth.usuario()?.id ?? 'x'}_${hoyISO()}`;
  }

  private yaSeCelebroElDia(): boolean {
    try {
      return localStorage.getItem(this.llaveDia()) === '1';
    } catch {
      return false;
    }
  }

  private marcarDia(): void {
    try {
      localStorage.setItem(this.llaveDia(), '1');
    } catch {
      // Sin almacenamiento podría repetirse la celebración: es lo peor que pasa.
    }
  }
}
