import { Routes } from '@angular/router';
import { authGuard } from './core/guards/auth-guard';
import { adminGuard } from './core/guards/role-guard';
import { userGuard } from './core/guards/user-guard';

export const routes: Routes = [
  {
    path: '',
    loadComponent: () => import('./home/home').then(m => m.Home),
    pathMatch: 'full',
  },
  {
    path: 'auth',
    loadChildren: () => import('./auth/auth.routes').then(m => m.AUTH_ROUTES),
  },
  {
    path: 'onboarding',
    loadComponent: () => import('./onboarding/onboarding').then(m => m.Onboarding),
    canActivate: [userGuard],
  },
  {
    path: '',
    loadComponent: () => import('./shared/layout/layout').then(m => m.Layout),
    canActivate: [authGuard],
    children: [
      { path: 'rutinas',   canActivate: [userGuard],  loadComponent: () => import('./rutinas/rutinas').then(m => m.Rutinas) },
      { path: 'progreso',  canActivate: [userGuard],  loadComponent: () => import('./progreso/progreso').then(m => m.Progreso) },
      { path: 'nutricion', canActivate: [userGuard],  loadComponent: () => import('./nutricion/nutricion').then(m => m.Nutricion) },
      { path: 'perfil',    canActivate: [userGuard],  loadComponent: () => import('./perfil/perfil').then(m => m.Perfil) },
      {
        path: 'admin',
        canActivate: [adminGuard],
        loadChildren: () => import('./admin/admin.routes').then(m => m.ADMIN_ROUTES),
      },
      { path: '', redirectTo: 'rutinas', pathMatch: 'full' },
    ],
  },
  { path: '**', redirectTo: '' },
];
