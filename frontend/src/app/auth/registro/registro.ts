import { Component, ChangeDetectionStrategy, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { ReactiveFormsModule, FormBuilder, Validators } from '@angular/forms';
import { InputTextModule } from 'primeng/inputtext';
import { PasswordModule } from 'primeng/password';
import { ButtonModule } from 'primeng/button';
import { MessageModule } from 'primeng/message';

import { AuthService } from '../../core/services/auth';
import { ThemeService } from '../../core/services/theme';

@Component({
  selector: 'app-registro',
  templateUrl: './registro.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [ReactiveFormsModule, RouterLink, InputTextModule, PasswordModule, ButtonModule, MessageModule],
})
export class Registro {
  private auth = inject(AuthService);
  protected theme = inject(ThemeService);
  private fb = inject(FormBuilder);

  protected loading = signal(false);
  protected error = signal('');

  protected form = this.fb.nonNullable.group({
    nombre:   ['', Validators.required],
    username: ['', Validators.required],
    email:    ['', [Validators.required, Validators.email]],
    password: ['', [Validators.required, Validators.minLength(8)]],
  });

  protected submit(): void {
    if (this.form.invalid) return;
    this.loading.set(true);
    this.error.set('');

    this.auth.registro(this.form.getRawValue()).subscribe({
      next: () => {},
      error: (err) => {
        const msg = err?.error?.email?.[0] ?? err?.error?.username?.[0] ?? 'Error al crear la cuenta.';
        this.error.set(msg);
        this.loading.set(false);
      },
    });
  }
}
