export interface DiaNutricional {
  id: number;
  dia_semana: number;
  dia_nombre: string;
  desayuno: string;
  almuerzo: string;
  cena: string;
  snacks: string;
  calorias_aprox: number | null;
}

export interface PlanNutricional {
  id: number;
  fecha_generacion: string;
  dias: DiaNutricional[];
}

export interface ItemMercado {
  id: number;
  nombre: string;
  cantidad: string;
  categoria: string;
  categoria_nombre: string;
  comprado: boolean;
}

export interface ListaMercado {
  id: number;
  fecha_generacion: string;
  items: ItemMercado[];
  consejos_compra: string[];
  plan_preparacion: string[];
}
