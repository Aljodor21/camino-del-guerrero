import { Type } from '@angular/core';

/**
 * La pantalla propia de cada tipo de proyecto (el mismo `tipo` que en `crecimiento/tipos.py`). Recibe el proyecto
 * como `proyecto`; lo común (título, notas) lo pone la página de Crecimiento. Un tipo sin pantalla aquí se
 * muestra como libre.
 */
export const PANTALLAS: Record<string, () => Promise<Type<unknown>>> = {
  taller_creencias: () =>
    import('./taller-creencias/taller-creencias').then((m) => m.TallerCreencias),
  diario_gastos: () => import('./diario-gastos/diario-gastos').then((m) => m.DiarioGastos),
  fadiman: () => import('./salud/salud').then((m) => m.Salud),
  otros_suplementos: () => import('./salud/salud').then((m) => m.Salud),
};
