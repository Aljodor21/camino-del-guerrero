import { Component, ChangeDetectionStrategy, inject, signal, computed, OnInit, OnDestroy } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { ReactiveFormsModule, FormBuilder, Validators } from '@angular/forms';
import { ButtonModule } from 'primeng/button';
import { DialogModule } from 'primeng/dialog';
import { InputNumberModule } from 'primeng/inputnumber';
import { TextareaModule } from 'primeng/textarea';
import { MessageModule } from 'primeng/message';
import { ProgressSpinnerModule } from 'primeng/progressspinner';

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
  imports: [ReactiveFormsModule, ButtonModule, DialogModule, InputNumberModule, TextareaModule, MessageModule, ProgressSpinnerModule],
})
export class Progreso implements OnInit, OnDestroy {
  private http = inject(HttpClient);
  private fb   = inject(FormBuilder);

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
  private sesionInicio: number | null = null;
  private timerInterval: ReturnType<typeof setInterval> | null = null;

  protected timerDisplay = computed(() => {
    const s = this.timerSeg();
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
    this.timerInterval = setInterval(() => this.timerSeg.update(v => v + 1), 1000);
  }

  protected finalizarSerie(eIdx: number, sIdx: number): void {
    this.detenerSerie(eIdx, sIdx, true);
    this.serieActiva.set(null);
    this.limpiarTimer();
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
    this.serieActiva.set(null);
    this.diaSeleccionado.set(null);
    this.ejerciciosEstado.set([]);
    this.sesionInicio = null;
    this.vistaEntrenamiento.set('lista');
  }

  protected abrirVideo(url: string): void {
    window.open(url, '_blank');
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
