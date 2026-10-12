import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { AuthService } from '../services/auth';

/** Permite el acceso solo a usuarios normales (no admin). */
export const userGuard: CanActivateFn = () => {
  const auth = inject(AuthService);
  const router = inject(Router);

  if (!auth.isLoggedIn()) {
    router.navigate(['/auth/login']);
    return false;
  }

  if (auth.isAdmin()) {
    router.navigate(['/admin/implementos']);
    return false;
  }

  return true;
};
