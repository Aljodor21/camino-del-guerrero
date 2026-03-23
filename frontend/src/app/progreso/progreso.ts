import { Component, ChangeDetectionStrategy, inject, signal, computed, OnInit, OnDestroy } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { ReactiveFormsModule, FormBuilder, Validators } from '@angular/forms';
import { DomSanitizer, SafeResourceUrl } from '@angular/platform-browser';
import { ButtonModule } from 'primeng/button';
import { ChartModule } from 'primeng/chart';
import { DialogModule } from 'primeng/dialog';
import { InputNumberModule } from 'primeng/inputnumber';
import { TextareaModule } from 'primeng/textarea';
import { MessageModule } from 'primeng/message';
import { ProgressSpinnerModule } from 'primeng/progressspinner';

import { ThemeService } from '../core/services/theme';

import { RegistroPeso, RegistroEntrenamiento, EjercicioCompletado } from '../core/models/progreso.model';
import { Rutina, DiaRutina, EjercicioDia } from '../core/models/rutina.model';

import { environment } from '../../environments/environment';
const API = environment.apiUrl;

interface SerieEstado {
  completada: boolean;
  duracion_seg: number;
  activa: boolean;
  inicio: number | null;
}

interface EjercicioEstado {
  ejercicioDia: EjercicioDia;
  series: SerieEstado[];
}

@Component({
  selector: 'app-progreso',
  templateUrl: './progreso.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [ReactiveFormsModule, ButtonModule, ChartModule, DialogModule, InputNumberModule, TextareaModule, MessageModule, ProgressSpinnerModule],
})
export class Progreso implements OnInit, OnDestroy {
  private http      = inject(HttpClient);
  private fb        = inject(FormBuilder);
  private sanitizer = inject(DomSanitizer);
  private theme     = inject(ThemeService);

  protected videoUrl = signal<SafeResourceUrl | null>(null);

  // ── TABS ──────────────────────────────────────────────────────────
  protected seccion = signal<'peso' | 'entrenamiento'>('peso');

  // ── PESO ──────────────────────────────────────────────────────────
  protected registrosPeso     = signal<RegistroPeso[]>([]);
  protected loadingPeso       = signal(true);
  protected savingPeso        = signal(false);
  protected errorPeso         = signal('');
  protected dialogPesoVisible = signal(false);

  protected formPeso = this.fb.nonNullable.group({
    peso_kg: [null as unknown as number, [Validators.required, Validators.min(20), Validators.max(300)]],
    nota:    [''],
  });

  protected ultimoPeso = computed(() => this.registrosPeso()[0]?.peso_kg ?? null);
  protected cambioPeso = computed(() => {
    const r = this.registrosPeso();
    if (r.length < 2) return null;
    return +(r[0].peso_kg - r[r.length - 1].peso_kg).toFixed(1);
  });

  // ── ENTRENAMIENTO — lista ─────────────────────────────────────────
  protected registros            = signal<RegistroEntrenamiento[]>([]);
  protected loadingRegistros     = signal(true);
  protected totalSesiones        = computed(() => this.registros().length);
  protected totalMinutosSesiones = computed(() =>
    Math.round(this.registros().reduce((s, r) => s + r.duracion_segundos, 0) / 60)
  );
  protected promedioMinutos = computed(() => {
    const r = this.registros();
    if (!r.length) return 0;
    return Math.round(r.reduce((s, x) => s + x.duracion_segundos, 0) / r.length / 60);
  });

  protected topEjercicios = computed(() => {
    const conteo: Record<string, number> = {};
    for (const r of this.registros()) {
      for (const e of r.ejercicios_completados) {
        if (e.series.some(s => s.completada)) {
          conteo[e.nombre] = (conteo[e.nombre] ?? 0) + 1;
        }
      }
    }
    return Object.entries(conteo)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 5)
      .map(([nombre, veces]) => ({ nombre, veces }));
  });

  private chartColors = computed(() => {
    const dark = this.theme.isDark();
    return {
      text:    dark ? '#9ca3af' : '#6b7280',
      grid:    dark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)',
    };
  });

  protected chartPesoData = computed(() => {
    const r = [...this.registrosPeso()].reverse();
    if (r.length < 2) return null;
    return {
      labels: r.map(p => new Date(p.fecha + 'T00:00:00').toLocaleDateString('es-CO', { day: 'numeric', month: 'short' })),
      datasets: [{
        label: 'Peso (kg)',
        data: r.map(p => p.peso_kg),
        borderColor: '#C0392B',
        backgroundColor: 'rgba(192,57,43,0.08)',
        pointBackgroundColor: '#C0392B',
        pointRadius: 5,
        tension: 0.3,
        fill: true,
      }],
    };
  });

  protected chartPesoOptions = computed(() => {
    const { text, grid } = this.chartColors();
    return {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: { callbacks: { label: (ctx: any) => ` ${ctx.raw} kg` } },
      },
      scales: {
        x: { ticks: { color: text, font: { size: 11 } }, grid: { color: grid } },
        y: { ticks: { color: text, font: { size: 11 }, callback: (v: number) => `${v} kg` }, grid: { color: grid } },
      },
    };
  });

  protected chartSesionesData = computed(() => {
    const r = [...this.registros()].reverse().slice(0, 10);
    if (!r.length) return null;
    return {
      labels: r.map(s => new Date(s.fecha + 'T00:00:00').toLocaleDateString('es-CO', { day: 'numeric', month: 'short' })),
      datasets: [{
        label: 'Minutos',
        data: r.map(s => Math.round(s.duracion_segundos / 60)),
        backgroundColor: 'rgba(192,57,43,0.7)',
        borderColor: '#C0392B',
        borderWidth: 1,
        borderRadius: 4,
      }],
    };
  });

  protected chartSesionesOptions = computed(() => {
    const { text, grid } = this.chartColors();
    return {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: { callbacks: { label: (ctx: any) => ` ${ctx.raw} min` } },
      },
      scales: {
        x: { ticks: { color: text, font: { size: 11 } }, grid: { color: grid } },
        y: { ticks: { color: text, font: { size: 11 }, callback: (v: number) => `${v} min` }, grid: { color: grid }, beginAtZero: true },
      },
    };
  });

  // ── ENTRENAMIENTO — sesión ────────────────────────────────────────
  protected vistaEntrenamiento = signal<'lista' | 'elegir_dia' | 'sesion'>('lista');
  protected rutina             = signal<Rutina | null>(null);
  protected sinRutina          = signal(false);
  protected diaSeleccionado    = signal<DiaRutina | null>(null);
  protected ejerciciosEstado   = signal<EjercicioEstado[]>([]);
  protected serieActiva        = signal<{ eIdx: number; sIdx: number } | null>(null);
  protected timerSeg           = signal(0);
  protected savingSesion       = signal(false);
  protected errorSesion        = signal('');
  protected descansoSeg        = signal(0);
  protected descansoActivo     = signal(false);
  private sesionInicio: number | null = null;
  private timerInterval: ReturnType<typeof setInterval> | null = null;
  private descansoInterval: ReturnType<typeof setInterval> | null = null;
  private readonly DESCANSO_SEG = 60;

  protected timerDisplay = computed(() => {
    const activa = this.serieActiva();
    if (!activa) return '00:00';
    const duracion = this.ejerciciosEstado()[activa.eIdx]?.ejercicioDia.duracion_segundos;
    const seg = this.timerSeg();
    if (duracion) {
      const restante = Math.max(0, duracion - seg);
      return `${Math.floor(restante / 60).toString().padStart(2, '0')}:${(restante % 60).toString().padStart(2, '0')}`;
    }
    return `${Math.floor(seg / 60).toString().padStart(2, '0')}:${(seg % 60).toString().padStart(2, '0')}`;
  });

  protected descansoDisplay = computed(() => {
    const s = this.descansoSeg();
    return `${Math.floor(s / 60).toString().padStart(2, '0')}:${(s % 60).toString().padStart(2, '0')}`;
  });

  // ── LIFECYCLE ─────────────────────────────────────────────────────
  ngOnInit(): void {
    this.cargarPeso();
    this.cargarRegistros();
    this.cargarRutina();
  }

  ngOnDestroy(): void {
    this.limpiarTimer();
    this.limpiarDescanso();
  }

  // ── PESO ──────────────────────────────────────────────────────────
  private cargarPeso(): void {
    this.http.get<RegistroPeso[]>(`${API}/progreso/peso/`).subscribe({
      next: data => { this.registrosPeso.set(data); this.loadingPeso.set(false); },
      error: ()   => this.loadingPeso.set(false),
    });
  }

  protected abrirDialogPeso(): void {
    this.errorPeso.set('');
    this.formPeso.reset({ peso_kg: null as unknown as number, nota: '' });
    this.dialogPesoVisible.set(true);
  }

  protected guardarPeso(): void {
    if (this.formPeso.invalid) return;
    this.savingPeso.set(true);
    this.http.post<RegistroPeso>(`${API}/progreso/peso/`, this.formPeso.getRawValue()).subscribe({
      next: () => { this.savingPeso.set(false); this.dialogPesoVisible.set(false); this.cargarPeso(); },
      error: () => { this.errorPeso.set('Error al guardar.'); this.savingPeso.set(false); },
    });
  }

  // ── ENTRENAMIENTO ─────────────────────────────────────────────────
  private cargarRegistros(): void {
    this.http.get<RegistroEntrenamiento[]>(`${API}/progreso/entrenamiento/`).subscribe({
      next: data => { this.registros.set(data); this.loadingRegistros.set(false); },
      error: ()   => this.loadingRegistros.set(false),
    });
  }

  private cargarRutina(): void {
    this.http.get<Rutina>(`${API}/rutinas/mi-rutina/`).subscribe({
      next: data => this.rutina.set(data),
      error: ()  => this.sinRutina.set(true),
    });
  }

  protected elegirDia(dia: DiaRutina): void {
    this.diaSeleccionado.set(dia);
    this.ejerciciosEstado.set(
      dia.ejercicios.map(ed => ({
        ejercicioDia: ed,
        series: Array.from({ length: ed.series ?? 1 }, () => ({
          completada: false, duracion_seg: 0, activa: false, inicio: null,
        })),
      }))
    );
    this.sesionInicio = Date.now();
    this.vistaEntrenamiento.set('sesion');
  }

  protected iniciarSerie(eIdx: number, sIdx: number): void {
    this.limpiarDescanso();
    const activa = this.serieActiva();
    if (activa) this.detenerSerie(activa.eIdx, activa.sIdx, false);
    this.limpiarTimer();

    const nuevos = this.ejerciciosEstado().map((e, ei) => ({
      ...e,
      series: e.series.map((s, si) =>
        ei === eIdx && si === sIdx ? { ...s, activa: true, inicio: Date.now() } : s
      ),
    }));
    this.ejerciciosEstado.set(nuevos);
    this.serieActiva.set({ eIdx, sIdx });

    this.timerInterval = setInterval(() => {
      this.timerSeg.update(v => v + 1);
      const duracion = this.ejerciciosEstado()[eIdx]?.ejercicioDia.duracion_segundos;
      if (duracion && this.timerSeg() >= duracion) {
        this.finalizarSerie(eIdx, sIdx);
      }
    }, 1000);
  }

  protected finalizarSerie(eIdx: number, sIdx: number): void {
    this.detenerSerie(eIdx, sIdx, true);
    this.serieActiva.set(null);
    this.limpiarTimer();
    this.iniciarDescanso();
  }

  protected saltarDescanso(): void {
    this.limpiarDescanso();
  }

  private iniciarDescanso(): void {
    this.descansoSeg.set(this.DESCANSO_SEG);
    this.descansoActivo.set(true);
    this.descansoInterval = setInterval(() => {
      if (this.descansoSeg() <= 1) {
        this.limpiarDescanso();
      } else {
        this.descansoSeg.update(v => v - 1);
      }
    }, 1000);
  }

  private limpiarDescanso(): void {
    if (this.descansoInterval) { clearInterval(this.descansoInterval); this.descansoInterval = null; }
    this.descansoSeg.set(0);
    this.descansoActivo.set(false);
  }

  private detenerSerie(eIdx: number, sIdx: number, completada: boolean): void {
    const serie = this.ejerciciosEstado()[eIdx]?.series[sIdx];
    if (!serie) return;
    const duracion = serie.inicio ? Math.floor((Date.now() - serie.inicio) / 1000) : 0;
    this.ejerciciosEstado.set(
      this.ejerciciosEstado().map((e, ei) => ({
        ...e,
        series: e.series.map((s, si) =>
          ei === eIdx && si === sIdx
            ? { ...s, activa: false, completada, duracion_seg: duracion, inicio: null }
            : s
        ),
      }))
    );
  }

  protected finalizarSesion(): void {
    const activa = this.serieActiva();
    if (activa) { this.detenerSerie(activa.eIdx, activa.sIdx, false); this.serieActiva.set(null); }
    this.limpiarTimer();

    const duracion = this.sesionInicio ? Math.floor((Date.now() - this.sesionInicio) / 1000) : 0;
    const ejerciciosCompletados: EjercicioCompletado[] = this.ejerciciosEstado().map(e => ({
      ejercicio_dia_id:       e.ejercicioDia.id,
      nombre:                 e.ejercicioDia.ejercicio.nombre,
      url_youtube:            e.ejercicioDia.ejercicio.url_youtube,
      series_plan:            e.ejercicioDia.series ?? 1,
      repeticiones:           e.ejercicioDia.repeticiones,
      duracion_segundos_plan: e.ejercicioDia.duracion_segundos,
      series: e.series.map((s, i) => ({
        numero: i + 1, duracion_seg: s.duracion_seg, completada: s.completada,
      })),
    }));

    this.savingSesion.set(true);
    this.errorSesion.set('');
    this.http.post(`${API}/progreso/entrenamiento/`, {
      dia_rutina:              this.diaSeleccionado()!.id,
      duracion_segundos:       duracion,
      ejercicios_completados:  ejerciciosCompletados,
    }).subscribe({
      next: () => { this.savingSesion.set(false); this.vistaEntrenamiento.set('lista'); this.cargarRegistros(); },
      error: () => { this.errorSesion.set('Error al guardar la sesión.'); this.savingSesion.set(false); },
    });
  }

  protected cancelarSesion(): void {
    this.limpiarTimer();
    this.limpiarDescanso();
    this.serieActiva.set(null);
    this.diaSeleccionado.set(null);
    this.ejerciciosEstado.set([]);
    this.sesionInicio = null;
    this.vistaEntrenamiento.set('lista');
  }

  protected verVideo(url: string): void {
    const match = url.match(/(?:v=|youtu\.be\/)([a-zA-Z0-9_-]{11})/);
    const embedUrl = match ? `https://www.youtube.com/embed/${match[1]}?autoplay=1` : url;
    this.videoUrl.set(this.sanitizer.bypassSecurityTrustResourceUrl(embedUrl));
  }

  protected cerrarVideo(): void {
    this.videoUrl.set(null);
  }

  protected seriesCompletadas(ej: EjercicioCompletado): number {
    return ej.series.filter(s => s.completada).length;
  }

  private limpiarTimer(): void {
    if (this.timerInterval) { clearInterval(this.timerInterval); this.timerInterval = null; }
    this.timerSeg.set(0);
  }

  protected formatFecha(fecha: string): string {
    return new Date(fecha + 'T00:00:00').toLocaleDateString('es-CO', {
      day: 'numeric', month: 'short', year: 'numeric',
    });
  }

  protected formatSegundos(seg: number): string {
    return `${Math.floor(seg / 60).toString().padStart(2, '0')}:${(seg % 60).toString().padStart(2, '0')}`;
  }
}
