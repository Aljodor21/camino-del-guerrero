import { Component, ChangeDetectionStrategy, inject, computed, OnInit } from '@angular/core';
import { RouterOutlet, RouterLink, RouterLinkActive } from '@angular/router';
import { ButtonModule } from 'primeng/button';
import { TooltipModule } from 'primeng/tooltip';

import { AuthService } from '../../core/services/auth';
import { ThemeService } from '../../core/services/theme';
import { NotificacionService } from '../../core/services/notificaciones';

@Component({
  selector: 'app-layout',
  templateUrl: './layout.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [RouterOutlet, RouterLink, RouterLinkActive, ButtonModule, TooltipModule],
})
export class Layout implements OnInit {
  protected authService      = inject(AuthService);
  protected themeService     = inject(ThemeService);
  protected notificaciones   = inject(NotificacionService);

  ngOnInit(): void {
    this.notificaciones.verificar();
  }

  protected navItems = computed(() => {
    if (this.authService.isAdmin()) {
      return [
        { path: '/admin/implementos', icon: 'pi pi-box',   label: 'Implementos' },
        { path: '/admin/ejercicios',  icon: 'pi pi-video', label: 'Ejercicios'  },
        { path: '/admin/usuarios',    icon: 'pi pi-users', label: 'Usuarios'    },
      ];
    }
    return [
      { path: '/rutinas',   icon: 'pi pi-bolt',      label: 'Rutinas'   },
      { path: '/progreso',  icon: 'pi pi-chart-line', label: 'Progreso'  },
      { path: '/nutricion', icon: 'pi pi-heart',      label: 'Nutrición' },
      { path: '/perfil',    icon: 'pi pi-user',       label: 'Perfil'    },
    ];
  });
}
