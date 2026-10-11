export type GrupoMinuta =
  | 'sustitutos'
  | 'lacteos'
  | 'carnes'
  | 'leguminosas'
  | 'cereales'
  | 'verduras'
  | 'frutas'
  | 'grasas'
  | 'semillas'
  | 'agua';

/** Grupos de la lista de intercambios: los de la minuta (sin agua) más los libres. */
export type GrupoAlimento = Exclude<GrupoMinuta, 'agua'> | 'libres';

export type TiempoComida = 'desayuno' | 'onces' | 'almuerzo' | 'algo' | 'cena' | 'merienda';

/** Porciones por comida; `dia` es el total del día (lo que no va en comidas se come cuando se quiera). */
export type FilaMinuta = Partial<Record<TiempoComida | 'dia', number>>;

export type PorcionesMinuta = Partial<Record<GrupoMinuta, FilaMinuta>>;

export type OrigenMinuta = 'nutricionista' | 'ia';

/** Porciones que un suplemento cubre en su comida. */
export type Reemplazo = Partial<Record<GrupoMinuta, number>>;

/** Minuta patrón del proceso. Una vez guardada no cambia: se guarda otra. */
export interface Minuta {
  id: number;
  proceso: number;
  origen: OrigenMinuta;
  porciones: PorcionesMinuta;
  tiempos: TiempoComida[];
  /** Lo del día que no va en una comida fija (agua, semillas). */
  durante_el_dia: Partial<Record<GrupoMinuta, number>>;
  kcal: number | null;
  proteina_g_kg: number | null;
  menu_ejemplo: Partial<Record<TiempoComida, string>>;
  recomendaciones: string;
  tiene_archivo: boolean;
  fecha_creacion: string;
}

/** Lo que se guarda: llenado en la plantilla, leído de un PDF o calculado por la IA. */
export interface MinutaPayload {
  origen: OrigenMinuta;
  /** Por defecto, el proceso vigente; al crear uno programado, ese. */
  proceso?: number;
  porciones: PorcionesMinuta;
  kcal: number | null;
  proteina_g_kg: number | null;
  menu_ejemplo: Partial<Record<TiempoComida, string>>;
  recomendaciones: string;
  /** Solo en un plan nuevo: hasta cuándo va (null = sin definir). Sin esta llave, no se toca. */
  fecha_fin_plan?: string | null;
}

export interface MinutaCalculada extends MinutaPayload {
  explicacion: string;
}

export type ReglaPorFuera = 'entre_semana' | 'siempre';

export interface PreferenciasComida {
  por_fuera: Partial<Record<TiempoComida, ReglaPorFuera>>;
}

export interface ComponenteComida {
  id: number;
  grupo: GrupoAlimento;
  alimento_id: number;
  alimento: string;
  porciones: number;
  cantidad: string;
  gramos: number | null;
}

export interface RequeridoComida {
  grupo: GrupoMinuta;
  grupo_nombre: string;
  porciones: number;
  /** Para comer por fuera: cuánto es, con un alimento de la lista. */
  ejemplo: string;
}

export interface SuplementoEnComida {
  id: number;
  nombre: string;
  scoops: number | null;
  reemplaza: Reemplazo;
}

export interface ComidaMenu {
  id: number;
  fecha: string;
  tiempo: TiempoComida;
  tiempo_nombre: string;
  nombre: string;
  por_fuera: boolean;
  cambiada: boolean;
  componentes: ComponenteComida[];
  suplementos: SuplementoEnComida[];
  requerido: RequeridoComida[];
}

export interface PorcionDelDia {
  grupo: GrupoMinuta;
  grupo_nombre: string;
  porciones: number;
}

export interface MenuSemanal {
  id: number;
  /** Lunes de la semana. */
  semana: string;
  minuta: number;
  generado_con_ia: boolean;
  durante_el_dia: PorcionDelDia[];
  comidas: ComidaMenu[];
}

export interface OpcionIntercambio {
  id: number;
  nombre: string;
  subgrupo: string;
  cantidad: string;
  gramos: number | null;
}

export type MotivoCambio = 'tiempo' | 'ingredientes' | 'antojo';
