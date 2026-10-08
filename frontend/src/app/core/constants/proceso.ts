import { ConfigEntrenamiento, Fase, Objetivo, OrigenMedicion, Pose } from '../models/proceso.model';
import { TipoRecordatorio } from '../models/agenda.model';
import { TipoSuplemento } from '../models/suplemento.model';

export interface Opcion<T> {
  label: string;
  value: T;
}

export const OBJETIVOS: (Opcion<Objetivo> & { icon: string })[] = [
  { label: 'Bajar de peso', value: 'bajar_peso', icon: 'pi pi-arrow-down' },
  { label: 'Ganar músculo', value: 'ganar_musculo', icon: 'pi pi-arrow-up' },
  { label: 'Mantener', value: 'mantener', icon: 'pi pi-minus' },
  { label: 'Resistencia', value: 'resistencia', icon: 'pi pi-heart' },
];

export const FASES: (Opcion<Fase> & { desc: string })[] = [
  { label: 'Sin fase', value: '', desc: 'Solo el objetivo' },
  { label: 'Volumen', value: 'volumen', desc: 'Superávit para ganar masa' },
  { label: 'Definición', value: 'definicion', desc: 'Déficit para marcar' },
  { label: 'Mantenimiento', value: 'mantenimiento', desc: 'Sostener lo logrado' },
];

export const ENFOQUES: (Opcion<ConfigEntrenamiento['enfoque_entrenamiento']> & {
  icon: string;
  desc: string;
})[] = [
  { label: 'Boxeo', value: 'boxeo', icon: 'pi pi-star', desc: 'Guantes, saco, cuerda' },
  {
    label: 'Cardio en casa',
    value: 'cardio_casa',
    icon: 'pi pi-heart',
    desc: 'Cuerda, colchoneta',
  },
  {
    label: 'Funcional / HIIT',
    value: 'funcional',
    icon: 'pi pi-bolt',
    desc: 'Sin equipo o mancuernas',
  },
  { label: 'Fuerza', value: 'fuerza', icon: 'pi pi-arrow-up', desc: 'Barra, mancuernas, máquinas' },
  { label: 'Yoga / Movilidad', value: 'movilidad', icon: 'pi pi-sun', desc: 'Colchoneta, bloques' },
];

export const NIVELES: Opcion<ConfigEntrenamiento['nivel_actividad']>[] = [
  { label: 'Principiante', value: 'principiante' },
  { label: 'Intermedio', value: 'intermedio' },
  { label: 'Avanzado', value: 'avanzado' },
];

export const DIAS: Opcion<ConfigEntrenamiento['dias_entrenamiento']>[] = [
  { label: '3 días', value: 3 },
  { label: '4 días', value: 4 },
  { label: '5 días', value: 5 },
];

export const DURACIONES: Opcion<ConfigEntrenamiento['duracion_sesion']>[] = [
  { label: '30 min', value: 30 },
  { label: '45 min', value: 45 },
  { label: '60 min', value: 60 },
];

export const FRECUENCIAS_PESO: Opcion<15 | 30>[] = [
  { label: 'Cada 15 días', value: 15 },
  { label: 'Cada mes', value: 30 },
];

export const ORIGENES_MEDICION: Opcion<OrigenMedicion>[] = [
  { label: 'Yo mismo', value: 'propia' },
  { label: 'Un profesional', value: 'profesional' },
];

export const CONFIG_ENTRENAMIENTO_INICIAL: ConfigEntrenamiento = {
  nivel_actividad: 'principiante',
  dias_entrenamiento: 3,
  duracion_sesion: 45,
  enfoque_entrenamiento: 'boxeo',
};

export const POSES: Opcion<Pose>[] = [
  { label: 'Frente', value: 'frente' },
  { label: 'Perfil', value: 'perfil' },
  { label: 'Espalda', value: 'espalda' },
];

export const TIPOS_RECORDATORIO: (Opcion<TipoRecordatorio> & {
  icon: string;
  tituloSugerido: string;
})[] = [
  {
    label: 'Control',
    value: 'control',
    icon: 'pi pi-user',
    tituloSugerido: 'Control con la nutricionista',
  },
  {
    label: 'Medición',
    value: 'medicion',
    icon: 'pi pi-chart-line',
    tituloSugerido: 'Tomar medidas',
  },
  { label: 'Otro', value: 'otro', icon: 'pi pi-bookmark', tituloSugerido: '' },
];

export const AVISOS_RECORDATORIO: Opcion<number>[] = [
  { label: 'Ese día', value: 0 },
  { label: '1 día', value: 1 },
  { label: '3 días', value: 3 },
  { label: '1 semana', value: 7 },
];

/**
 * Duración que se asume si el usuario no la sabe. La proteína suele ir 3 meses;
 * el hipercalórico va con la meta de volumen, es decir, todo el proceso (null).
 */
export const TIPOS_SUPLEMENTO: (Opcion<TipoSuplemento> & {
  articulo: 'el' | 'la';
  duracionUsual: number | null;
})[] = [
  { label: 'Hipercalórico', value: 'hipercalorico', articulo: 'el', duracionUsual: null },
  { label: 'Proteína', value: 'proteina', articulo: 'la', duracionUsual: 90 },
  { label: 'Creatina', value: 'creatina', articulo: 'la', duracionUsual: null },
  { label: 'Otro', value: 'otro', articulo: 'el', duracionUsual: null },
];

export const DURACIONES_SUPLEMENTO: Opcion<number | null>[] = [
  { label: 'Todo el proceso', value: null },
  { label: '1 mes', value: 30 },
  { label: '2 meses', value: 60 },
  { label: '3 meses', value: 90 },
  { label: '6 meses', value: 180 },
];

/** Para seguir con el mismo al terminar lo planeado. */
export const EXTENSIONES_SUPLEMENTO: Opcion<number>[] = [
  { label: '1 mes más', value: 30 },
  { label: '2 meses más', value: 60 },
  { label: '3 meses más', value: 90 },
];
