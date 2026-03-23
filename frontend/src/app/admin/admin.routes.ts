import { Routes } from '@angular/router';

export const ADMIN_ROUTES: Routes = [
  { path: '', redirectTo: 'implementos', pathMatch: 'full' },
  {
    path: 'implementos',
    loadComponent: () => import('./implementos/implementos').then(m => m.Implementos),
  },
  {
    path: 'ejercicios',
    loadComponent: () => import('./ejercicios/ejercicios').then(m => m.Ejercicios),
  },
];
