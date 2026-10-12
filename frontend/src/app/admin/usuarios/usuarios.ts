import { Component, ChangeDetectionStrategy, inject, signal, OnInit } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { DatePipe } from '@angular/common';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ButtonModule } from 'primeng/button';
import { DialogModule } from 'primeng/dialog';
import { InputTextModule } from 'primeng/inputtext';
import { MessageModule } from 'primeng/message';
import { ProgressSpinnerModule } from 'primeng/progressspinner';
import { SelectModule } from 'primeng/select';

import { Sexo, Usuario } from '../../core/models/usuario.model';
import { mensajeError } from '../../shared/errores';
import { environment } from '../../../environments/environment';
const API = environment.apiUrl;

/** Usuarios registrados. Solo el administrador corrige los datos de inicio de una persona. */
@Component({
  selector: 'app-usuarios',
  templateUrl: './usuarios.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    ButtonModule,
    DialogModule,
    InputTextModule,
    MessageModule,
    ProgressSpinnerModule,
    ReactiveFormsModule,
    SelectModule,
    DatePipe,
  ],
})
export class Usuarios implements OnInit {
  private http = inject(HttpClient);
  private fb = inject(NonNullableFormBuilder);

  protected usuarios = signal<Usuario[]>([]);
  protected sexos = signal<Sexo[]>([]);
  protected loading = signal(true);
  protected editando = signal<Usuario | null>(null);
  protected guardando = signal(false);
  protected error = signal('');

  /** Los datos de inicio: lo que la persona dijo al empezar y que ella no puede cambiar. */
  protected form = this.fb.group({
    nombre: ['', [Validators.required, Validators.maxLength(150)]],
    sexo_id: [null as number | null],
    fecha_nacimiento: [''],
    estatura: [null as number | null, [Validators.min(100), Validators.max(250)]],
    nacionalidad: ['', Validators.maxLength(100)],
    region: ['', Validators.maxLength(100)],
  });

  ngOnInit(): void {
    this.cargar();
    this.http.get<Sexo[]>(`${API}/usuarios/sexos/`).subscribe({ next: (s) => this.sexos.set(s) });
  }

  private cargar(): void {
    this.loading.set(true);
    this.http.get<Usuario[]>(`${API}/usuarios/admin/usuarios/`).subscribe({
      next: (data) => {
        this.usuarios.set(data);
        this.loading.set(false);
      },
    });
  }

  protected editar(u: Usuario): void {
    this.error.set('');
    this.form.reset({
      nombre: u.nombre,
      sexo_id: u.sexo?.id ?? null,
      fecha_nacimiento: u.fecha_nacimiento ?? '',
      estatura: u.estatura,
      nacionalidad: u.nacionalidad,
      region: u.region,
    });
    this.editando.set(u);
  }

  protected guardar(): void {
    const u = this.editando();
    if (!u || this.form.invalid) return;
    const v = this.form.getRawValue();
    this.guardando.set(true);
    this.error.set('');
    this.http
      .patch<Usuario>(`${API}/usuarios/admin/usuarios/${u.id}/`, {
        ...v,
        nombre: v.nombre.trim(),
        fecha_nacimiento: v.fecha_nacimiento || null,
      })
      .subscribe({
        next: () => {
          this.guardando.set(false);
          this.editando.set(null);
          this.cargar();
        },
        error: (err) => {
          this.error.set(mensajeError(err, 'No pudimos guardar los cambios.'));
          this.guardando.set(false);
        },
      });
  }

  protected eliminar(usuario: Usuario): void {
    if (!confirm(`¿Eliminar a "${usuario.nombre}"? Esta acción no se puede deshacer.`)) return;
    this.http.delete(`${API}/usuarios/admin/usuarios/${usuario.id}/`).subscribe({
      next: () => this.cargar(),
    });
  }
}
