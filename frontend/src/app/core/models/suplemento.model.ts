import { Reemplazo, TiempoComida } from './minuta.model';

export type TipoSuplemento = 'hipercalorico' | 'proteina' | 'creatina' | 'otro';

export type Liquido = '' | 'agua' | 'leche';

export interface Suplemento {
  id: number;
  tipo: TipoSuplemento;
  tipo_nombre: string;
  nombre: string;
  fecha_inicio: string;
  /** null: va mientras dure el proceso. */
  duracion_dias: number | null;
  duracion_confirmada: boolean;
  /** Las anotadas a mano; si es null, salen de la etiqueta (peso / porción). */
  porciones_envase: number | null;
  /** Lo que dice la etiqueta. */
  peso_envase_g: number | null;
  porcion_g: number | null;
  scoops_porcion: number | null;
  porciones_por_envase: number | null;
  /** Con qué se mezcla y cuántos ml lleva la porción del día; opcional. */
  liquido: Liquido;
  liquido_ml: number | null;
  porciones_dia: number;
  envase_desde: string;
  fecha_fin: string | null;
  fin_estimado: string | null;
  dias_envase: number | null;
  se_acaba: string | null;
  proceso: number;
  /** En qué comidas se toma la porción del día. Vacío si aún no se sabe. */
  tomas: Toma[];
  /** Enlace con la información nutricional (opcional). */
  info_url: string;
  /** Hay foto del producto (el pote); es privada. */
  tiene_foto: boolean;
  /** La foto o el PDF de la etiqueta que subió el usuario; null si no hay. */
  info_archivo_tipo: 'pdf' | 'imagen' | null;
}

/** Una toma: la comida, cuántos scoops lleva y qué porciones de esa comida reemplaza. */
export interface Toma {
  tiempo: TiempoComida;
  scoops: number | null;
  /** Vacío: se suma a lo que indica la minuta. */
  reemplaza: Reemplazo;
}

export type SuplementoPayload = Pick<
  Suplemento,
  | 'nombre'
  | 'duracion_dias'
  | 'duracion_confirmada'
  | 'porciones_envase'
  | 'peso_envase_g'
  | 'porcion_g'
  | 'scoops_porcion'
  | 'porciones_dia'
  | 'liquido'
  | 'liquido_ml'
> &
  Partial<Pick<Suplemento, 'tomas' | 'info_url'>>;

export type CrearSuplementoPayload = SuplementoPayload &
  Pick<Suplemento, 'tipo'> & {
    /** Por defecto, el proceso vigente. */
    proceso?: number;
  };

export type AccionSuplemento = 'abrir-envase' | 'continuar' | 'terminar' | 'reemplazar';
