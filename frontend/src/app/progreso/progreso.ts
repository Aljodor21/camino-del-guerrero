import {
  Component,
  ChangeDetectionStrategy,
  effect,
  inject,
  signal,
  computed,
  OnInit,
  OnDestroy,
} from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { ActivatedRoute } from '@angular/router';
import { DomSanitizer, SafeResourceUrl } from '@angular/platform-browser';
import { ButtonModule } from 'primeng/button';
import { ChartModule } from 'primeng/chart';
import { DialogModule } from 'primeng/dialog';
import { ProgressSpinnerModule } from 'primeng/progressspinner';

import { ThemeService } from '../core/services/theme';
import { AudioService } from '../core/services/audio';
import { CelebracionesService } from '../core/services/celebraciones';
import { RegistroEntrenamiento, EjercicioCompletado } from '../core/models/progreso.model';
import { ProcesoService } from '../core/services/proceso';
import { Medidas } from './medidas/medidas';
import { Agenda } from './agenda/agenda';
import { ResumenProceso } from './resumen-proceso/resumen-proceso';
import { AgendaService } from '../core/services/agenda';
import { Rutina, DiaRutina } from '../core/models/rutina.model';
import { environment } from '../../environments/environment';
import { Portada } from '../shared/portada/portada';
import { guardarSeccionEnUrl } from '../shared/seccion-en-url';
import { Pestana, Pestanas } from '../shared/pestanas/pestanas';
import { Proyeccion } from '../nutricion/proyeccion/proyeccion';
import { QueEs } from '../shared/que-es/que-es';

const API = environment.apiUrl;
const LOCAL_KEY = 'cdg_sesion';

type Seccion = 'medidas' | 'agenda' | 'proyeccion' | 'entrenamiento';

interface EjercicioEnSesion {
  ejercicioDiaId: number;
  nombre: string;
  url_youtube: string | null;
  busqueda_media: string | null;
  series_plan: number;
  repeticiones: number | null;
  duracion_segundos_plan: number | null;
  series: { completada: boolean; duracion_seg: number; inicio: number | null }[];
}

interface SesionGuardada {
  diaRutinaId: number;
  diaNombre: string;
  inicio: number;
  ejercicioActual: number;
  ejercicios: EjercicioEnSesion[];
}

@Component({
  selector: 'app-progreso',
  templateUrl: './progreso.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    QueEs,
    Portada,
    ButtonModule,
    ChartModule,
    DialogModule,
    ProgressSpinnerModule,
    Medidas,
    Agenda,
    ResumenProceso,
    Pestanas,
    Proyeccion,
  ],
})
export class Progreso implements OnInit, OnDestroy {
  private http = inject(HttpClient);
  private procesos = inject(ProcesoService);
  private sanitizer = inject(DomSanitizer);
  private theme = inject(ThemeService);
  private audio = inject(AudioService);
  private celebraciones = inject(CelebracionesService);
  private route = inject(ActivatedRoute);
  private agenda = inject(AgendaService);

  protected videoUrl = signal<SafeResourceUrl | null>(null);
  protected seccion = signal<Seccion>(this.seccionInicial());
  protected tieneEntrenamiento = computed(
    () => this.procesos.vigente()?.incluye_entrenamiento ?? false,
  );
  protected tieneAlimentacion = computed(
    () => this.procesos.vigente()?.incluye_alimentacion ?? false,
  );
  protected pestanas = computed((): Pestana<Seccion>[] => [
    { id: 'medidas', label: 'Medidas', icon: 'pi pi-chart-line' },
    { id: 'agenda', label: 'Agenda', icon: 'pi pi-calendar' },
    ...(this.tieneAlimentacion()
      ? [{ id: 'proyeccion' as const, label: 'Proyección', icon: 'pi pi-compass' }]
      : []),
    ...(this.tieneEntrenamiento()
      ? [{ id: 'entrenamiento' as const, label: 'Sesiones', icon: 'pi pi-bolt' }]
      : []),
  ]);

  constructor() {
    guardarSeccionEnUrl(this.seccion);
    // La proyección necesita la alimentación del proceso; sin ella se vuelve a las medidas.
    effect(() => {
      if (this.procesos.vigente() && this.seccion() === 'proyeccion' && !this.tieneAlimentacion()) {
        this.seccion.set('medidas');
      }
    });
  }

  private seccionInicial(): Seccion {
    const pedida = this.route.snapshot.queryParamMap.get('seccion');
    return pedida === 'agenda' || pedida === 'proyeccion' || pedida === 'entrenamiento'
      ? pedida
      : 'medidas';
  }

  // ── ENTRENAMIENTO — historial ──────────────────────────────────────
  protected registros = signal<RegistroEntrenamiento[]>([]);
  protected loadingRegistros = signal(true);
  protected totalSesiones = computed(() => this.registros().length);
  protected totalMinutosSesiones = computed(() =>
    Math.round(this.registros().reduce((s, r) => s + r.duracion_segundos, 0) / 60),
  );
  protected promedioMinutos = computed(() => {
    const r = this.registros();
    if (!r.length) return 0;
    return Math.round(r.reduce((s, x) => s + x.duracion_segundos, 0) / r.length / 60);
  });

  // Último registro por día de rutina (para marcar días completados)
  protected diasUltimaVez = computed(() => {
    const map: Record<number, string> = {};
    for (const r of this.registros()) {
      if (r.dia_rutina !== null) {
        if (!map[r.dia_rutina] || r.fecha > map[r.dia_rutina]) {
          map[r.dia_rutina] = r.fecha;
        }
      }
    }
    return map;
  });

  protected progresoRutina = computed(() => {
    const dias = this.rutina()?.dias ?? [];
    if (!dias.length) return { completados: 0, total: 0, porcentaje: 0 };
    const completados = dias.filter((d) => !!this.diasUltimaVez()[d.id]).length;
    return {
      completados,
      total: dias.length,
      porcentaje: Math.round((completados / dias.length) * 100),
    };
  });

  protected topEjercicios = computed(() => {
    const conteo: Record<string, number> = {};
    for (const r of this.registros()) {
      for (const e of r.ejercicios_completados) {
        if (e.series.some((s) => s.completada)) conteo[e.nombre] = (conteo[e.nombre] ?? 0) + 1;
      }
    }
    return Object.entries(conteo)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 5)
      .map(([nombre, veces]) => ({ nombre, veces }));
  });

  private chartColors = computed(() => ({
    text: this.theme.isDark() ? '#9ca3af' : '#6b7280',
    grid: this.theme.isDark() ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)',
  }));

  protected chartSesionesData = computed(() => {
    const r = [...this.registros()].reverse().slice(0, 10);
    if (!r.length) return null;
    return {
      labels: r.map((s) =>
        new Date(s.fecha + 'T00:00:00').toLocaleDateString('es-CO', {
          day: 'numeric',
          month: 'short',
        }),
      ),
      datasets: [
        {
          label: 'Minutos',
          data: r.map((s) => Math.round(s.duracion_segundos / 60)),
          backgroundColor: 'rgba(192,57,43,0.7)',
          borderColor: '#C0392B',
          borderWidth: 1,
          borderRadius: 4,
        },
      ],
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
        y: {
          ticks: { color: text, font: { size: 11 }, callback: (v: number) => `${v} min` },
          grid: { color: grid },
          beginAtZero: true,
        },
      },
    };
  });

  // ── ENTRENAMIENTO — sesión ────────────────────────────────────────
  protected vistaEntrenamiento = signal<'lista' | 'elegir_dia' | 'pre_sesion' | 'sesion'>('lista');
  protected rutina = signal<Rutina | null>(null);
  protected sinRutina = signal(false);
  protected diaSeleccionado = signal<DiaRutina | null>(null);

  // Estado de la sesión activa (respaldado en localStorage)
  protected sesion = signal<SesionGuardada | null>(null);
  protected sesionPendiente = signal<SesionGuardada | null>(null);
  protected serieActivaIdx = signal<number | null>(null);
  protected enDescanso = signal(false);
  protected descansoSeg = signal(0);
  protected timerSeg = signal(0);
  protected sesionTotalSeg = signal(0);
  protected savingSesion = signal(false);
  protected errorSesion = signal('');
  protected gifsCache = signal<Record<string, string>>({});

  private timerInterval: ReturnType<typeof setInterval> | null = null;
  private descansoInterval: ReturnType<typeof setInterval> | null = null;
  private sesionInterval: ReturnType<typeof setInterval> | null = null;
  private readonly DESCANSO_SEG = 60;

  // ── Computed de sesión ────────────────────────────────────────────
  protected ejercicioActual = computed(() => {
    const s = this.sesion();
    return s ? (s.ejercicios[s.ejercicioActual] ?? null) : null;
  });

  protected seriesCompletadasActual = computed(
    () => this.ejercicioActual()?.series.filter((s) => s.completada).length ?? 0,
  );

  protected seriesPendientes = computed(
    () => this.ejercicioActual()?.series.filter((s) => !s.completada).length ?? 0,
  );

  protected esUltimoEjercicio = computed(() => {
    const s = this.sesion();
    return s ? s.ejercicioActual === s.ejercicios.length - 1 : false;
  });

  protected ejercicioCompletado = computed(
    () => this.seriesPendientes() === 0 && this.serieActivaIdx() === null && !this.enDescanso(),
  );

  protected gifActual = computed(() => {
    const ej = this.ejercicioActual();
    if (!ej || ej.url_youtube || !ej.busqueda_media) return null;
    return this.gifsCache()[ej.busqueda_media] ?? null;
  });

  protected timerDisplay = computed(() => {
    const ej = this.ejercicioActual();
    if (!ej || this.serieActivaIdx() === null) return '00:00';
    const duracion = ej.duracion_segundos_plan;
    const seg = this.timerSeg();
    if (duracion) {
      const restante = Math.max(0, duracion - seg);
      return `${Math.floor(restante / 60)
        .toString()
        .padStart(2, '0')}:${(restante % 60).toString().padStart(2, '0')}`;
    }
    return `${Math.floor(seg / 60)
      .toString()
      .padStart(2, '0')}:${(seg % 60).toString().padStart(2, '0')}`;
  });

  protected descansoDisplay = computed(() => {
    const s = this.descansoSeg();
    return `${Math.floor(s / 60)
      .toString()
      .padStart(2, '0')}:${(s % 60).toString().padStart(2, '0')}`;
  });

  protected sesionDuracionDisplay = computed(() => {
    const t = this.sesionTotalSeg();
    const h = Math.floor(t / 3600);
    const m = Math.floor((t % 3600) / 60);
    const s = t % 60;
    return h > 0
      ? `${h}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`
      : `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
  });

  protected progresoEjercicios = computed(() => {
    const s = this.sesion();
    if (!s || !s.ejercicios.length) return 0;
    return Math.round((s.ejercicioActual / s.ejercicios.length) * 100);
  });

  // ── LIFECYCLE ─────────────────────────────────────────────────────
  ngOnInit(): void {
    this.agenda.cargar().subscribe();
    if (!this.tieneEntrenamiento()) {
      if (this.seccion() === 'entrenamiento') this.seccion.set('medidas');
      return;
    }
    this.cargarRegistros();
    this.cargarRutina();
    const guardada = this.leerLocal();
    if (guardada) this.sesionPendiente.set(guardada);
  }

  ngOnDestroy(): void {
    this.limpiarTimer();
    this.limpiarDescanso(true);
    this.limpiarTimerSesion();
  }

  // ── HISTORIAL ─────────────────────────────────────────────────────
  private cargarRegistros(): void {
    this.http.get<RegistroEntrenamiento[]>(`${API}/progreso/entrenamiento/`).subscribe({
      next: (data) => {
        this.registros.set(data);
        this.loadingRegistros.set(false);
      },
      error: () => this.loadingRegistros.set(false),
    });
  }

  private cargarRutina(): void {
    this.http.get<Rutina>(`${API}/rutinas/mi-rutina/`).subscribe({
      next: (data) => this.rutina.set(data),
      error: () => this.sinRutina.set(true),
    });
  }

  // ── LOCALSTORAGE ──────────────────────────────────────────────────
  private guardarLocal(): void {
    const s = this.sesion();
    if (s) localStorage.setItem(LOCAL_KEY, JSON.stringify(s));
  }

  private leerLocal(): SesionGuardada | null {
    try {
      const raw = localStorage.getItem(LOCAL_KEY);
      return raw ? JSON.parse(raw) : null;
    } catch {
      return null;
    }
  }

  private borrarLocal(): void {
    localStorage.removeItem(LOCAL_KEY);
  }

  // ── GESTIÓN DE SESIÓN ─────────────────────────────────────────────
  protected elegirDia(dia: DiaRutina): void {
    this.diaSeleccionado.set(dia);
    this.vistaEntrenamiento.set('pre_sesion');
  }

  protected iniciarSesion(): void {
    const dia = this.diaSeleccionado();
    if (!dia) return;

    const nueva: SesionGuardada = {
      diaRutinaId: dia.id,
      diaNombre: dia.dia_nombre,
      inicio: Date.now(),
      ejercicioActual: 0,
      ejercicios: [...dia.ejercicios]
        .sort((a, b) => a.orden - b.orden)
        .map((ed) => ({
          ejercicioDiaId: ed.id,
          nombre: ed.ejercicio.nombre,
          url_youtube: ed.ejercicio.url_youtube || null,
          busqueda_media: ed.ejercicio.busqueda_media || null,
          series_plan: ed.series ?? 1,
          repeticiones: ed.repeticiones,
          duracion_segundos_plan: ed.duracion_segundos,
          series: Array.from({ length: ed.series ?? 1 }, () => ({
            completada: false,
            duracion_seg: 0,
            inicio: null,
          })),
        })),
    };

    this.sesion.set(nueva);
    this.guardarLocal();
    this.sesionPendiente.set(null);
    this.serieActivaIdx.set(null);
    this.sesionTotalSeg.set(0);
    this.gifsCache.set({});
    this.precargarGifs(nueva.ejercicios);
    this.iniciarTimerSesion();
    this.vistaEntrenamiento.set('sesion');
  }

  protected restaurarSesion(): void {
    const s = this.sesionPendiente();
    if (!s) return;
    const elapsed = Math.floor((Date.now() - s.inicio) / 1000);
    this.sesion.set(s);
    this.sesionTotalSeg.set(elapsed);
    this.sesionPendiente.set(null);
    this.iniciarTimerSesion();
    this.seccion.set('entrenamiento');
    this.vistaEntrenamiento.set('sesion');
  }

  protected descartarSesionLocal(): void {
    this.borrarLocal();
    this.sesionPendiente.set(null);
  }

  protected cancelarSesion(): void {
    this.limpiarTimer();
    this.limpiarDescanso(true);
    this.limpiarTimerSesion();
    this.borrarLocal();
    this.sesion.set(null);
    this.diaSeleccionado.set(null);
    this.serieActivaIdx.set(null);
    this.errorSesion.set('');
    this.vistaEntrenamiento.set('lista');
  }

  // ── SERIES ────────────────────────────────────────────────────────
  protected iniciarSerie(): void {
    const ej = this.ejercicioActual();
    if (!ej) return;
    const nextIdx = ej.series.findIndex((s) => !s.completada);
    if (nextIdx === -1) return;

    this.limpiarDescanso();
    this.actualizarEjActual((e) => ({
      ...e,
      series: e.series.map((s, i) => (i === nextIdx ? { ...s, inicio: Date.now() } : s)),
    }));

    this.serieActivaIdx.set(nextIdx);
    this.limpiarTimer();
    this.audio.iniciarSerie();

    const duracion = ej.duracion_segundos_plan;
    this.timerInterval = setInterval(() => {
      this.timerSeg.update((v) => v + 1);
      const restante = duracion ? duracion - this.timerSeg() : null;
      if (restante !== null && restante <= 3 && restante > 0) this.audio.tick();
      if (duracion && this.timerSeg() >= duracion) this.completarSerie();
    }, 1000);
  }

  protected completarSerie(): void {
    const sIdx = this.serieActivaIdx();
    if (sIdx === null) return;
    const ej = this.ejercicioActual();
    if (!ej) return;

    const inicio = ej.series[sIdx].inicio ?? Date.now();
    const duracion = Math.floor((Date.now() - inicio) / 1000);

    this.actualizarEjActual((e) => ({
      ...e,
      series: e.series.map((s, i) =>
        i === sIdx ? { completada: true, duracion_seg: duracion, inicio: null } : s,
      ),
    }));

    this.serieActivaIdx.set(null);
    this.limpiarTimer();
    this.audio.completarSerie();
    this.guardarLocal();

    // Descanso solo si quedan más series
    if (this.seriesPendientes() > 0) this.iniciarDescanso();
  }

  private actualizarEjActual(fn: (ej: EjercicioEnSesion) => EjercicioEnSesion): void {
    const s = this.sesion();
    if (!s) return;
    this.sesion.set({
      ...s,
      ejercicios: s.ejercicios.map((ej, i) => (i === s.ejercicioActual ? fn(ej) : ej)),
    });
  }

  protected siguienteEjercicio(): void {
    const s = this.sesion();
    if (!s) return;
    this.limpiarDescanso(true);
    this.limpiarTimer();
    this.serieActivaIdx.set(null);
    this.sesion.set({ ...s, ejercicioActual: s.ejercicioActual + 1 });
    this.guardarLocal();
  }

  protected finalizarSesion(): void {
    const s = this.sesion();
    if (!s) return;

    this.limpiarTimer();
    this.limpiarDescanso(true);
    this.limpiarTimerSesion();

    const duracion = Math.floor((Date.now() - s.inicio) / 1000);
    const ejerciciosCompletados: EjercicioCompletado[] = s.ejercicios.map((ej) => ({
      ejercicio_dia_id: ej.ejercicioDiaId,
      nombre: ej.nombre,
      url_youtube: ej.url_youtube ?? '',
      series_plan: ej.series_plan,
      repeticiones: ej.repeticiones,
      duracion_segundos_plan: ej.duracion_segundos_plan,
      series: ej.series.map((ser, i) => ({
        numero: i + 1,
        duracion_seg: ser.duracion_seg,
        completada: ser.completada,
      })),
    }));

    this.savingSesion.set(true);
    this.errorSesion.set('');

    this.http
      .post(`${API}/progreso/entrenamiento/`, {
        dia_rutina: s.diaRutinaId,
        duracion_segundos: duracion,
        ejercicios_completados: ejerciciosCompletados,
      })
      .subscribe({
        next: () => {
          this.audio.sesionFinalizada();
          this.celebraciones.registro('entrenar');
          this.borrarLocal();
          this.sesion.set(null);
          this.savingSesion.set(false);
          this.vistaEntrenamiento.set('lista');
          this.cargarRegistros();
        },
        error: () => {
          this.errorSesion.set(
            'No se pudo guardar en el servidor. Tus datos están seguros. Puedes reintentar cuando tengas conexión.',
          );
          this.savingSesion.set(false);
          // Reiniciar el timer de sesión para que el usuario pueda seguir viendo el tiempo
          this.iniciarTimerSesion();
        },
      });
  }

  protected reintentarGuardar(): void {
    this.finalizarSesion();
  }

  // ── DESCANSO ──────────────────────────────────────────────────────
  private iniciarDescanso(): void {
    this.audio.iniciarDescanso();
    this.descansoSeg.set(this.DESCANSO_SEG);
    this.enDescanso.set(true);
    this.descansoInterval = setInterval(() => {
      if (this.descansoSeg() <= 1) {
        this.limpiarDescanso();
      } else {
        this.descansoSeg.update((v) => v - 1);
      }
    }, 1000);
  }

  protected saltarDescanso(): void {
    this.limpiarDescanso();
  }

  /** El tono de fin de descanso suena solo si de verdad había un descanso en curso. */
  private limpiarDescanso(silencioso = false): void {
    const habiaDescanso = this.enDescanso();
    if (this.descansoInterval) {
      clearInterval(this.descansoInterval);
      this.descansoInterval = null;
    }
    this.descansoSeg.set(0);
    this.enDescanso.set(false);
    if (!silencioso && habiaDescanso) this.audio.finDescanso();
  }

  private limpiarTimer(): void {
    if (this.timerInterval) {
      clearInterval(this.timerInterval);
      this.timerInterval = null;
    }
    this.timerSeg.set(0);
  }

  private iniciarTimerSesion(): void {
    this.limpiarTimerSesion();
    this.sesionInterval = setInterval(() => this.sesionTotalSeg.update((v) => v + 1), 1000);
  }

  private limpiarTimerSesion(): void {
    if (this.sesionInterval) {
      clearInterval(this.sesionInterval);
      this.sesionInterval = null;
    }
  }

  // ── VIDEO ─────────────────────────────────────────────────────────
  private precargarGifs(ejercicios: EjercicioEnSesion[]): void {
    for (const ej of ejercicios) {
      if (!ej.url_youtube && ej.busqueda_media) {
        const term = ej.busqueda_media;
        this.http
          .get<{ gif_url: string | null }>(`${API}/rutinas/gif/?q=${encodeURIComponent(term)}`)
          .subscribe({
            next: (data) => {
              if (data.gif_url) this.gifsCache.update((c) => ({ ...c, [term]: data.gif_url! }));
            },
            error: () => {},
          });
      }
    }
  }

  protected youtubeThumb(url: string | null): string | null {
    if (!url) return null;
    const m = url.match(/(?:youtube\.com\/watch\?v=|youtu\.be\/)([^&\n?#]+)/);
    return m ? `https://img.youtube.com/vi/${m[1]}/mqdefault.jpg` : null;
  }

  protected verVideo(url: string): void {
    const m = url.match(/(?:v=|youtu\.be\/)([a-zA-Z0-9_-]{11})/);
    const embedUrl = m ? `https://www.youtube.com/embed/${m[1]}?autoplay=1` : url;
    this.videoUrl.set(this.sanitizer.bypassSecurityTrustResourceUrl(embedUrl));
  }

  protected cerrarVideo(): void {
    this.videoUrl.set(null);
  }

  // ── HELPERS ───────────────────────────────────────────────────────
  protected seriesCompletadas(ej: EjercicioCompletado): number {
    return ej.series.filter((s) => s.completada).length;
  }

  protected formatFecha(fecha: string): string {
    return new Date(fecha + 'T00:00:00').toLocaleDateString('es-CO', {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
    });
  }

  protected formatTimestamp(ts: number): string {
    return new Date(ts).toLocaleString('es-CO', {
      weekday: 'long',
      hour: '2-digit',
      minute: '2-digit',
    });
  }

  protected formatSegundos(seg: number): string {
    return `${Math.floor(seg / 60)
      .toString()
      .padStart(2, '0')}:${(seg % 60).toString().padStart(2, '0')}`;
  }
}
