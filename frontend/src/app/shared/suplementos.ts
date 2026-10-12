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
  /** Con qué se mezcla (opcional), cuántos ml de líquido lleva la porción del día y cuántos son leche. */
  liquido: Liquido;
  liquidoMl: number | null;
  lecheMl: number | null;
  /** Tabla nutricional de la leche por porción (opcional): ml de la porción, calorías y proteína. */
  lechePorcionMl: number | null;
  lecheKcal: number | null;
  lecheProteina: number | null;
}

const GRAMOS_POR: Record<Etiqueta['unidad'], number> = { kg: 1000, lb: 453.592, g: 1 };

export function etiquetaVacia(): Etiqueta {
  return {
    peso: null,
    unidad: 'kg',
    porcionG: null,
    scoops: null,
    porcionesDia: 1,
    liquido: '',
    liquidoMl: null,
    lecheMl: null,
    lechePorcionMl: null,
    lecheKcal: null,
    lecheProteina: null,
  };
}

/** La etiqueta de un suplemento guardado: en kg si es redondo, en libras si son libras enteras. */
export function etiquetaDe(
  s: Pick<
    Suplemento,
    | 'peso_envase_g'
    | 'porcion_g'
    | 'scoops_porcion'
    | 'porciones_dia'
    | 'liquido'
    | 'liquido_ml'
    | 'leche_ml'
    | 'leche_nutricional'
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
    liquidoMl: s.liquido_ml,
    lecheMl: s.leche_ml,
    lechePorcionMl: s.leche_nutricional?.porcion_ml ?? null,
    lecheKcal: s.leche_nutricional?.kcal ?? null,
    lecheProteina: s.leche_nutricional?.proteina_g ?? null,
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
  const malEscritos = (
    [
      'peso',
      'porcionG',
      'scoops',
      'liquidoMl',
      'lecheMl',
      'lechePorcionMl',
      'lecheKcal',
      'lecheProteina',
    ] as const
  ).filter((k) => Number.isNaN(e[k]));
  for (const k of malEscritos) errores[k] = 'Escribe solo el número.';
  if (malEscritos.length) return errores;
  const g = gramosEnvase(e);
  if (g !== null && (g < 50 || g > 20000)) errores.peso = 'Revisa el peso del envase.';
  if (e.porcionG !== null && (e.porcionG < 1 || e.porcionG > 1000))
    errores.porcionG = 'Entre 1 y 1.000 g.';
  if (e.scoops !== null && (e.scoops < 0.5 || e.scoops > 20 || (e.scoops * 2) % 1))
    errores.scoops = 'Entre 0,5 y 20, de medio en medio.';
  if (e.liquido && e.liquidoMl !== null && (e.liquidoMl < 10 || e.liquidoMl > 5000))
    errores.liquidoMl = 'Entre 10 y 5.000 ml.';
  if (e.liquido === 'mezcla') {
    if (e.lecheMl === null || !e.liquidoMl)
      errores.lecheMl = 'Escribe cuánto líquido lleva y cuánto de ese es leche.';
    else if (e.lecheMl < 10 || e.lecheMl >= e.liquidoMl)
      errores.lecheMl = 'La leche tiene que ser menos que el líquido total.';
  }
  const tablaLeche = [e.lechePorcionMl, e.lecheKcal, e.lecheProteina];
  if (tablaLeche.some((v) => v !== null) && tablaLeche.some((v) => v === null))
    errores.lecheKcal = 'Escribe los ml de la porción, las calorías y la proteína de la leche.';
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
    liquido_ml: e.liquido && e.liquidoMl !== null ? Math.round(e.liquidoMl) : null,
    leche_ml: e.liquido === 'mezcla' ? e.lecheMl : null,
    leche_nutricional:
      (e.liquido === 'leche' || e.liquido === 'mezcla') && e.lechePorcionMl !== null
        ? { porcion_ml: e.lechePorcionMl, kcal: e.lecheKcal!, proteina_g: e.lecheProteina! }
        : null,
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
