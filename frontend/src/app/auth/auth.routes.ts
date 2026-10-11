import { Routes } from '@angular/router';

export const AUTH_ROUTES: Routes = [
  { path: '', redirectTo: 'login', pathMatch: 'full' },
  {
    path: 'login',
    loadComponent: () => import('./login/login').then(m => m.Login),
  },
  {
    path: 'recuperar',
    loadComponent: () => import('./recuperar/recuperar').then(m => m.Recuperar),
  },
  {
    path: 'restablecer',
    loadComponent: () => import('./restablecer/restablecer').then(m => m.Restablecer),
  },
  {
    path: 'registro',
    loadComponent: () => import('./registro/registro').then(m => m.Registro),
  },
];
