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
import { Sexo, ObjetivoUsuario, Usuario } from '../core/models/usuario.model';
import { PAISES } from '../core/constants/paises';

import { environment } from '../../environments/environment';
const API = environment.apiUrl;

@Component({
  selector: 'app-perfil',
  templateUrl: './perfil.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    ReactiveFormsModule,
    InputNumberModule,
    InputTextModule,
    SelectModule,
    AutoCompleteModule,
    SelectButtonModule,
    ButtonModule,
    MessageModule,
  ],
})
export class Perfil implements OnInit {
  private http = inject(HttpClient);
  private fb = inject(FormBuilder);
  protected auth = inject(AuthService);

  protected sexos = signal<Sexo[]>([]);
  protected paisesFiltrados = signal<string[]>([]);
  protected savingPerfil = signal(false);
  protected savingObjetivo = signal(false);
  protected errorPerfil = signal('');
  protected errorObjetivo = signal('');
  protected okPerfil = signal(false);
  protected okObjetivo = signal(false);

  protected readonly objetivoOpciones = [
    { label: 'Bajar peso', value: 'bajar_peso' },
    { label: 'Ganar músculo', value: 'ganar_musculo' },
    { label: 'Mantener', value: 'mantener' },
    { label: 'Resistencia', value: 'resistencia' },
  ];
  protected readonly nivelOpciones = [
    { label: 'Principiante', value: 'principiante' },
    { label: 'Intermedio', value: 'intermedio' },
    { label: 'Avanzado', value: 'avanzado' },
  ];
  protected readonly diasOpciones = [
    { label: '3 días', value: 3 },
    { label: '4 días', value: 4 },
    { label: '5 días', value: 5 },
  ];
  protected readonly duracionOpciones = [
    { label: '30 min', value: 30 },
    { label: '45 min', value: 45 },
    { label: '60 min', value: 60 },
  ];
  protected readonly frecuenciaOpciones = [
    { label: 'Cada 15 días', value: 15 },
    { label: 'Cada mes', value: 30 },
  ];

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

  protected formObjetivo = this.fb.nonNullable.group({
    objetivo: ['bajar_peso', Validators.required],
    peso_inicial: [null as unknown as number, [Validators.required, Validators.min(20)]],
    peso_objetivo: [null as number | null],
    nivel_actividad: ['principiante', Validators.required],
    dias_entrenamiento: [3, Validators.required],
    duracion_sesion: [45, Validators.required],
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

    this.http.get<ObjetivoUsuario>(`${API}/usuarios/objetivo/activo/`).subscribe({
      next: (obj) =>
        this.formObjetivo.patchValue({
          objetivo: obj.objetivo,
          peso_inicial: obj.peso_inicial,
          peso_objetivo: obj.peso_objetivo,
          nivel_actividad: obj.nivel_actividad,
          dias_entrenamiento: obj.dias_entrenamiento,
          duracion_sesion: obj.duracion_sesion,
        }),
    });
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
        this.http.patch<Usuario>(`${API}/usuarios/perfil/`, this.formPerfil.getRawValue()),
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

  protected async guardarObjetivo(): Promise<void> {
    if (this.formObjetivo.invalid) return;
    this.savingObjetivo.set(true);
    this.errorObjetivo.set('');
    this.okObjetivo.set(false);
    try {
      await firstValueFrom(
        this.http.patch(`${API}/usuarios/objetivo/activo/`, this.formObjetivo.getRawValue()),
      );
      this.okObjetivo.set(true);
      setTimeout(() => this.okObjetivo.set(false), 3000);
    } catch {
      this.errorObjetivo.set('Error al guardar el objetivo.');
    } finally {
      this.savingObjetivo.set(false);
    }
  }
}
