export type ClaseGasto = 'cerebral' | 'emocional';
/** Cada cuánto se paga un gasto: lo anual se divide entre 12 y lo hormiga se multiplica por los días del mes. */
export type Frecuencia = 'mensual' | 'anual' | 'semestral' | 'hormiga';

/** Una línea del diario, como en el ejercicio, con lo que cae en el mes. */
export interface Rubro {
  categoria: string;
  nombre: string;
  frecuencia: Frecuencia;
  /** Lo que vale cada pago (o cada día, si es hormiga). */
  valor: number;
  cerebral: number;
  emocional: number;
  dias_mes: number;
  mes_pago: number | null;
  mensual: number;
  mensual_cerebral: number;
  mensual_emocional: number;
  al_anio?: number;
  meses_faltan?: number;
  ahorro_hasta_pago?: number;
}

export type RubroPayload = Pick<
  Rubro,
  'categoria' | 'nombre' | 'frecuencia' | 'valor' | 'cerebral' | 'dias_mes' | 'mes_pago'
>;

export interface GastoAnotado {
  id: number;
  fecha: string;
  valor: number;
  descripcion: string;
  categoria: string;
  clase: ClaseGasto;
  se_puede_borrar: boolean;
}

export interface PorClase {
  total: number;
  cerebral: number;
  emocional: number;
}

export interface EstadoDiario {
  /** «octubre 2026». */
  mes: string;
  categorias: { id: string; nombre: string }[];
  rubros: Rubro[];
  /** Falso mientras la lista es la del libro en blanco. */
  guardados: boolean;
  registro: GastoAnotado[];
  hoy_al_dia: boolean;
  resumen: {
    plan: PorClase;
    por_frecuencia: Record<Frecuencia, number>;
    anotado: PorClase;
    por_categoria: { categoria: string; nombre: string; plan: number; anotado: number }[];
    dias_al_dia: number;
    dias_transcurridos: number;
  };
  ajustes: { avisar: boolean; hora_aviso: string };
}
