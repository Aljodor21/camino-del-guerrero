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
  /** «Visa ·1234» si se pagó con tarjeta de crédito; vacío si no. */
  tarjeta: string;
  cuotas: number;
  se_puede_borrar: boolean;
}

export interface TarjetaPayload {
  nombre: string;
  /** Solo los 4 últimos números, o nada. */
  ultimos: string;
  cupo: number | null;
  dia_corte: number | null;
  dia_pago: number | null;
  avisar: boolean;
}

/** Una tarjeta de crédito con lo calculado de su corte (cuotas sin intereses). */
export interface TarjetaCredito extends TarjetaPayload {
  id: number;
  periodo: { desde: string; hasta: string; pago: string | null };
  compras: {
    id: number;
    fecha: string;
    valor: number;
    descripcion: string;
    clase: ClaseGasto;
    cuotas: number;
  }[];
  comprado: number;
  emocional: number;
  /** Lo que va en la factura de este corte: lo de contado y las cuotas que caen aquí. */
  este_corte: number;
  /** La factura del corte anterior, mientras no pase su día de pago. */
  factura: { valor: number; corte: string; pago: string } | null;
  deuda: number;
  disponible: number | null;
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
  tarjetas: TarjetaCredito[];
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
