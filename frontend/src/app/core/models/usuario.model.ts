export interface Rol {
  id: number;
  nombre: string;
}

export interface Usuario {
  id: number;
  email: string;
  nombre: string;
  username: string;
  rol: Rol | null;
  frecuencia_peso: 15 | 30;
}

export interface ObjetivoUsuario {
  id: number;
  objetivo: 'bajar_peso' | 'ganar_musculo' | 'mantener' | 'resistencia';
  peso_inicial: number;
  peso_objetivo: number | null;
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
}

export interface LoginPayload {
  email: string;
  password: string;
}
