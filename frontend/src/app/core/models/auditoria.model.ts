export type Cliente = 'app' | 'web';

export interface Huella {
  id: number;
  usuario: number | null;
  correo: string;
  momento: string;
  tipo: 'api' | 'pantalla';
  metodo: string;
  ruta: string;
  camino: string;
  consulta: string;
  estado: number | null;
  duracion_ms: number | null;
  automatico: boolean;
  ip: string | null;
  cliente: Cliente | '';
  version_app: string;
  sistema: string;
  dispositivo: string;
  navegador: string;
}

export interface Huellas {
  desde: string;
  hasta: string;
  resultados: Huella[];
  /** El id desde el que seguir, o null si no hay más. */
  siguiente: number | null;
}

export interface ResumenAuditoria {
  desde: string;
  hasta: string;
  total: number;
  personas: number;
  consultas: number;
  errores: number;
  por_dia: { fecha: string; total: number; personas: number }[];
  por_cliente: { cliente: Cliente; total: number }[];
  por_dispositivo: {
    cliente: Cliente;
    sistema: string;
    dispositivo: string;
    total: number;
    personas: number;
    ultima: string;
  }[];
  por_persona: { usuario: number; correo: string; total: number; ultima: string }[];
  rutas: { metodo: string; ruta: string; total: number; errores: number; ms: number | null }[];
  pantallas: { ruta: string; total: number }[];
  versiones_app: { version_app: string; personas: number; total: number }[];
}

export interface FiltrosAuditoria {
  desde: string;
  hasta: string;
  cliente?: Cliente;
  usuario?: string;
  q?: string;
  errores?: boolean;
  automaticos?: boolean;
}
