import { HttpErrorResponse } from '@angular/common/http';

/** Extrae el mensaje legible de un error de la API (DRF), o usa el de respaldo. */
export function mensajeError(err: unknown, respaldo: string): string {
  if (!(err instanceof HttpErrorResponse) || !err.error || typeof err.error !== 'object') {
    return respaldo;
  }
  const primero = (valor: unknown): string | null => {
    if (typeof valor === 'string') return valor;
    if (Array.isArray(valor)) return primero(valor[0]);
    if (valor && typeof valor === 'object') return primero(Object.values(valor)[0]);
    return null;
  };
  return (
    primero(err.error.detail) ??
    primero(err.error.non_field_errors) ??
    primero(err.error) ??
    respaldo
  );
}
