/** Fechas de la API (YYYY-MM-DD) siempre como fecha local, sin corrimiento por zona horaria. */
export function fechaLocal(iso: string): Date {
  return new Date(`${iso}T00:00:00`);
}

export function hoyISO(): string {
  return aISO(new Date());
}

export function aISO(fecha: Date): string {
  const m = `${fecha.getMonth() + 1}`.padStart(2, '0');
  const d = `${fecha.getDate()}`.padStart(2, '0');
  return `${fecha.getFullYear()}-${m}-${d}`;
}

export function sumarDias(iso: string, dias: number): string {
  const f = fechaLocal(iso);
  f.setDate(f.getDate() + dias);
  return aISO(f);
}

/** Días de `desde` a `hasta` (0 el mismo día). */
export function diasEntre(desde: string, hasta: string): number {
  return Math.round((fechaLocal(hasta).getTime() - fechaLocal(desde).getTime()) / 86_400_000);
}

/** Días transcurridos desde `iso` hasta hoy (0 el mismo día). */
export function diasDesde(iso: string): number {
  return diasEntre(iso, hoyISO());
}

const FORMATOS: Record<'corta' | 'larga' | 'dia' | 'grafica', Intl.DateTimeFormatOptions> = {
  corta: { day: 'numeric', month: 'short', year: 'numeric' },
  grafica: { day: 'numeric', month: 'short' },
  larga: { weekday: 'long', day: 'numeric', month: 'long' },
  dia: { weekday: 'short', day: 'numeric', month: 'short' },
};

export function formatearFecha(iso: string, formato: keyof typeof FORMATOS = 'corta'): string {
  return fechaLocal(iso).toLocaleDateString('es-CO', FORMATOS[formato]);
}

/** Números como se escriben en Colombia: 63,4. */
export function formatearNumero(valor: number | null | undefined, decimales = 2): string {
  if (valor === null || valor === undefined) return '—';
  return valor.toLocaleString('es-CO', { maximumFractionDigits: decimales });
}

/** "07:30:00" → "7:30 a. m." */
export function formatearHora(hora: string): string {
  const [h, m] = hora.split(':').map(Number);
  return new Date(2000, 0, 1, h, m).toLocaleTimeString('es-CO', {
    hour: 'numeric',
    minute: '2-digit',
  });
}

/** Distancia en días dicha como se habla: hoy, mañana, en 3 días, hace 2 días. */
export function cuandoEs(iso: string): string {
  const dias = diasEntre(hoyISO(), iso);
  if (dias === 0) return 'Hoy';
  if (dias === 1) return 'Mañana';
  if (dias === -1) return 'Ayer';
  return dias > 0 ? `En ${dias} días` : `Hace ${-dias} días`;
}
