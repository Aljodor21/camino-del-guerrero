import { Component, inject } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { ThemeService } from './core/services/theme';
import { ServidorCaido } from './shared/servidor-caido/servidor-caido';

@Component({
  selector: 'app-root',
  imports: [RouterOutlet, ServidorCaido],
  template: `
    <router-outlet />
    <app-servidor-caido />
  `,
})
export class App {
  constructor() {
    inject(ThemeService);
  }
}
