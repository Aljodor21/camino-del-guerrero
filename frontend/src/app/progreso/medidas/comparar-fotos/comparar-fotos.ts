import { Component, ChangeDetectionStrategy, computed, input, output, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { SelectButtonModule } from 'primeng/selectbutton';

import { FotoProgreso, Medicion, Pose } from '../../../core/models/proceso.model';
import { POSES } from '../../../core/constants/proceso';
import { Foto } from '../../../shared/foto/foto';
import { diasEntre, formatearFecha, formatearNumero } from '../../../shared/fechas';

export interface FotoAmpliada {
  foto: FotoProgreso;
  medicion: Medicion;
}

interface Toma {
  medicion: Medicion;
  foto: FotoProgreso;
}

/** Compara la foto del punto de partida con cualquier otra en la misma pose. */
@Component({
  selector: 'app-comparar-fotos',
  templateUrl: './comparar-fotos.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [FormsModule, SelectButtonModule, Foto],
})
export class CompararFotos {
  /** Mediciones del usuario, de la más reciente a la más antigua. */
  readonly mediciones = input.required<Medicion[]>();
  readonly ampliar = output<FotoAmpliada>();

  protected formatearFecha = formatearFecha;
  protected num = formatearNumero;

  private poseElegida = signal<Pose | null>(null);
  private elegida = signal<number | null>(null);

  protected poses = computed(() => {
    const conFoto = new Set(this.mediciones().flatMap((m) => m.fotos.map((f) => f.pose)));
    return POSES.filter((p) => conFoto.has(p.value));
  });

  protected pose = computed(() => {
    const elegida = this.poseElegida();
    return this.poses().some((p) => p.value === elegida)
      ? elegida
      : (this.poses()[0]?.value ?? null);
  });

  /** Tomas en la pose activa, de la más antigua a la más reciente. */
  private tomas = computed<Toma[]>(() => {
    const pose = this.pose();
    return [...this.mediciones()].reverse().flatMap((medicion) => {
      const foto = medicion.fotos.find((f) => f.pose === pose);
      return foto ? [{ medicion, foto }] : [];
    });
  });

  /** El punto de partida: la foto de la medición inicial o, si no tiene, la primera que haya. */
  protected base = computed(() => {
    const tomas = this.tomas();
    return tomas.find((t) => t.medicion.es_inicial) ?? tomas[0] ?? null;
  });

  protected otras = computed(() => this.tomas().filter((t) => t !== this.base()));

  protected comparada = computed(() => {
    const otras = this.otras();
    return otras.find((t) => t.medicion.id === this.elegida()) ?? otras.at(-1) ?? null;
  });

  protected cambio = computed(() => {
    const base = this.base();
    const comparada = this.comparada();
    if (!base || !comparada) return null;
    return {
      kg: Math.round((comparada.medicion.peso_kg - base.medicion.peso_kg) * 10) / 10,
      dias: diasEntre(base.medicion.fecha, comparada.medicion.fecha),
    };
  });

  protected cambiarPose(pose: Pose): void {
    this.poseElegida.set(pose);
    this.elegida.set(null);
  }

  protected elegir(toma: Toma): void {
    this.elegida.set(toma.medicion.id);
  }
}
