import { HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';

import { environment } from '../../../environments/environment';
import { AuditoriaService } from '../services/auditoria';

/** Cada petición a nuestra API dice si viene de la app instalada o del navegador, y su versión. */
export const auditoriaInterceptor: HttpInterceptorFn = (req, next) => {
  if (!req.url.startsWith(environment.apiUrl)) return next(req);
  const auditoria = inject(AuditoriaService);
  const cabeceras: Record<string, string> = { 'X-Cliente': auditoria.cliente };
  if (auditoria.version()) cabeceras['X-App-Version'] = auditoria.version();
  return next(req.clone({ setHeaders: cabeceras }));
};
