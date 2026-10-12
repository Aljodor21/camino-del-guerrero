export interface ItemMercado {
  id: number;
  nombre: string;
  cantidad: string;
  categoria: string;
  categoria_nombre: string;
  frecuencia: 'semanal' | 'quincenal' | 'mensual';
  frecuencia_nombre: string;
  comprado: boolean;
}

export type PeriodoMercado = 'semana' | 'quincena' | 'mes';

export interface ItemYaComprado {
  nombre: string;
  ultima_compra: string;
}

export interface ListaMercado {
  id: number;
  fecha_generacion: string;
  items: ItemMercado[];
  consejos_compra: string[];
  plan_preparacion: string[];
  num_personas: number;
  items_ya_comprados: ItemYaComprado[];
  periodo: PeriodoMercado;
  /** El próximo 15 o 30: promoción en Colanta. */
  promocion_colanta: string;
}
