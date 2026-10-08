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
  date_joined: string;
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
