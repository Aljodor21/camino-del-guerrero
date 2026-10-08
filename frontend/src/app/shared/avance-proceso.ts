import { Proceso } from '../core/models/proceso.model';
import { diasEntre, hoyISO } from './fechas';

export interface AvanceProceso {
  /** Día del proceso; el de inicio es el día 1. */
  dia: number;
  semana: number;
  /** Solo si el proceso tiene fecha de fin planeada. */
  semanas: number | null;
  diasRestantes: number | null;
  porcentaje: number | null;
}

/** Dónde va un proceso en curso respecto a lo planeado. Null si aún no inicia. */
export function avanceProceso(p: Proceso): AvanceProceso | null {
  const hoy = hoyISO();
  if (p.fecha_inicio > hoy) return null;
  const dia = diasEntre(p.fecha_inicio, hoy) + 1;
  const semana = Math.ceil(dia / 7);
  if (!p.fecha_fin_plan)
    return { dia, semana, semanas: null, diasRestantes: null, porcentaje: null };
  const total = diasEntre(p.fecha_inicio, p.fecha_fin_plan) + 1;
  return {
    dia,
    semana,
    semanas: Math.ceil(total / 7),
    diasRestantes: diasEntre(hoy, p.fecha_fin_plan),
    porcentaje: Math.min(100, Math.round((dia / total) * 100)),
  };
}
