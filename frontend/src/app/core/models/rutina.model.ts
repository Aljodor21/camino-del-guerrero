export interface Implemento {
  id: number;
  nombre: string;
  descripcion: string;
  categoria: string;
  es_sin_implemento: boolean;
}

export interface Ejercicio {
  id: number;
  nombre: string;
  descripcion: string;
  url_youtube: string;
  busqueda_media: string;
  requiere_implemento: boolean;
  implementos: Implemento[];
}

export interface EjercicioDia {
  id: number;
  ejercicio: Ejercicio;
  series: number | null;
  repeticiones: number | null;
  duracion_segundos: number | null;
  orden: number;
}

export interface DiaRutina {
  id: number;
  dia_semana: number;
  dia_nombre: string;
  ejercicios: EjercicioDia[];
}

export interface Recomendacion {
  id: number;
  titulo: string;
  descripcion: string;
  url_video: string;
  categoria: 'tecnica' | 'fisico' | 'nutricion' | 'mental' | 'general';
  activa: boolean;
  orden: number;
}

export interface Rutina {
  id: number;
  nombre: string;
  descripcion: string;
  fecha_generacion: string;
  activa: boolean;
  dias: DiaRutina[];
}
