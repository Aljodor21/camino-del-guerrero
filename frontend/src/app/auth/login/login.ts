import { Component, ChangeDetectionStrategy, inject, signal } from '@angular/core';
import { RouterLink,Router } from '@angular/router';
import { ReactiveFormsModule, FormBuilder, Validators } from '@angular/forms';
import { InputTextModule } from 'primeng/inputtext';
import { PasswordModule } from 'primeng/password';
import { ButtonModule } from 'primeng/button';
import { MessageModule } from 'primeng/message';


import { AuthService } from '../../core/services/auth';

@Component({
  selector: 'app-login',
  templateUrl: './login.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [ReactiveFormsModule, RouterLink, InputTextModule, PasswordModule, ButtonModule, MessageModule],
})
export class Login {
  private auth = inject(AuthService);
  private fb = inject(FormBuilder);
  private router = inject(Router);

  protected loading = signal(false);
  protected error = signal('');

  protected form = this.fb.nonNullable.group({
    email:    ['', [Validators.required, Validators.email]],
    password: ['', Validators.required],
  });

  protected submit(): void {
    if (this.form.invalid) return;
    this.loading.set(true);
    this.error.set('');

    this.auth.login(this.form.getRawValue()).subscribe({
      next: () => this.router.navigate(['/inicio']),
      error: () => {
        this.error.set('Correo o contraseña incorrectos.');
        this.loading.set(false);
      },
    });
  }
}
