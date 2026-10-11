import { Injectable, signal, computed, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Router } from '@angular/router';
import { tap } from 'rxjs/operators';
import { Observable } from 'rxjs';

import { AuthResponse, LoginPayload, RegistroPayload, Usuario } from '../models/usuario.model';

import { environment } from '../../../environments/environment';
const API = `${environment.apiUrl}/usuarios`;
const ACCESS_KEY = 'cdg_access';
const REFRESH_KEY = 'cdg_refresh';
const RECUPERAR_KEY = 'cdg_recuperar';

@Injectable({ providedIn: 'root' })
export class AuthService {
  private _usuario = signal<Usuario | null>(this._cargarUsuario());
  private http = inject(HttpClient);
  private router = inject(Router);

  readonly usuario = this._usuario.asReadonly();
  readonly isLoggedIn = computed(() => this._usuario() !== null);
  readonly isAdmin = computed(() => this._usuario()?.rol?.nombre === 'admin');

  registro(payload: RegistroPayload): Observable<AuthResponse> {
    return this.http
      .post<AuthResponse>(`${API}/registro/`, payload)
      .pipe(tap((res) => this._guardarSesion(res)));
  }

  login(payload: LoginPayload): Observable<AuthResponse> {
    return this.http
      .post<AuthResponse>(`${API}/login/`, payload)
      .pipe(tap((res) => this._guardarSesion(res)));
  }

  /**
   * Manda al correo el usuario y un enlace para crear una clave nueva. El enlace solo sirve en
   * este navegador: se guarda aquí un código y el servidor lo compara al abrirlo.
   */
  recuperarClave(email: string): Observable<{ detail: string }> {
    return this.http.post<{ detail: string }>(`${API}/recuperar-clave/`, {
      email,
      dispositivo: this.codigoDelNavegador(true),
    });
  }

  restablecerClave(token: string, password: string): Observable<{ detail: string }> {
    return this.http.post<{ detail: string }>(`${API}/restablecer-clave/`, {
      token,
      password,
      dispositivo: this.codigoDelNavegador(false),
    });
  }

  private codigoDelNavegador(crear: boolean): string {
    try {
      let codigo = localStorage.getItem(RECUPERAR_KEY);
      if (!codigo && crear) {
        codigo = crypto.randomUUID();
        localStorage.setItem(RECUPERAR_KEY, codigo);
      }
      return codigo ?? '';
    } catch {
      return '';
    }
  }

  logout(): void {
    localStorage.removeItem(ACCESS_KEY);
    localStorage.removeItem(REFRESH_KEY);
    localStorage.removeItem('cdg_usuario');
    this._usuario.set(null);
    this.router.navigate(['/']);
  }

  refreshToken(): Observable<{ access: string }> {
    const refresh = localStorage.getItem(REFRESH_KEY);
    return this.http
      .post<{ access: string }>(`${API}/token/refresh/`, { refresh })
      .pipe(tap((res) => localStorage.setItem(ACCESS_KEY, res.access)));
  }

  getAccessToken(): string | null {
    return localStorage.getItem(ACCESS_KEY);
  }

  actualizarUsuario(usuario: Usuario): void {
    localStorage.setItem('cdg_usuario', JSON.stringify(usuario));
    this._usuario.set(usuario);
  }

  private _guardarSesion(res: AuthResponse): void {
    localStorage.setItem(ACCESS_KEY, res.access);
    localStorage.setItem(REFRESH_KEY, res.refresh);
    localStorage.setItem('cdg_usuario', JSON.stringify(res.usuario));
    this._usuario.set(res.usuario);
  }

  private _cargarUsuario(): Usuario | null {
    try {
      const raw = localStorage.getItem('cdg_usuario');
      return raw ? JSON.parse(raw) : null;
    } catch {
      return null;
    }
  }
}
