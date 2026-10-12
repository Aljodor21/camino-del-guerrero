import { Injectable } from '@angular/core';

@Injectable({ providedIn: 'root' })
export class AudioService {
  private ctx: AudioContext | null = null;

  private getCtx(): AudioContext | null {
    try {
      if (!this.ctx) this.ctx = new AudioContext();
      if (this.ctx.state === 'suspended') this.ctx.resume();
      return this.ctx;
    } catch {
      return null;
    }
  }

  private tono(
    freq: number,
    duracion: number,
    inicio = 0,
    tipo: OscillatorType = 'sine',
    volumen = 0.3,
  ): void {
    const ctx = this.getCtx();
    if (!ctx) return;
    try {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.type = tipo;
      osc.frequency.setValueAtTime(freq, ctx.currentTime + inicio);
      gain.gain.setValueAtTime(volumen, ctx.currentTime + inicio);
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + inicio + duracion);
      osc.start(ctx.currentTime + inicio);
      osc.stop(ctx.currentTime + inicio + duracion + 0.05);
    } catch {
      /* sin soporte */
    }
  }

  /** Tick corto — últimos segundos del countdown */
  tick(): void {
    this.tono(1100, 0.07, 0, 'sine', 0.2);
  }

  /** Al iniciar una serie — dos tonos ascendentes: ¡listo! */
  iniciarSerie(): void {
    this.tono(440, 0.12, 0.0, 'sine', 0.3);
    this.tono(660, 0.18, 0.14, 'sine', 0.3);
  }

  /** Al completar una serie — dos beeps rápidos de éxito */
  completarSerie(): void {
    this.tono(660, 0.1, 0.0, 'sine', 0.3);
    this.tono(880, 0.2, 0.12, 'sine', 0.35);
  }

  /** Al empezar el descanso — tono grave y suave */
  iniciarDescanso(): void {
    this.tono(330, 0.5, 0, 'sine', 0.25);
  }

  /** Al terminar el descanso (o saltarlo) — tres tonos ascendentes: ¡a moverse! */
  finDescanso(): void {
    this.tono(523, 0.1, 0.0, 'square', 0.18);
    this.tono(659, 0.1, 0.11, 'square', 0.18);
    this.tono(784, 0.25, 0.22, 'square', 0.18);
  }

  /** Al finalizar la sesión completa — fanfarria corta */
  sesionFinalizada(): void {
    const notas = [523, 659, 784, 1047];
    notas.forEach((freq, i) => this.tono(freq, 0.22, i * 0.15, 'sine', 0.3));
  }
}
