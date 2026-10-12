export type Objetivo = 'bajar_peso' | 'ganar_musculo' | 'mantener' | 'resistencia';
export type Fase = '' | 'volumen' | 'definicion' | 'mantenimiento';
export type EstadoProceso = 'programado' | 'en_curso' | 'finalizado';
export type OrigenMedicion = 'propia' | 'profesional';
export type Modulo = 'alimentacion' | 'entrenamiento';
export type Pose = 'frente' | 'perfil' | 'espalda';

export interface FotoProgreso {
  id: number;
  pose: Pose;
  ancho: number;
  alto: number;
}

export interface Medicion {
  id: number;
  fecha: string;
  origen: OrigenMedicion;
  peso_kg: number;
  talla_cm: number | null;
  cintura_cm: number | null;
  abdomen_cm: number | null;
  cadera_cm: number | null;
  brazo_cm: number | null;
  muslo_cm: number | null;
  pierna_cm: number | null;
  pliegue_triceps_mm: number | null;
  pliegue_biceps_mm: number | null;
  pliegue_subescapular_mm: number | null;
  pliegue_supraespinal_mm: number | null;
  pliegue_abdominal_mm: number | null;
  pliegue_muslo_mm: number | null;
  pliegue_pierna_mm: number | null;
  pliegue_cresta_iliaca_mm: number | null;
  nota: string;
  imc: number | null;
  es_inicial: boolean;
  fotos: FotoProgreso[];
  /** Si aún se le pueden agregar fotos (las de inicio tienen plazo). */
  admite_fotos: boolean;
  fotos_hasta: string | null;
}

/** Lo que se envía al registrar una medición: sin los campos calculados. */
export type MedicionPayload = Partial<
  Omit<Medicion, 'id' | 'imc' | 'es_inicial' | 'fotos' | 'admite_fotos' | 'fotos_hasta'>
> &
  Pick<Medicion, 'peso_kg'>;

export interface ConfigEntrenamiento {
  nivel_actividad: 'principiante' | 'intermedio' | 'avanzado';
  dias_entrenamiento: 3 | 4 | 5;
  duracion_sesion: 30 | 45 | 60;
  enfoque_entrenamiento: 'boxeo' | 'cardio_casa' | 'funcional' | 'fuerza' | 'movilidad';
}

export interface Proceso {
  id: number;
  objetivo: Objetivo;
  objetivo_nombre: string;
  fase: Fase;
  fase_nombre: string;
  peso_objetivo: number | null;
  incluye_alimentacion: boolean;
  incluye_entrenamiento: boolean;
  fecha_inicio: string;
  fecha_fin: string | null;
  /** La fecha de control: fija una vez puesta; solo cambia al llegar el control o con un plan nuevo. */
  fecha_fin_plan: string | null;
  /** Ya llegó la fecha de control: toca preguntar si sigue o cambia. */
  plan_terminado: boolean;
  /** Fechas meta anteriores. */
  renovaciones: { hasta: string; cambiada_el: string }[];
  estado: EstadoProceso;
  medicion_inicial: Medicion | null;
  entrenamiento: ConfigEntrenamiento | null;
  notas: string;
  fecha_creacion: string;
}

export interface EstadoProcesos {
  actual: Proceso | null;
  programado: Proceso | null;
}

export interface CrearProcesoPayload {
  objetivo: Objetivo;
  fase: Fase;
  peso_objetivo: number | null;
  incluye_alimentacion: boolean;
  incluye_entrenamiento: boolean;
  fecha_inicio: string;
  fecha_fin_plan: string | null;
  notas: string;
  medicion_inicial: MedicionPayload | null;
  entrenamiento: ConfigEntrenamiento | null;
}

export type ActualizarProcesoPayload = Partial<
  Pick<
    Proceso,
    'peso_objetivo' | 'fecha_fin_plan' | 'notas' | 'incluye_alimentacion' | 'incluye_entrenamiento'
  >
> & { entrenamiento?: ConfigEntrenamiento };
