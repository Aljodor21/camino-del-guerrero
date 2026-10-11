export type TipoAviso = 'agua' | 'toma' | 'dormir' | 'entreno' | 'recordatorio' | 'comida' | 'proceso';

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
  scoops: number | null;
  hecha: boolean;
}

export interface ResumenHoy {
  fecha: string;
  agua: { meta: number; vasos: number; ml_vaso: number };
  tomas: TomaDeHoy[];
  entreno: { toca: boolean; hecho: boolean };
  dormir: { hora: string | null; acostado: string | null };
}
