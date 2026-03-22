import { Component, signal } from '@angular/core';
import { RouterOutlet } from '@angular/router';

//Primeng
import { PrimeImportsModule } from './prime-imports';

@Component({
  selector: 'app-root',
  imports: [RouterOutlet,PrimeImportsModule],
  templateUrl: './app.html',
  styleUrl: './app.css'
})
export class App {
  protected readonly title = signal('frontend');
}
