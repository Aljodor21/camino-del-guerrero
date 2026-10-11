import { Component, ChangeDetectionStrategy, inject, signal, computed, OnInit } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { DatePipe } from '@angular/common';
import { DomSanitizer, SafeResourceUrl } from '@angular/platform-browser';
import { firstValueFrom } from 'rxjs';
import { ButtonModule } from 'primeng/button';
import { ProgressSpinnerModule } from 'primeng/progressspinner';
import { TooltipModule } from 'primeng/tooltip';
import { DialogModule } from 'primeng/dialog';
import { InputTextModule } from 'primeng/inputtext';

import { Implemento, Rutina } from '../core/models/rutina.model';

import { environment } from '../../environments/environment';
import { Portada } from '../shared/portada/portada';
const API = environment.apiUrl;

@Component({
  selector: 'app-rutinas',
  templateUrl: './rutinas.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [Portada, DatePipe, ButtonModule, ProgressSpinnerModule, TooltipModule, DialogModule, InputTextModule],
})
export class Rutinas implements OnInit {
  private http      = inject(HttpClient);
  private sanitizer = inject(DomSanitizer);

  protected videoUrl = signal<SafeResourceUrl | null>(null);

  protected loading = signal(true);
  protected rutina = signal<Rutina | null>(null);
  protected diaSeleccionado = signal(0);

  // Dialog de configuración antes de regenerar
  protected mostrarDialogReg    = signal(false);
  protected loadingDialogReg    = signal(false);
  protected loadingConfirmarReg = signal(false);
  protected implementosDisp     = signal<Implemento[]>([]);
  protected seleccionadosReg    = signal<number[]>([]);
  protected implementosAdicReg  = signal('');

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
        this.loadingConfirmarReg.set(false);
      },
      error: () => {
        this.loading.set(false);
        this.loadingConfirmarReg.set(false);
      },
    });
  }

  protected abrirRegenerar(): void {
    this.loadingDialogReg.set(true);
    this.mostrarDialogReg.set(true);
    Promise.all([
      firstValueFrom(this.http.get<Implemento[]>(`${API}/rutinas/implementos/`)),
      firstValueFrom(this.http.get<{ id: number; implemento: Implemento }[]>(`${API}/rutinas/mis-implementos/`)),
      firstValueFrom(this.http.get<{ implementos_adicionales: string }>(`${API}/usuarios/perfil/`)),
    ]).then(([disponibles, actuales, perfil]) => {
      this.implementosDisp.set(disponibles);
      this.seleccionadosReg.set(actuales.map(u => u.implemento.id));
      this.implementosAdicReg.set(perfil.implementos_adicionales ?? '');
      this.loadingDialogReg.set(false);
    }).catch(() => {
      this.mostrarDialogReg.set(false);
      this.loadingDialogReg.set(false);
    });
  }

  protected isSeleccionadoReg(id: number): boolean {
    return this.seleccionadosReg().includes(id);
  }

  protected toggleImplementoReg(id: number): void {
    const sinImp = this.implementosDisp().find(i => i.es_sin_implemento)?.id;
    const actual = this.seleccionadosReg();
    if (id === sinImp) {
      this.seleccionadosReg.set(actual.includes(id) ? [] : [id]);
      return;
    }
    const filtrado = actual.filter(i => i !== sinImp);
    this.seleccionadosReg.set(
      filtrado.includes(id) ? filtrado.filter(i => i !== id) : [...filtrado, id]
    );
  }

  protected clasesCard(activo: boolean): string {
    const base = 'flex items-center gap-2 p-3 rounded-xl border-2 text-left transition-all w-full';
    return activo
      ? `${base} border-guerrero-red bg-red-50 dark:bg-guerrero-red/10 text-guerrero-red`
      : `${base} border-gray-200 dark:border-dark-700 text-gray-600 dark:text-gray-400`;
  }

  protected async confirmarRegenerar(): Promise<void> {
    this.loadingConfirmarReg.set(true);
    try {
      await firstValueFrom(this.http.patch(`${API}/usuarios/perfil/`, {
        implementos_adicionales: this.implementosAdicReg(),
      }));
      const existentes = await firstValueFrom(
        this.http.get<{ id: number }[]>(`${API}/rutinas/mis-implementos/`)
      );
      for (const e of existentes) {
        await firstValueFrom(this.http.delete(`${API}/rutinas/mis-implementos/${e.id}/`));
      }
      for (const id of this.seleccionadosReg()) {
        await firstValueFrom(this.http.post(`${API}/rutinas/mis-implementos/`, { implemento_id: id }));
      }
      await firstValueFrom(this.http.post(`${API}/nutricion/generar-rutina/`, {}));
      this.mostrarDialogReg.set(false);
      this.cargarRutina();
    } catch {
      this.loadingConfirmarReg.set(false);
    }
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

  protected verVideo(url: string): void {
    const match = url.match(/(?:v=|youtu\.be\/)([a-zA-Z0-9_-]{11})/);
    const embedUrl = match ? `https://www.youtube.com/embed/${match[1]}?autoplay=1` : url;
    this.videoUrl.set(this.sanitizer.bypassSecurityTrustResourceUrl(embedUrl));
  }

  protected cerrarVideo(): void {
    this.videoUrl.set(null);
  }
}
