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
