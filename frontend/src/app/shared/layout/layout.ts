import { Component, ChangeDetectionStrategy, inject, computed, OnInit } from '@angular/core';
import { RouterOutlet, RouterLink, RouterLinkActive } from '@angular/router';
import { ButtonModule } from 'primeng/button';
import { TooltipModule } from 'primeng/tooltip';

import { AuthService } from '../../core/services/auth';
import { ThemeService } from '../../core/services/theme';
import { NotificacionService } from '../../core/services/notificaciones';
import { ProcesoService } from '../../core/services/proceso';
import { AgendaService } from '../../core/services/agenda';
import { cuandoEs, formatearFecha, formatearHora } from '../fechas';

interface Aviso {
  icono: string;
  texto: string;
  accion: string | null;
  enlace: string[];
  queryParams?: Record<string, string>;
  /** Qué hacer al cerrarlo; sin esto el aviso no se puede cerrar. */
  descartar?: () => void;
}

@Component({
  selector: 'app-layout',
  templateUrl: './layout.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [RouterOutlet, RouterLink, RouterLinkActive, ButtonModule, TooltipModule],
})
export class Layout implements OnInit {
  protected authService = inject(AuthService);
  protected themeService = inject(ThemeService);
  protected notificaciones = inject(NotificacionService);
  private procesos = inject(ProcesoService);
  private agenda = inject(AgendaService);

  ngOnInit(): void {
    this.notificaciones.verificar();
    if (!this.authService.isAdmin()) this.agenda.cargar().subscribe({ error: () => {} });
  }

  /** Un solo aviso a la vez, el más importante primero. */
  protected aviso = computed((): Aviso | null => {
    if (this.authService.isAdmin()) return null;
    if (this.procesos.medicionInicialPendiente()) {
      return {
        icono: 'pi pi-flag',
        texto: 'Tu proceso ya inició. Registra tu medición inicial.',
        accion: 'Registrar',
        enlace: ['/progreso'],
        queryParams: { medicion: 'inicial' },
      };
    }
    const recordatorio = this.agenda.aviso();
    if (recordatorio) {
      const hora = recordatorio.hora ? ` · ${formatearHora(recordatorio.hora)}` : '';
      return {
        icono: 'pi pi-calendar',
        texto: `${cuandoEs(recordatorio.fecha)}: ${recordatorio.titulo}${hora}`,
        accion: 'Ver',
        enlace: ['/progreso'],
        queryParams: { seccion: 'agenda' },
        descartar: () => this.agenda.marcarVisto(recordatorio.id),
      };
    }
    const programado = this.procesos.programado();
    if (programado && !this.procesos.actual()) {
      return {
        icono: 'pi pi-calendar',
        texto: `Tu proceso inicia el ${formatearFecha(programado.fecha_inicio, 'larga')}.`,
        accion: null,
        enlace: ['/perfil'],
      };
    }
    if (this.notificaciones.recordatorioPeso()) {
      return {
        icono: 'pi pi-bell',
        texto: 'Es momento de registrar tu peso.',
        accion: 'Registrar',
        enlace: ['/progreso'],
        descartar: () => this.notificaciones.dismiss(),
      };
    }
    return null;
  });

  protected navItems = computed(() => {
    if (this.authService.isAdmin()) {
      return [
        { path: '/admin/implementos', icon: 'pi pi-box', label: 'Implementos' },
        { path: '/admin/ejercicios', icon: 'pi pi-video', label: 'Ejercicios' },
        { path: '/admin/recomendaciones', icon: 'pi pi-play-circle', label: 'Consejos' },
        { path: '/admin/usuarios', icon: 'pi pi-users', label: 'Usuarios' },
      ];
    }
    const p = this.procesos.vigente();
    return [
      ...(p?.incluye_alimentacion
        ? [{ path: '/nutricion', icon: 'pi pi-heart', label: 'Nutrición' }]
        : []),
      ...(p?.incluye_entrenamiento
        ? [{ path: '/rutinas', icon: 'pi pi-bolt', label: 'Rutinas' }]
        : []),
      { path: '/progreso', icon: 'pi pi-chart-line', label: 'Progreso' },
      { path: '/recomendaciones', icon: 'pi pi-play-circle', label: 'Consejos' },
      { path: '/perfil', icon: 'pi pi-user', label: 'Perfil' },
    ];
  });

  protected descartarAviso(aviso: Aviso): void {
    aviso.descartar?.();
  }
}
