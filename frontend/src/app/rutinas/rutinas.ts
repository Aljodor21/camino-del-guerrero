import { Component, ChangeDetectionStrategy, inject, signal, computed, OnInit } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Router } from '@angular/router';
import { DatePipe } from '@angular/common';
import { DomSanitizer, SafeResourceUrl } from '@angular/platform-browser';
import { ButtonModule } from 'primeng/button';
import { ProgressSpinnerModule } from 'primeng/progressspinner';
import { TooltipModule } from 'primeng/tooltip';
import { DialogModule } from 'primeng/dialog';

import { Rutina } from '../core/models/rutina.model';

import { environment } from '../../environments/environment';
const API = environment.apiUrl;

@Component({
  selector: 'app-rutinas',
  templateUrl: './rutinas.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [DatePipe, ButtonModule, ProgressSpinnerModule, TooltipModule, DialogModule],
})
export class Rutinas implements OnInit {
  private http      = inject(HttpClient);
  private router    = inject(Router);
  private sanitizer = inject(DomSanitizer);

  protected videoUrl = signal<SafeResourceUrl | null>(null);

  protected loading = signal(true);
  protected loadingRegenerar = signal(false);
  protected rutina = signal<Rutina | null>(null);
  protected diaSeleccionado = signal(0);

  protected diaActual = computed(() => {
    const r = this.rutina();
    if (!r?.dias.length) return null;
    return r.dias[this.diaSeleccionado()] ?? null;
  });

  ngOnInit(): void {
    this.cargarRutina();
  }

  private cargarRutina(): void {
    this.loading.set(true);
    this.http.get<Rutina>(`${API}/rutinas/mi-rutina/`).subscribe({
      next: rutina => {
        this.rutina.set(rutina);
        const hoy = new Date().getDay();
        const hoyDjango = hoy === 0 ? 7 : hoy;
        const idx = rutina.dias.findIndex(d => d.dia_semana === hoyDjango);
        this.diaSeleccionado.set(idx >= 0 ? idx : 0);
        this.loading.set(false);
        this.loadingRegenerar.set(false);
      },
      error: () => {
        this.loading.set(false);
        this.loadingRegenerar.set(false);
      },
    });
  }

  protected regenerar(): void {
    this.loadingRegenerar.set(true);
    this.http.post(`${API}/nutricion/generar-rutina/`, {}).subscribe({
      next: () => this.cargarRutina(),
      error: () => this.loadingRegenerar.set(false),
    });
  }

  protected seleccionarDia(index: number): void {
    this.diaSeleccionado.set(index);
  }

  protected esHoy(diaSemana: number): boolean {
    const hoy = new Date().getDay();
    return (hoy === 0 ? 7 : hoy) === diaSemana;
  }

  protected formatDuracion(segundos: number): string {
    return segundos >= 60 ? `${Math.floor(segundos / 60)} min` : `${segundos} seg`;
  }

  protected irOnboarding(): void {
    this.router.navigate(['/onboarding']);
  }

  protected verVideo(url: string): void {
    const match = url.match(/(?:v=|youtu\.be\/)([a-zA-Z0-9_-]{11})/);
    const embedUrl = match ? `https://www.youtube.com/embed/${match[1]}?autoplay=1` : url;
    this.videoUrl.set(this.sanitizer.bypassSecurityTrustResourceUrl(embedUrl));
  }

  protected cerrarVideo(): void {
    this.videoUrl.set(null);
  }
}
