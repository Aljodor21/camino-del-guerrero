import {
  FilaMinuta,
  GrupoMinuta,
  PorcionesMinuta,
  TiempoComida,
} from '../core/models/minuta.model';
import { ORDEN_GRUPOS, TIEMPOS_COMIDA } from '../core/constants/nutricion';

const ORDEN_TIEMPOS = Object.keys(TIEMPOS_COMIDA) as TiempoComida[];

export function enComidas(fila: FilaMinuta | undefined): number {
  return ORDEN_TIEMPOS.reduce((suma, t) => suma + (fila?.[t] ?? 0), 0);
}

/** Lo del día que no va en una comida fija. */
export function libreDe(fila: FilaMinuta | undefined): number {
  return Math.max(0, (fila?.dia ?? 0) - enComidas(fila));
}

/** Comidas que tienen alguna porción (sin contar el agua). */
export function tiemposDe(porciones: PorcionesMinuta): TiempoComida[] {
  return ORDEN_TIEMPOS.filter((t) =>
    ORDEN_GRUPOS.some((g) => g !== 'agua' && (porciones[g]?.[t] ?? 0) > 0),
  );
}

export function gruposEn(porciones: PorcionesMinuta, tiempo: TiempoComida | ''): GrupoMinuta[] {
  if (!tiempo) return [];
  return ORDEN_GRUPOS.filter((g) => g !== 'agua' && (porciones[g]?.[tiempo] ?? 0) > 0);
}

/** Cambia una celda y deja el total del día al día. `tiempo` null es lo libre del día. */
export function conValor(
  porciones: PorcionesMinuta,
  grupo: GrupoMinuta,
  tiempo: TiempoComida | null,
  valor: number,
): PorcionesMinuta {
  const fila: FilaMinuta = { ...porciones[grupo] };
  const libre = libreDe(fila);
  if (tiempo) fila[tiempo] = valor;
  fila.dia = enComidas(fila) + (tiempo ? libre : valor);
  return { ...porciones, [grupo]: fila };
}
