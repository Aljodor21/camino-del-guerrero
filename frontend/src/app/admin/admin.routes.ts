import { Routes } from '@angular/router';

export const ADMIN_ROUTES: Routes = [
  { path: '', redirectTo: 'implementos', pathMatch: 'full' },
  {
    path: 'implementos',
    loadComponent: () => import('./implementos/implementos').then((m) => m.Implementos),
  },
  {
    path: 'ejercicios',
    loadComponent: () => import('./ejercicios/ejercicios').then((m) => m.Ejercicios),
  },
  {
    path: 'usuarios',
    loadComponent: () => import('./usuarios/usuarios').then((m) => m.Usuarios),
  },
  {
    path: 'auditoria',
    loadComponent: () => import('./auditoria/auditoria').then((m) => m.Auditoria),
  },
  {
    path: 'recomendaciones',
    loadComponent: () =>
      import('./recomendaciones/recomendaciones').then((m) => m.AdminRecomendaciones),
  },
];
