import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { Component, ChangeDetectionStrategy, inject, computed, OnDestroy, OnInit, signal } from '@angular/core';
import { NavigationEnd, Router, RouterOutlet, RouterLink, RouterLinkActive } from '@angular/router';
import { ButtonModule } from 'primeng/button';
import { TooltipModule } from 'primeng/tooltip';

import { AuthService } from '../../core/services/auth';
import { ThemeService } from '../../core/services/theme';
import { NotificacionService } from '../../core/services/notificaciones';
import { ProcesoService } from '../../core/services/proceso';
import { AgendaService } from '../../core/services/agenda';
import { AvisosService } from '../../core/services/avisos';
import { Visor } from '../visor/visor';
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
  imports: [RouterOutlet, RouterLink, RouterLinkActive, ButtonModule, TooltipModule, Visor],
})
export class Layout implements OnInit, OnDestroy {
  protected authService = inject(AuthService);
  protected themeService = inject(ThemeService);
  protected notificaciones = inject(NotificacionService);
  private procesos = inject(ProcesoService);
  private agenda = inject(AgendaService);
  protected avisos = inject(AvisosService);
  private router = inject(Router);

  private anterior = '/nutricion';
  protected enAvisos = signal(false);

  constructor() {
    // Se recuerda dónde estaba la persona (con su pestaña) para devolverla al cerrar los avisos.
    this.router.events.pipe(takeUntilDestroyed()).subscribe((e) => {
      if (!(e instanceof NavigationEnd)) return;
      const enAvisos = e.urlAfterRedirects.split('?')[0] === '/avisos';
      this.enAvisos.set(enAvisos);
      if (!enAvisos) this.anterior = e.urlAfterRedirects;
    });
  }

  /** El botón de avisos abre la bandeja y, estando en ella, regresa a donde se estaba. */
  protected alternarAvisos(evento: Event): void {
    evento.preventDefault();
    void this.router.navigateByUrl(this.enAvisos() ? this.anterior : '/avisos');
  }

  ngOnInit(): void {
    this.notificaciones.verificar();
    if (!this.authService.isAdmin()) {
      this.agenda.cargar().subscribe({ error: () => {} });
      this.avisos.iniciar();
    }
  }

  ngOnDestroy(): void {
    this.avisos.detener();
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
    if (this.procesos.vigente()?.plan_terminado) {
      return {
        icono: 'pi pi-flag',
        texto: 'Llegó tu control: ¿sigues con tu proceso o tienes cambios?',
        accion: 'Responder',
        enlace: ['/control'],
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
