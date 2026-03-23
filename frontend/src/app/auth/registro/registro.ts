import { Component, ChangeDetectionStrategy, inject, signal, OnInit } from '@angular/core';
import { RouterLink, Router } from '@angular/router';
import { HttpClient } from '@angular/common/http';
import { ReactiveFormsModule, FormBuilder, Validators } from '@angular/forms';
import { InputTextModule } from 'primeng/inputtext';
import { PasswordModule } from 'primeng/password';
import { ButtonModule } from 'primeng/button';
import { MessageModule } from 'primeng/message';

import { AuthService } from '../../core/services/auth';
import { ThemeService } from '../../core/services/theme';
import { Sexo } from '../../core/models/usuario.model';
import { environment } from '../../../environments/environment';

const API = environment.apiUrl;

@Component({
  selector: 'app-registro',
  templateUrl: './registro.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [ReactiveFormsModule, RouterLink, InputTextModule, PasswordModule, ButtonModule, MessageModule],
})
export class Registro implements OnInit {
  private auth   = inject(AuthService);
  private http   = inject(HttpClient);
  protected theme = inject(ThemeService);
  private fb     = inject(FormBuilder);
  private router = inject(Router);

  protected loading = signal(false);
  protected error   = signal('');
  protected sexos   = signal<Sexo[]>([]);

  protected form = this.fb.nonNullable.group({
    nombre:           ['', Validators.required],
    username:         ['', Validators.required],
    email:            ['', [Validators.required, Validators.email]],
    password:         ['', [Validators.required, Validators.minLength(8)]],
    sexo:             [null as unknown as number, Validators.required],
    fecha_nacimiento: ['', Validators.required],
  });

  ngOnInit(): void {
    this.http.get<Sexo[]>(`${API}/usuarios/sexos/`).subscribe({
      next: data => this.sexos.set(data),
    });
  }

  protected submit(): void {
    if (this.form.invalid) return;
    this.loading.set(true);
    this.error.set('');

    this.auth.registro(this.form.getRawValue()).subscribe({
      next: () => this.router.navigate(['/onboarding']),
      error: (err) => {
        const msg = err?.error?.email?.[0] ?? err?.error?.username?.[0] ?? 'Error al crear la cuenta.';
        this.error.set(msg);
        this.loading.set(false);
      },
    });
  }
}
