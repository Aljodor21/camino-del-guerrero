export interface DiaNutricional {
  id: number;
  dia_semana: number;
  desayuno: string;
  almuerzo: string;
  cena: string;
  snacks: string;
  calorias_aprox: number;
}

export interface PlanNutricional {
  id: number;
  fecha_generacion: string;
  dias: DiaNutricional[];
}
