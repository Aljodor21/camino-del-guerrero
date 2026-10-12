import { GrupoMinuta, MotivoCambio, ReglaPorFuera, TiempoComida } from '../models/minuta.model';
import { Opcion } from './proceso';

export const GRUPOS_MINUTA: Record<GrupoMinuta, string> = {
  sustitutos: 'Sustitutos',
  lacteos: 'Lácteos',
  carnes: 'Carnes',
  leguminosas: 'Leguminosas',
  cereales: 'Cereales y tubérculos',
  verduras: 'Verduras',
  frutas: 'Frutas',
  grasas: 'Aceites y aguacate',
  semillas: 'Semillas',
  agua: 'Agua',
};

/** Qué entra en cada grupo, como lo explica la minuta. */
export const EJEMPLOS_GRUPO: Record<GrupoMinuta, string> = {
  sustitutos: 'huevo, queso, cuajada, jamón',
  lacteos: 'leche, yogur, kumis',
  carnes: 'res, cerdo, pollo, pescado',
  leguminosas: 'fríjol, lenteja, garbanzo',
  cereales: 'arroz, arepa, papa, plátano, avena',
  verduras: 'todas las verduras',
  frutas: 'todas las frutas',
  grasas: 'aceite, aguacate',
  semillas: 'maní, almendras, nueces',
  agua: 'agua potable',
};

export const ORDEN_GRUPOS = Object.keys(GRUPOS_MINUTA) as GrupoMinuta[];

/** `con`: cómo se nombra en una frase ("en las onces"). */
export const TIEMPOS_COMIDA: Record<TiempoComida, { label: string; hora: string; con: string }> = {
  desayuno: { label: 'Desayuno', hora: 'Mañana', con: 'el desayuno' },
  onces: { label: 'Onces', hora: 'Media mañana', con: 'las onces' },
  almuerzo: { label: 'Almuerzo', hora: 'Mediodía', con: 'el almuerzo' },
  algo: { label: 'Algo', hora: 'Media tarde', con: 'el algo' },
  cena: { label: 'Cena', hora: 'Noche', con: 'la cena' },
  merienda: { label: 'Merienda', hora: 'Antes de dormir', con: 'la merienda' },
};

export const OPCIONES_POR_FUERA: Opcion<ReglaPorFuera | null>[] = [
  { label: 'En casa', value: null },
  { label: 'Fuera entre semana', value: 'entre_semana' },
  { label: 'Fuera siempre', value: 'siempre' },
];

export const MOTIVOS_CAMBIO: Opcion<MotivoCambio>[] = [
  { label: 'No tengo tiempo de cocinar', value: 'tiempo' },
  { label: 'No tengo los ingredientes', value: 'ingredientes' },
  { label: 'Quiero otra cosa', value: 'antojo' },
];

/** "1 porción de lácteos", "10 vasos de agua". */
export function porcionesDe(grupo: GrupoMinuta, porciones: number): string {
  const n = porciones.toLocaleString('es-CO', { maximumFractionDigits: 1 });
  if (grupo === 'agua') return `${n} ${porciones === 1 ? 'vaso' : 'vasos'} de agua`;
  return `${n} ${porciones === 1 ? 'porción' : 'porciones'} de ${GRUPOS_MINUTA[grupo].toLowerCase()}`;
}
