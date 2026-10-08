import { Suplemento, TipoSuplemento } from '../core/models/suplemento.model';
import { TIPOS_SUPLEMENTO } from '../core/constants/proceso';
import { diasEntre, hoyISO } from './fechas';

export function tipoSuplemento(tipo: TipoSuplemento) {
  return TIPOS_SUPLEMENTO.find((t) => t.value === tipo)!;
}

/** "la proteína", "Whey Gold". */
export function nombreSuplemento(s: Pick<Suplemento, 'tipo' | 'nombre'>): string {
  if (s.nombre) return s.nombre;
  const t = tipoSuplemento(s.tipo);
  return `${t.articulo} ${s.tipo === 'otro' ? 'suplemento' : t.label.toLowerCase()}`;
}

/** 90 → "3 meses", 14 → "2 semanas"; null → "todo el proceso". */
export function duracionEnPalabras(dias: number | null): string {
  if (dias === null) return 'todo el proceso';
  if (dias % 30 === 0) return dias === 30 ? '1 mes' : `${dias / 30} meses`;
  if (dias % 7 === 0) return dias === 7 ? '1 semana' : `${dias / 7} semanas`;
  return `${dias} días`;
}

/** Dónde va: día actual, total y cuánto le queda al envase. */
export function avanceSuplemento(s: Suplemento) {
  const hoy = hoyISO();
  const dia = Math.max(0, diasEntre(s.fecha_inicio, hoy)) + 1;
  const total = s.fin_estimado ? diasEntre(s.fecha_inicio, s.fin_estimado) + 1 : null;
  return {
    dia,
    total,
    porcentaje: total ? Math.min(100, Math.round((dia / total) * 100)) : null,
    diasRestantes: s.fin_estimado ? diasEntre(hoy, s.fin_estimado) : null,
    diasEnvase: s.se_acaba ? diasEntre(hoy, s.se_acaba) : null,
  };
}
