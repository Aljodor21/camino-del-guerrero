export type ClaseGasto = 'cerebral' | 'emocional';

export interface RubroMes {
  categoria: string;
  nombre: string;
  valor: number;
  cerebral: number;
  emocional: number;
}

export interface NoMensual {
  id: number;
  nombre: string;
  valor: number;
  periodicidad: 'anual' | 'semestral';
  mes_pago: number;
  clase: ClaseGasto;
  total_anual: number;
  /** El total del año entre 12: lo que hay que apartar cada mes. */
  mensual: number;
  /** Meses que faltan para el próximo pago, contando este (0 si toca este mes). */
  meses_faltan: number;
  ahorro_hasta_pago: number;
}

export interface Hormiga {
  id: number;
  nombre: string;
  valor_dia: number;
  dias_mes: number;
  clase: ClaseGasto;
  mensual: number;
  anual: number;
}

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
  mes: string;
  categorias: { id: string; nombre: string; rubros: string[] }[];
  rubros: RubroMes[];
  /** 'guardado', el mes del que se copió ('2026-09') o 'plantilla' (la lista del libro en blanco). */
  rubros_de: string;
  no_mensuales: NoMensual[];
  hormiga: Hormiga[];
  registro: GastoAnotado[];
  sin_gasto: string[];
  hoy_al_dia: boolean;
  resumen: {
    relacion: PorClase;
    provision: { mensual: number; cerebral: number; emocional: number };
    hormiga: PorClase;
    estimado: PorClase;
    anotado: PorClase & {
      por_categoria: (PorClase & { categoria: string; nombre: string })[];
    };
    dias_al_dia: number;
    dias_transcurridos: number;
  };
  ajustes: { avisar: boolean; hora_aviso: string };
}
