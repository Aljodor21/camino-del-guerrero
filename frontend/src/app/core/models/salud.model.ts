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
  /** De qué plan y hora salió («id@08:00»), o vacío si se anotó suelta. */
  plan: string;
  se_puede_borrar: boolean;
}

/** Un suplemento con su plan: qué, cuánto, qué días (lunes = 0), a qué horas y cuánto dura. */
export interface PlanSuplemento {
  id: string;
  nombre: string;
  cantidad: string;
  dias: number[];
  horas: string[];
  inicio: string;
  /** Días de tratamiento, o null si no tiene fin. */
  duracion_dias: number | null;
  nota: string;
  avisar: boolean;
}

/** El plan con lo que calcula el servidor. */
export interface PlanSuplementoEstado extends PlanSuplemento {
  fin: string | null;
  termino: boolean;
  toca_hoy: boolean;
  /** En qué día del tratamiento va (null si no ha empezado o ya terminó). */
  dia_tratamiento: number | null;
}

export interface TomaDeHoy {
  clave: string;
  hora: string;
  nombre: string;
  cantidad: string;
  tomada: boolean;
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
  // Solo en otros suplementos.
  planes?: PlanSuplementoEstado[];
  de_hoy?: TomaDeHoy[];
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
  plan?: string;
}
