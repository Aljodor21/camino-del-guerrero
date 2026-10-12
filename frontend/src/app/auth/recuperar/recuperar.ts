import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { ButtonModule } from 'primeng/button';
import { InputTextModule } from 'primeng/inputtext';
import { MessageModule } from 'primeng/message';

import { AuthService } from '../../core/services/auth';
import { mensajeError } from '../../shared/errores';

/** Pide el correo y manda el usuario y un enlace para crear una clave nueva. */
@Component({
  selector: 'app-recuperar',
  templateUrl: './recuperar.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [ReactiveFormsModule, RouterLink, InputTextModule, ButtonModule, MessageModule],
})
export class Recuperar {
  private auth = inject(AuthService);
  private fb = inject(FormBuilder);

  protected enviando = signal(false);
  protected enviado = signal('');
  protected error = signal('');

  protected form = this.fb.nonNullable.group({
    email: ['', [Validators.required, Validators.email]],
  });

  protected enviar(): void {
    if (this.form.invalid) return;
    this.enviando.set(true);
    this.error.set('');
    this.auth.recuperarClave(this.form.getRawValue().email).subscribe({
      next: (res) => {
        this.enviado.set(res.detail);
        this.enviando.set(false);
      },
      error: (err) => {
        this.error.set(mensajeError(err, 'No pudimos enviar el correo. Intenta de nuevo.'));
        this.enviando.set(false);
      },
    });
  }
}
