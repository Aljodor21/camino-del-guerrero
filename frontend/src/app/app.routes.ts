import { Routes } from '@angular/router';
import { authGuard } from './core/guards/auth-guard';
import { adminGuard } from './core/guards/role-guard';

export const routes: Routes = [
  { path: '', redirectTo: 'auth/login', pathMatch: 'full' },
  {
    path: 'auth',
    loadChildren: () => import('./auth/auth.routes').then(m => m.AUTH_ROUTES),
  },
  {
    path: 'onboarding',
    loadComponent: () => import('./onboarding/onboarding').then(m => m.Onboarding),
    canActivate: [authGuard],
  },
  {
    path: '',
    loadComponent: () => import('./shared/layout/layout').then(m => m.Layout),
    canActivate: [authGuard],
    children: [
      { path: 'rutinas',   loadComponent: () => import('./rutinas/rutinas').then(m => m.Rutinas) },
      { path: 'progreso',  loadComponent: () => import('./progreso/progreso').then(m => m.Progreso) },
      { path: 'nutricion', loadComponent: () => import('./nutricion/nutricion').then(m => m.Nutricion) },
      {
        path: 'admin',
        canActivate: [adminGuard],
        loadChildren: () => import('./admin/admin.routes').then(m => m.ADMIN_ROUTES),
      },
      { path: '', redirectTo: 'rutinas', pathMatch: 'full' },
    ],
  },
  { path: '**', redirectTo: 'auth/login' },
];
