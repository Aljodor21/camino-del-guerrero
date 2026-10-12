import { Routes } from '@angular/router';
import { authGuard } from './core/guards/auth-guard';
import { adminGuard } from './core/guards/role-guard';
import { userGuard } from './core/guards/user-guard';
import { inicioGuard, moduloGuard, procesoGuard } from './core/guards/proceso-guard';

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
    canActivate: [authGuard, procesoGuard],
    children: [
      { path: 'rutinas',          canActivate: [userGuard, moduloGuard('entrenamiento')], loadComponent: () => import('./rutinas/rutinas').then(m => m.Rutinas) },
      { path: 'progreso',         canActivate: [userGuard], loadComponent: () => import('./progreso/progreso').then(m => m.Progreso) },
      { path: 'nutricion',        canActivate: [userGuard, moduloGuard('alimentacion')], loadComponent: () => import('./nutricion/nutricion').then(m => m.Nutricion) },
      { path: 'nutricion/plan',   canActivate: [userGuard, moduloGuard('alimentacion')], loadComponent: () => import('./nutricion/cargar-minuta/cargar-minuta').then(m => m.CargarMinuta) },
      { path: 'comidas/contar',   canActivate: [userGuard, moduloGuard('alimentacion')], loadComponent: () => import('./comidas/contar/contar').then(m => m.ContarComida) },
      { path: 'cumplimiento',     canActivate: [userGuard, moduloGuard('alimentacion')], loadComponent: () => import('./comidas/cumplimiento/cumplimiento').then(m => m.CumplimientoPlan) },
      { path: 'control',          canActivate: [userGuard], loadComponent: () => import('./control/control').then(m => m.Control) },
      { path: 'lista-alimentos',  canActivate: [userGuard, moduloGuard('alimentacion')], loadComponent: () => import('./nutricion/lista-alimentos/lista-alimentos').then(m => m.ListaAlimentos) },
      { path: 'proyeccion',       canActivate: [userGuard, moduloGuard('alimentacion')], loadComponent: () => import('./nutricion/proyeccion/proyeccion').then(m => m.Proyeccion) },
      { path: 'avisos',           canActivate: [userGuard], loadComponent: () => import('./avisos/avisos').then(m => m.Avisos) },
      { path: 'recomendaciones',  canActivate: [userGuard], loadComponent: () => import('./recomendaciones/recomendaciones').then(m => m.Recomendaciones) },
      { path: 'perfil',           canActivate: [userGuard], loadComponent: () => import('./perfil/perfil').then(m => m.Perfil) },
      {
        path: 'admin',
        canActivate: [adminGuard],
        loadChildren: () => import('./admin/admin.routes').then(m => m.ADMIN_ROUTES),
      },
      { path: 'inicio', canActivate: [inicioGuard], children: [] },
      { path: '', redirectTo: 'inicio', pathMatch: 'full' },
    ],
  },
  { path: '**', redirectTo: '' },
];
