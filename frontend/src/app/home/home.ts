import { Component, ChangeDetectionStrategy, inject } from '@angular/core';
import { RouterLink } from '@angular/router';
import { ButtonModule } from 'primeng/button';

import { ThemeService } from '../core/services/theme';
import { AuthService } from '../core/services/auth';

@Component({
  selector: 'app-home',
  templateUrl: './home.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [RouterLink, ButtonModule],
})
export class Home {
  protected theme = inject(ThemeService);
  protected auth  = inject(AuthService);
}
