export interface RegistroPeso {
  id: number;
  peso_kg: number;
  fecha: string;
  nota: string;
}

export interface RegistroEntrenamiento {
  id: number;
  rutina: number | null;
  fecha: string;
  rounds: number;
  duracion_minutos: number;
  notas: string;
}
