import { Component, ChangeDetectionStrategy, inject } from '@angular/core';
import { RouterOutlet, RouterLink, RouterLinkActive } from '@angular/router';
import { ButtonModule } from 'primeng/button';
import { TooltipModule } from 'primeng/tooltip';

import { AuthService } from '../../core/services/auth';
import { ThemeService } from '../../core/services/theme';

@Component({
  selector: 'app-layout',
  templateUrl: './layout.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [RouterOutlet, RouterLink, RouterLinkActive, ButtonModule, TooltipModule],
})
export class Layout {
  protected authService = inject(AuthService);
  protected themeService = inject(ThemeService);

  protected navItems = [
    { path: '/rutinas',   icon: 'pi pi-bolt',       label: 'Rutinas'    },
    { path: '/progreso',  icon: 'pi pi-chart-line',  label: 'Progreso'   },
    { path: '/nutricion', icon: 'pi pi-heart',       label: 'Nutrición'  },
  ];
}
