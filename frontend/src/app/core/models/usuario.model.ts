export interface Rol {
  id: number;
  nombre: string;
}

export interface Sexo {
  id: number;
  nombre: string;
}

export interface Usuario {
  id: number;
  email: string;
  nombre: string;
  username: string;
  rol: Rol | null;
  sexo: Sexo | null;
  fecha_nacimiento: string | null;
  estatura: number | null;
  frecuencia_peso: 15 | 30;
  nacionalidad: string;
  region: string;
  preferencias_alimentarias: string;
}

export interface ObjetivoUsuario {
  id: number;
  objetivo: 'bajar_peso' | 'ganar_musculo' | 'mantener' | 'resistencia';
  peso_inicial: number;
  peso_objetivo: number | null;
  nivel_actividad: 'principiante' | 'intermedio' | 'avanzado';
  dias_entrenamiento: 3 | 4 | 5;
  duracion_sesion: 30 | 45 | 60;
  fecha_inicio: string;
  activo: boolean;
}

export interface AuthResponse {
  access: string;
  refresh: string;
  usuario: Usuario;
}

export interface RegistroPayload {
  email: string;
  nombre: string;
  username: string;
  password: string;
  sexo: number | null;
  fecha_nacimiento: string;
}

export interface LoginPayload {
  email: string;
  password: string;
}
