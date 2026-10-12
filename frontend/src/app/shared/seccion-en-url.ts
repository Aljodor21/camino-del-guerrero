import { Signal, effect, inject } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';

/**
 * Deja la pestaña activa en la URL (?seccion=...), sin sumar entradas al historial,
 * para volver a ella desde otra pantalla, como los avisos.
 */
export function guardarSeccionEnUrl(seccion: Signal<string>): void {
  const router = inject(Router);
  const route = inject(ActivatedRoute);
  effect(() => {
    void router.navigate([], {
      relativeTo: route,
      queryParams: { seccion: seccion() },
      queryParamsHandling: 'merge',
      preserveFragment: true,
      replaceUrl: true,
    });
  });
}
