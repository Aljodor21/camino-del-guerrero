export type ClaseToma = 'dosis' | 'observacion';

export interface TomaSalud {
  id: number;
  fecha: string;
  clase: ClaseToma;
  nombre: string;
  cantidad: string;
  animo: number | null;
  energia: number | null;
  nota: string;
  /** Se anotó en un día que el protocolo no marcaba. */
  fuera_de_protocolo: boolean;
  se_puede_borrar: boolean;
}

export interface DiaProtocolo {
  fase: 'sin_empezar' | 'ciclo' | 'descanso';
  /** De 1 a 4, solo en ciclo. */
  dia: number | null;
  vuelta: number;
  semana: number;
}

export interface AjustesFadiman {
  sustancia: string;
  dosis: string;
  inicio: string;
  semanas_ciclo: number;
  semanas_descanso: number;
  avisar: boolean;
  hora_aviso: string;
  rango_ciclo: [number, number];
  rango_descanso: [number, number];
}

/** Lo que responde la API de Salud: el estado entero en cada llamada. */
export interface EstadoSalud {
  tipo: 'fadiman' | 'otros_suplementos';
  hoy: string;
  tomas: TomaSalud[];
  cuidados: string[];
  frecuentes: { nombre: string; cantidad: string }[];
  // Solo en el protocolo.
  dia?: DiaProtocolo;
  etapa?: [string, string] | null;
  toma_hoy?: boolean;
  observacion_hoy?: boolean;
  siguiente_toma?: string | null;
  primer_ciclo?: { previstas: number; hechas: number };
  ajustes?: AjustesFadiman;
}

export interface TomaPayload {
  clase?: ClaseToma;
  nombre?: string;
  cantidad?: string;
  animo?: number | null;
  energia?: number | null;
  nota?: string;
}
