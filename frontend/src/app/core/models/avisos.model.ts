export type TipoAviso =
  'agua' | 'toma' | 'dormir' | 'levantar' | 'entreno' | 'recordatorio' | 'comida' | 'proceso';

/** Un aviso pendiente: sale de la bandeja solo cuando se confirma lo que pide. */
export interface Aviso {
  id: number;
  tipo: TipoAviso;
  fecha: string;
  programada_para: string;
  titulo: string;
  cuerpo: string;
  /** Texto del botón para confirmar ("Ya lo tomé"); vacío si se resuelve en otra parte. */
  accion: string;
  suplemento: number | null;
  recordatorio: number | null;
  datos: Record<string, unknown>;
}

/** Lo que indicó la nutricionista para el día a día. Todo es opcional. */
export interface Habitos {
  agua_ml: number | null;
  /** De cuántos ml es el vaso de la persona. */
  vaso_ml: number;
  vasos_meta: number;
  /** "HH:MM:SS" desde la API. */
  hora_levantarse: string | null;
  hora_dormir: string | null;
  hora_entreno: string | null;
  avisos_apagados: TipoAviso[];
  /** Horas distintas por día de la semana (1 = lunes): lo que falta usa la hora general. */
  horas_semana: Record<string, { levantarse?: string; dormir?: string }>;
  /** A qué hora come la persona cada tiempo; lo que falta usa la de referencia. */
  horas_comida: Record<string, string>;
  /** Entre qué horas se reparte el agua (vacío: de una hora después de levantarte a una antes de acostarte). */
  horas_agua: { inicio?: string; fin?: string };
  tiempos_comida: HoraDeComida[];
}

/** Un cambio de horas que la app propone según cómo usa la persona su día. */
export interface SugerenciaDeHoras {
  id: string;
  tipo: 'comida' | 'agua' | 'levantarse' | 'acostarse';
  titulo: string;
  texto: string;
  actual: string;
  sugerida: string;
  /** Lo que se guarda en los hábitos si la persona acepta. */
  cambios: Partial<Habitos>;
}

/** Una comida del plan con la hora a la que se come (la suya o la de referencia). */
export interface HoraDeComida {
  tiempo: string;
  nombre: string;
  hora: string;
  referencia: string;
  personalizada: boolean;
}

export interface HorasDelDia {
  levantarse: string | null;
  dormir: string | null;
  /** Se cambiaron solo para ese día. */
  personalizado: boolean;
}

export type HabitosPayload = Partial<Omit<Habitos, 'vasos_meta' | 'tiempos_comida'>>;

export interface TomaDeHoy {
  suplemento: number;
  nombre: string;
  tiempo: string;
  /** HH:MM si es otra toma a esa hora. */
  hora?: string | null;
  scoops: number | null;
  hecha: boolean;
}

export interface VasoTomado {
  momento: string;
  ml: number;
}

export interface ResumenHoy {
  fecha: string;
  agua: {
    meta: number;
    vasos: number;
    ml_vaso: number;
    meta_ml: number | null;
    ml_total: number;
    /** Cada vaso tomado hoy, con su tamaño y la hora exacta en que se anotó. */
    registros: VasoTomado[];
  };
  tomas: TomaDeHoy[];
  /** Las comidas del plan de hoy y si ya se contaron. */
  comidas: { tiempo: string; nombre: string; hora: string; contada: boolean }[];
  entreno: { toca: boolean; hecho: boolean };
  dormir: { hora: string | null; acostado: string | null };
  /** A qué hora se levantó hoy (si ya lo anotó) y cuánto durmió anoche. */
  levantar: {
    hora: string | null;
    levantado: string | null;
    dormiste_horas: number | null;
    /** Minutos antes (−) o después (+) de lo previsto: anoche al acostarte y hoy al levantarte. */
    acostarse_min: number | null;
    levantarse_min: number | null;
  };
  /** Las horas previstas de hoy y de mañana (se pueden cambiar solo por ese día). */
  horario: { hoy: HorasDelDia; manana: HorasDelDia };
}

export interface Noche {
  fecha: string;
  acostado: string;
  levantado: string;
  horas: number;
  dif_acostarse_min: number | null;
  dif_levantarse_min: number | null;
}

/** Cuánto se durmió entre dos fechas: de la hora en que anotó que se acostó a la que anotó que se levantó. */
export interface Sueno {
  desde: string;
  hasta: string;
  promedio_horas: number | null;
  noches: Noche[];
  promedio_acostarse_min: number | null;
  promedio_levantarse_min: number | null;
}

export type BloqueCumplimiento = 'comidas' | 'entreno' | 'tomas' | 'agua' | 'dormir';

/** Una parte del día que se mide: agua, dormir, comidas, proteína o entreno. */
export interface BloqueDelDia {
  id: BloqueCumplimiento;
  pilar: 'alimentacion' | 'deporte';
  nombre: string;
  peso: number;
  hecho: number;
  meta: number;
  porcentaje: number;
  detalle: string;
  /** Lo que faltó, dicho en una frase cada cosa. */
  faltas: string[];
}

export interface DiaCumplimiento {
  fecha: string;
  porcentaje: number | null;
  /** false antes de que empiece el proceso: solo cuentan el agua y dormir. */
  en_proceso: boolean;
  es_hoy: boolean;
  bloques: BloqueDelDia[];
  pilares: { id: 'alimentacion' | 'deporte'; nombre: string; porcentaje: number; peso: number }[];
}

export interface CumplimientoGlobal {
  desde: string;
  hasta: string;
  porcentaje: number | null;
  /** Cuánto lleva del periodo entero: los días que faltan cuentan como lo que aún no se hace. */
  porcentaje_periodo: number | null;
  /** Cuántos días tiene el periodo completo (7 en una semana). */
  dias_periodo: number;
  dias_cumplidos: number;
  racha_actual: number;
  mejor_racha: number;
  umbral_racha: number;
  /** Promedio de cada bloque en los días en que aplicó. */
  bloques: {
    id: BloqueCumplimiento;
    nombre: string;
    peso: number;
    porcentaje: number;
    dias: number;
  }[];
  dias: DiaCumplimiento[];
}
