export interface RegistroPeso {
  id: number;
  peso_kg: number;
  fecha: string;
  nota: string;
}

export interface SerieCompletada {
  numero: number;
  duracion_seg: number;
  completada: boolean;
}

export interface EjercicioCompletado {
  ejercicio_dia_id: number;
  nombre: string;
  url_youtube: string;
  series_plan: number;
  repeticiones: number | null;
  duracion_segundos_plan: number | null;
  series: SerieCompletada[];
}

export interface RegistroEntrenamiento {
  id: number;
  dia_rutina: number | null;
  dia_nombre: string;
  fecha: string;
  duracion_segundos: number;
  ejercicios_completados: EjercicioCompletado[];
  notas: string;
}
