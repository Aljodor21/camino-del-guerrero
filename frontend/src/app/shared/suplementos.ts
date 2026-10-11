import { Liquido, Suplemento, TipoSuplemento, Toma } from '../core/models/suplemento.model';
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

/** Lo que trae la etiqueta del envase, como lo escribe el usuario. */
export interface Etiqueta {
  peso: number | null;
  unidad: 'kg' | 'lb' | 'g';
  porcionG: number | null;
  scoops: number | null;
  porcionesDia: number | null;
  /** Con qué se mezcla y cuántos litros lleva la porción del día (opcional). */
  liquido: Liquido;
  liquidoL: number | null;
}

const GRAMOS_POR: Record<Etiqueta['unidad'], number> = { kg: 1000, lb: 453.592, g: 1 };

export function etiquetaVacia(): Etiqueta {
  return { peso: null, unidad: 'kg', porcionG: null, scoops: null, porcionesDia: 1, liquido: '', liquidoL: null };
}

/** La etiqueta de un suplemento guardado: en kg si es redondo, en libras si son libras enteras. */
export function etiquetaDe(
  s: Pick<
    Suplemento,
    'peso_envase_g' | 'porcion_g' | 'scoops_porcion' | 'porciones_dia' | 'liquido' | 'liquido_ml'
  >,
): Etiqueta {
  const g = s.peso_envase_g;
  const libras = g === null ? 0 : g / GRAMOS_POR.lb;
  const enKg = g !== null && g % 100 === 0;
  const enLb = !enKg && g !== null && Math.abs(libras - Math.round(libras)) * GRAMOS_POR.lb < 1.5;
  return {
    peso: g === null ? null : enKg ? g / 1000 : enLb ? Math.round(libras) : g,
    unidad: enKg || g === null ? 'kg' : enLb ? 'lb' : 'g',
    porcionG: s.porcion_g === null ? null : Number(s.porcion_g),
    scoops: s.scoops_porcion === null ? null : Number(s.scoops_porcion),
    porcionesDia: Number(s.porciones_dia),
    liquido: s.liquido,
    liquidoL: s.liquido_ml === null ? null : s.liquido_ml / 1000,
  };
}

export function gramosEnvase(e: Etiqueta): number | null {
  return e.peso === null ? null : Math.round(e.peso * GRAMOS_POR[e.unidad]);
}

/** Porciones completas que trae el envase. */
export function porcionesPorEnvase(e: Etiqueta): number | null {
  const g = gramosEnvase(e);
  if (g === null || !e.porcionG) return null;
  return Math.floor(g / e.porcionG) || null;
}

/** Lo que está mal escrito; vacío si todo se puede guardar (todo es opcional menos las del día). */
export function erroresEtiqueta(e: Etiqueta): Partial<Record<keyof Etiqueta, string>> {
  const errores: Partial<Record<keyof Etiqueta, string>> = {};
  const malEscritos = (['peso', 'porcionG', 'scoops', 'liquidoL'] as const).filter((k) =>
    Number.isNaN(e[k]),
  );
  for (const k of malEscritos) errores[k] = 'Escribe solo el número.';
  if (malEscritos.length) return errores;
  const g = gramosEnvase(e);
  if (g !== null && (g < 50 || g > 20000)) errores.peso = 'Revisa el peso del envase.';
  if (e.porcionG !== null && (e.porcionG < 1 || e.porcionG > 500))
    errores.porcionG = 'Entre 1 y 500 g.';
  if (e.scoops !== null && (e.scoops < 0.5 || e.scoops > 10 || (e.scoops * 2) % 1))
    errores.scoops = 'Entre 0,5 y 10.';
  if (e.liquido && e.liquidoL !== null && (e.liquidoL < 0.01 || e.liquidoL > 5))
    errores.liquidoL = 'Entre 0,01 y 5 litros.';
  if (g !== null && e.porcionG !== null && !errores.peso && !errores.porcionG && g < e.porcionG)
    errores.porcionG = 'La porción no puede pesar más que el envase.';
  return errores;
}

/** Lo que se manda al backend. */
export function payloadEtiqueta(e: Etiqueta) {
  return {
    peso_envase_g: gramosEnvase(e),
    porcion_g: e.porcionG,
    scoops_porcion: e.scoops,
    porciones_dia: 1,
    liquido: e.liquido,
    liquido_ml: e.liquido && e.liquidoL !== null ? Math.round(e.liquidoL * 1000) : null,
  };
}

/** Reparte los scoops de la porción entre las comidas, de medio en medio. */
export function repartirScoops(total: number, comidas: number): number[] {
  if (comidas === 0) return [];
  const base = Math.floor((total / comidas) * 2) / 2;
  let resto = Math.round((total - base * comidas) * 2) / 2;
  return Array.from({ length: comidas }, () => {
    const extra = resto > 0 ? Math.min(0.5, resto) : 0;
    resto -= extra;
    return base + extra;
  });
}

/** Lo que falta (+) o sobra (−) para completar la porción con las tomas. */
export function scoopsFaltantes(tomas: Toma[], total: number | null): number {
  if (!total || tomas.length === 0) return 0;
  return Math.round((total - tomas.reduce((s, t) => s + (t.scoops ?? 0), 0)) * 2) / 2;
}
