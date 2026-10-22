export type GrupoHito = 'racha' | 'dias' | 'agua' | 'entreno' | 'comida' | 'proteina' | 'medicion';
export type NivelHito = 'bronce' | 'plata' | 'oro';

/** Un hito: se logra con lo registrado y nunca se pierde. */
export interface Hito {
  id: string;
  grupo: GrupoHito;
  nivel: NivelHito;
  nombre: string;
  descripcion: string;
  actual: number;
  meta: number;
  /** YYYY-MM-DD; null mientras no se logre. */
  logrado_en: string | null;
  logrado: boolean;
  /** Se logró hace poco y aún no se ha celebrado. */
  nuevo: boolean;
}

export interface Racha {
  actual: number;
  mejor: number;
  umbral: number;
  /** Aún no se ha usado el comodín de esta semana (lunes a domingo). */
  comodin_disponible: boolean;
  dias_salvados: string[];
}

export interface Logros {
  racha: Racha;
  hitos: Hito[];
  hoy: {
    porcentaje: number | null;
    en_proceso: boolean;
    /** Alimentación y deporte (si ese día toca entrenar): cada uno vale la mitad del día. */
    pilares: { id: 'alimentacion' | 'deporte'; nombre: string; porcentaje: number; peso: number }[];
    /** Hoy no cuenta: una pausa cubrió 8 horas o más (no suma ni corta la racha). */
    en_pausa?: boolean;
    /** Hoy terminó una pausa: la persona ya volvió. */
    volvio?: boolean;
  } | null;
  logrados: number;
  total: number;
}

export interface Capitulo {
  lunes: string;
  domingo: string;
  completa: boolean;
  es_actual: boolean;
  /** Promedio de los días que ya van. */
  porcentaje: number | null;
  /** Lo que lleva de la semana entera (7 días). */
  porcentaje_semana: number | null;
  dias_que_van: number;
  anterior: number | null;
  diferencia: number | null;
  titulo: string;
  frase: string;
  estaciones: { fecha: string; porcentaje: number | null; es_hoy: boolean }[];
  mejor_dia: { fecha: string; porcentaje: number } | null;
  para_mirar: { nombre: string; porcentaje: number } | null;
  hitos: Hito[];
}
