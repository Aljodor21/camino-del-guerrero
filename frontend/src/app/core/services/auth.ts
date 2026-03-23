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

@Injectable({ providedIn: 'root' })
export class AuthService {
  private _usuario = signal<Usuario | null>(this._cargarUsuario());
  private http = inject(HttpClient);
  private router = inject(Router);

  readonly usuario = this._usuario.asReadonly();
  readonly isLoggedIn = computed(() => this._usuario() !== null);
  readonly isAdmin = computed(() => this._usuario()?.rol?.nombre === 'admin');


  registro(payload: RegistroPayload): Observable<AuthResponse> {
    return this.http.post<AuthResponse>(`${API}/registro/`, payload).pipe(
      tap(res => this._guardarSesion(res))
    );
  }

  login(payload: LoginPayload): Observable<AuthResponse> {
    return this.http.post<AuthResponse>(`${API}/login/`, payload).pipe(
      tap(res => this._guardarSesion(res))
    );
  }

  logout(): void {
    localStorage.removeItem(ACCESS_KEY);
    localStorage.removeItem(REFRESH_KEY);
    localStorage.removeItem('cdg_usuario');
    this._usuario.set(null);
    this.router.navigate(['/auth/login']);
  }

  refreshToken(): Observable<{ access: string }> {
    const refresh = localStorage.getItem(REFRESH_KEY);
    return this.http.post<{ access: string }>(`${API}/token/refresh/`, { refresh }).pipe(
      tap(res => localStorage.setItem(ACCESS_KEY, res.access))
    );
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
