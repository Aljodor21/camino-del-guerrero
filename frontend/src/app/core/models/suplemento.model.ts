export type TipoSuplemento = 'hipercalorico' | 'proteina' | 'creatina' | 'otro';

export interface Suplemento {
  id: number;
  tipo: TipoSuplemento;
  tipo_nombre: string;
  nombre: string;
  fecha_inicio: string;
  /** null: va mientras dure el proceso. */
  duracion_dias: number | null;
  duracion_confirmada: boolean;
  porciones_envase: number | null;
  porciones_dia: number;
  envase_desde: string;
  fecha_fin: string | null;
  fin_estimado: string | null;
  dias_envase: number | null;
  se_acaba: string | null;
  proceso: number;
}

export type SuplementoPayload = Pick<
  Suplemento,
  'nombre' | 'duracion_dias' | 'duracion_confirmada' | 'porciones_envase' | 'porciones_dia'
>;

export type CrearSuplementoPayload = SuplementoPayload &
  Pick<Suplemento, 'tipo'> & {
    /** Por defecto, el proceso vigente. */
    proceso?: number;
  };

export type AccionSuplemento = 'abrir-envase' | 'continuar' | 'terminar' | 'reemplazar';
