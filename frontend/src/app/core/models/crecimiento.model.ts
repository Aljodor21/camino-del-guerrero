export type FuenteProceso = 'libro' | 'curso' | 'mentor' | 'propio';
export type EstadoProceso = 'en_curso' | 'pausado' | 'terminado';
export type EstadoProyecto = 'por_empezar' | 'en_curso' | 'terminado';

export interface AreaCrecimiento {
  id: number;
  nombre: string;
  icono: string;
  orden: number;
  procesos: number;
  avance: number;
}

/** Un camino dentro de un área, con su fuente («según este libro de este autor»). */
export interface ProcesoCrecimiento {
  id: number;
  area: number;
  titulo: string;
  fuente: FuenteProceso;
  fuente_titulo: string;
  autor: string;
  nota: string;
  estado: EstadoProceso;
  /** El programa del catálogo del que salió, o vacío si es propio. */
  programa: string;
  fecha_inicio: string;
  fecha_fin: string | null;
  proyectos: number;
  avance: number;
}

export type ProcesoPayload = Partial<
  Pick<
    ProcesoCrecimiento,
    'area' | 'titulo' | 'fuente' | 'fuente_titulo' | 'autor' | 'nota' | 'estado' | 'programa'
  >
>;

/** Un programa del catálogo: un proceso ya armado según una fuente, con sus proyectos. */
export interface ProgramaCrecimiento {
  id: string;
  titulo: string;
  fuente: FuenteProceso;
  fuente_titulo: string;
  autor: string;
  area: string;
  descripcion: string;
  proyectos: { clave: string; titulo: string; detalle: string }[];
}

/**
 * Un ejercicio de un proceso. Todos los tipos de proyecto cumplen el mismo estándar: título, estado, avance (0 a
 * 100), una frase de resumen y sus notas; lo propio de cada tipo va en `datos`.
 */
export interface ProyectoCrecimiento {
  id: number;
  proceso: number;
  tipo: string;
  tipo_nombre: string;
  /** Cuál proyecto del programa es (vacío si lo creó la persona). */
  clave: string;
  titulo: string;
  detalle: string;
  orden: number;
  estado: EstadoProyecto;
  avance: number;
  /** Si el tipo calcula su avance (si no, lo marca la persona). */
  calcula_avance: boolean;
  datos: Record<string, unknown>;
  resumen: string;
  notas: number;
  creado: string;
  actualizado: string;
}

export type ProyectoPayload = Partial<
  Pick<
    ProyectoCrecimiento,
    'proceso' | 'tipo' | 'titulo' | 'detalle' | 'estado' | 'avance' | 'datos'
  >
>;

export interface NotaCrecimiento {
  id: number;
  proyecto: number;
  proyecto_titulo: string;
  titulo: string;
  texto: string;
  fecha: string;
}

/** Lo que la app principal puede traer de crecimiento. */
export interface ResumenCrecimiento {
  areas: {
    id: number;
    nombre: string;
    icono: string;
    avance: number;
    procesos: {
      id: number;
      titulo: string;
      fuente: FuenteProceso;
      fuente_titulo: string;
      autor: string;
      estado: EstadoProceso;
      avance: number;
      proyectos: {
        id: number;
        titulo: string;
        estado: EstadoProyecto;
        avance: number;
        resumen: string;
      }[];
    }[];
  }[];
  notas: NotaCrecimiento[];
}
