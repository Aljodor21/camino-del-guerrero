import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { catchError, map, of } from 'rxjs';

import { AuthService } from '../services/auth';
import { ProcesoService } from '../services/proceso';
import { Modulo } from '../models/proceso.model';

/** Usuarios sin proceso (ni en curso ni programado) van al onboarding. */
export const procesoGuard: CanActivateFn = () => {
  const auth = inject(AuthService);
  const router = inject(Router);
  const procesos = inject(ProcesoService);
  if (auth.isAdmin()) return true;
  return procesos.cargar().pipe(
    map(() => (procesos.tieneProceso() ? true : router.createUrlTree(['/onboarding']))),
    catchError(() => of(true)),
  );
};

/** Solo deja entrar a la sección si el proceso incluye ese módulo. */
export const moduloGuard =
  (modulo: Modulo): CanActivateFn =>
  () => {
    const router = inject(Router);
    const procesos = inject(ProcesoService);
    return procesos
      .cargar()
      .pipe(map(() => (procesos.tieneModulo(modulo) ? true : router.createUrlTree(['/progreso']))));
  };

/** Pantalla inicial según el rol y los módulos del proceso. */
export const inicioGuard: CanActivateFn = () => {
  const auth = inject(AuthService);
  const router = inject(Router);
  const procesos = inject(ProcesoService);
  if (auth.isAdmin()) return router.createUrlTree(['/admin/implementos']);
  return procesos.cargar().pipe(
    map(() => {
      if (procesos.tieneModulo('alimentacion')) return router.createUrlTree(['/nutricion']);
      if (procesos.tieneModulo('entrenamiento')) return router.createUrlTree(['/rutinas']);
      return router.createUrlTree(['/progreso']);
    }),
  );
};
