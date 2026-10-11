import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { ButtonModule } from 'primeng/button';
import { MessageModule } from 'primeng/message';
import { PasswordModule } from 'primeng/password';

import { AuthService } from '../../core/services/auth';
import { mensajeError } from '../../shared/errores';

/** Destino del enlace del correo: ?uid=...&token=... */
@Component({
  selector: 'app-restablecer',
  templateUrl: './restablecer.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [ReactiveFormsModule, RouterLink, PasswordModule, ButtonModule, MessageModule],
})
export class Restablecer {
  private auth = inject(AuthService);
  private fb = inject(FormBuilder);
  private token = inject(ActivatedRoute).snapshot.queryParamMap.get('token') ?? '';
  protected enlaceCompleto = !!this.token;

  protected guardando = signal(false);
  protected listo = signal(false);
  protected error = signal('');

  constructor() {
    // El enlace no se queda en la barra de direcciones ni en el historial.
    if (this.token) void inject(Router).navigate([], { replaceUrl: true, queryParams: {} });
  }

  protected form = this.fb.nonNullable.group({
    password: ['', [Validators.required, Validators.minLength(8)]],
    repetir: ['', Validators.required],
  });

  protected coinciden(): boolean {
    const { password, repetir } = this.form.getRawValue();
    return password === repetir;
  }

  protected guardar(): void {
    if (this.form.invalid || !this.coinciden()) return;
    this.guardando.set(true);
    this.error.set('');
    this.auth.restablecerClave(this.token, this.form.getRawValue().password).subscribe({
      next: () => {
        this.listo.set(true);
        this.guardando.set(false);
      },
      error: (err) => {
        this.error.set(mensajeError(err, 'No pudimos guardar tu clave. Intenta de nuevo.'));
        this.guardando.set(false);
      },
    });
  }
}
