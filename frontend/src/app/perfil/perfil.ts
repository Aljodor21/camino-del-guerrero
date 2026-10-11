import { Component, ChangeDetectionStrategy, inject, signal, OnInit } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { ReactiveFormsModule, FormBuilder, Validators } from '@angular/forms';
import { firstValueFrom } from 'rxjs';
import { InputNumberModule } from 'primeng/inputnumber';
import { InputTextModule } from 'primeng/inputtext';
import { SelectModule } from 'primeng/select';
import { AutoCompleteModule } from 'primeng/autocomplete';
import { SelectButtonModule } from 'primeng/selectbutton';
import { ButtonModule } from 'primeng/button';
import { MessageModule } from 'primeng/message';

import { AuthService } from '../core/services/auth';
import { Sexo, Usuario } from '../core/models/usuario.model';
import { FRECUENCIAS_PESO } from '../core/constants/proceso';
import { MiProceso } from './mi-proceso/mi-proceso';
import { PAISES } from '../core/constants/paises';

import { environment } from '../../environments/environment';
import { Portada } from '../shared/portada/portada';
const API = environment.apiUrl;

@Component({
  selector: 'app-perfil',
  templateUrl: './perfil.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [Portada, 
    ReactiveFormsModule,
    InputNumberModule,
    InputTextModule,
    SelectModule,
    AutoCompleteModule,
    SelectButtonModule,
    ButtonModule,
    MessageModule,
    MiProceso,
  ],
})
export class Perfil implements OnInit {
  private http = inject(HttpClient);
  private fb = inject(FormBuilder);
  protected auth = inject(AuthService);

  protected sexos = signal<Sexo[]>([]);
  protected paisesFiltrados = signal<string[]>([]);
  protected savingPerfil = signal(false);
  protected errorPerfil = signal('');
  protected okPerfil = signal(false);

  protected readonly frecuenciaOpciones = FRECUENCIAS_PESO;

  protected formPerfil = this.fb.nonNullable.group({
    nombre: ['', Validators.required],
    sexo_id: [null as number | null],
    fecha_nacimiento: [null as string | null],
    estatura: [null as number | null],
    nacionalidad: ['', Validators.required],
    region: ['', Validators.required],
    preferencias_alimentarias: [''],
    frecuencia_peso: [30 as 15 | 30, Validators.required],
  });

  ngOnInit(): void {
    this.http.get<Sexo[]>(`${API}/usuarios/sexos/`).subscribe({
      next: (data) => this.sexos.set(data),
    });
    this.cargarDatos();
  }

  private cargarDatos(): void {
    const u = this.auth.usuario();
    if (u) this.patchPerfil(u);
  }

  private patchPerfil(u: Usuario): void {
    this.formPerfil.patchValue({
      nombre: u.nombre,
      sexo_id: u.sexo?.id ?? null,
      fecha_nacimiento: u.fecha_nacimiento,
      estatura: u.estatura,
      nacionalidad: u.nacionalidad,
      region: u.region,
      preferencias_alimentarias: u.preferencias_alimentarias,
      frecuencia_peso: u.frecuencia_peso,
    });
    // Lo que ya se dijo al empezar queda fijo; si algo falta, se puede completar una vez.
    const datos: Record<string, unknown> = {
      nombre: u.nombre,
      sexo_id: u.sexo?.id ?? null,
      fecha_nacimiento: u.fecha_nacimiento,
      estatura: u.estatura,
      nacionalidad: u.nacionalidad,
      region: u.region,
    };
    for (const [campo, valor] of Object.entries(datos)) {
      const control = this.formPerfil.get(campo);
      if (valor !== null && valor !== '') control?.disable({ emitEvent: false });
    }
  }

  protected filtrarPaises(query: string): void {
    const q = query.toLowerCase();
    this.paisesFiltrados.set(PAISES.filter((p) => p.toLowerCase().includes(q)));
  }

  protected async guardarPerfil(): Promise<void> {
    if (this.formPerfil.invalid) return;
    this.savingPerfil.set(true);
    this.errorPerfil.set('');
    this.okPerfil.set(false);
    try {
      const usuario = await firstValueFrom(
        this.http.patch<Usuario>(`${API}/usuarios/perfil/`, this.formPerfil.value),
      );
      this.auth.actualizarUsuario(usuario);
      this.okPerfil.set(true);
      setTimeout(() => this.okPerfil.set(false), 3000);
    } catch {
      this.errorPerfil.set('Error al guardar los datos personales.');
    } finally {
      this.savingPerfil.set(false);
    }
  }
}
