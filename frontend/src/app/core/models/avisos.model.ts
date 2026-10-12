export type TipoAviso =
  'agua' | 'toma' | 'dormir' | 'entreno' | 'recordatorio' | 'comida' | 'proceso';

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
}

export type HabitosPayload = Partial<Omit<Habitos, 'vasos_meta'>>;

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
  entreno: { toca: boolean; hecho: boolean };
  dormir: { hora: string | null; acostado: string | null };
}
