import { HttpErrorResponse, HttpInterceptorFn, HttpResponse } from '@angular/common/http';
import { inject } from '@angular/core';
import { tap } from 'rxjs';

import { environment } from '../../../environments/environment';
import { ServidorService } from '../services/servidor';

const SIN_SERVIDOR = [0, 502, 503, 504];

/** Le cuenta a `ServidorService` si nuestra API responde o no; no cambia nada de la petición. */
export const servidorInterceptor: HttpInterceptorFn = (req, next) => {
  if (!req.url.startsWith(environment.apiUrl)) return next(req);
  const servidor = inject(ServidorService);
  return next(req).pipe(
    tap({
      next: (evento) => {
        if (evento instanceof HttpResponse) servidor.reportarRespuesta();
      },
      error: (err) => {
        if (!(err instanceof HttpErrorResponse)) return;
        if (SIN_SERVIDOR.includes(err.status)) servidor.reportarFallo();
        else servidor.reportarRespuesta(); // un 400 o un 401 también es el servidor contestando
      },
    }),
  );
};
