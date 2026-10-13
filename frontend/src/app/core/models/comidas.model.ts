import { GrupoMinuta, TiempoComida } from './minuta.model';

/** Lo que la minuta pide en una comida, para preguntar cuánto se comió de cada grupo. */
export interface PedidoComida {
  fecha: string;
  tiempo: TiempoComida;
  tiempo_nombre: string;
  grupos: { grupo: GrupoMinuta; nombre: string; porciones: number }[];
  contada: boolean;
  /** Lo que se toma en esta comida (la proteína) y lo que reemplaza de ella. */
  tomas: {
    suplemento: number;
    nombre: string;
    scoops: number | null;
    reemplaza: { grupo: GrupoMinuta; nombre: string; porciones: number }[];
    tomada: boolean;
  }[];
}

/** De 0 a 1 de lo que pedía la minuta para ese grupo. */
export type Avances = Partial<Record<GrupoMinuta, number>>;

export interface RegistroComida {
  id: number;
  fecha: string;
  tiempo: TiempoComida;
  tiempo_nombre: string;
  tiene_foto: boolean;
  nota: string;
}

export interface FaltanteComida {
  grupo: GrupoMinuta;
  nombre: string;
  porciones: number;
}

export interface ComidaContada {
  id: number;
  fecha: string;
  tiempo: TiempoComida;
  nombre: string;
  porcentaje: number;
  faltaron: FaltanteComida[];
  nota: string;
  tiene_foto: boolean;
}

export type PeriodoCumplimiento = 'hoy' | 'semana' | 'mes';

export interface Cumplimiento {
  desde: string;
  hasta: string;
  /** Sobre las comidas contadas; null si aún no se ha contado ninguna. */
  porcentaje: number | null;
  porciones_pedidas: number;
  porciones_comidas: number;
  comidas: ComidaContada[];
  sin_contar: { fecha: string; tiempo: TiempoComida; nombre: string }[];
  por_grupo: { grupo: GrupoMinuta; nombre: string; pedido: number; comido: number }[];
  faltantes: FaltanteComida[];
  mensaje: string;
}
