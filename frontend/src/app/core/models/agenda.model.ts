export type TipoRecordatorio = 'control' | 'medicion' | 'suplemento' | 'otro';

/** Por qué la app sugirió el recordatorio a partir de un suplemento. */
export type MotivoSugerido = 'confirmar' | 'reponer' | 'revisar';

export interface Recordatorio {
  id: number;
  tipo: TipoRecordatorio;
  tipo_nombre: string;
  titulo: string;
  fecha: string;
  /** HH:MM:SS o null si es todo el día. */
  hora: string | null;
  nota: string;
  avisar_dias_antes: number;
  completado_en: string | null;
  proceso: number | null;
  /** Los sugeridos se resuelven desde su suplemento, no se editan. */
  automatico: boolean;
  suplemento: number | null;
  motivo: MotivoSugerido | '';
  /** Los que se crearon juntos al repetirlo comparten la serie. */
  serie: string | null;
}

export interface RecordatorioPayload {
  tipo: TipoRecordatorio;
  titulo: string;
  fecha: string;
  hora: string | null;
  nota: string;
  avisar_dias_antes: number;
  /** Solo al crear: repetirlo cada día, semana o mes, `veces` en total. */
  repetir?: 'dia' | 'semana' | 'mes';
  veces?: number;
}
