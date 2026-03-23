import { Component, ChangeDetectionStrategy, inject, signal, OnInit } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { DatePipe } from '@angular/common';
import { ButtonModule } from 'primeng/button';
import { ProgressSpinnerModule } from 'primeng/progressspinner';

import { Usuario } from '../../core/models/usuario.model';
import { environment } from '../../../environments/environment';
const API = environment.apiUrl;

@Component({
  selector: 'app-usuarios',
  templateUrl: './usuarios.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [ButtonModule, ProgressSpinnerModule, DatePipe],
})
export class Usuarios implements OnInit {
  private http = inject(HttpClient);

  protected usuarios = signal<Usuario[]>([]);
  protected loading = signal(true);

  ngOnInit(): void {
    this.cargar();
  }

  private cargar(): void {
    this.loading.set(true);
    this.http.get<Usuario[]>(`${API}/usuarios/admin/usuarios/`).subscribe({
      next: data => { this.usuarios.set(data); this.loading.set(false); },
    });
  }

  protected eliminar(usuario: Usuario): void {
    if (!confirm(`¿Eliminar a "${usuario.nombre}"? Esta acción no se puede deshacer.`)) return;
    this.http.delete(`${API}/usuarios/admin/usuarios/${usuario.id}/`).subscribe({
      next: () => this.cargar(),
    });
  }
}
