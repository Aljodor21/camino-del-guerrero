import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  OnInit,
  computed,
  inject,
  signal,
} from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { ButtonModule } from 'primeng/button';
import { InputTextModule } from 'primeng/inputtext';
import { MessageModule } from 'primeng/message';

import {
  Aviso,
  HoraDeComida,
  SugerenciaDeHoras,
  Sueno,
  TipoAviso,
} from '../core/models/avisos.model';
import { AvisosService } from '../core/services/avisos';
import { NotificacionesCelularService } from '../core/services/notificaciones-celular';
import { PushService } from '../core/services/push';
import { TIEMPOS_COMIDA } from '../core/constants/nutricion';
import { TiempoComida } from '../core/models/minuta.model';
import { clasesChip } from '../shared/chip';
import { TamanoVaso, vasoValido } from '../shared/tamano-vaso';
import { parsearDecimal } from '../shared/decimal-input';
import { mensajeError } from '../shared/errores';
import { formatearHora, formatearNumero, hoyISO, sumarDias } from '../shared/fechas';
import { Pestana, Pestanas } from '../shared/pestanas/pestanas';
import { guardarSeccionEnUrl } from '../shared/seccion-en-url';

const ICONOS: Record<TipoAviso, string> = {
  agua: 'pi pi-circle-fill',
  toma: 'pi pi-box',
  dormir: 'pi pi-moon',
  levantar: 'pi pi-sun',
  entreno: 'pi pi-bolt',
  recordatorio: 'pi pi-calendar',
  comida: 'pi pi-camera',
  proceso: 'pi pi-flag',
};

/** El color de cada tipo de aviso: así se distingue de un vistazo qué es cada uno. */
const ESTILOS: Record<TipoAviso, string> = {
  agua: 'bg-sky-500/15 text-sky-600 dark:text-sky-400',
  toma: 'bg-amber-500/15 text-amber-600 dark:text-amber-400',
  dormir: 'bg-indigo-500/15 text-indigo-600 dark:text-indigo-400',
  levantar: 'bg-amber-500/15 text-amber-600 dark:text-amber-400',
  entreno: 'bg-guerrero-red/15 text-guerrero-red',
  recordatorio: 'bg-violet-500/15 text-violet-600 dark:text-violet-400',
  comida: 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400',
  proceso: 'bg-slate-500/15 text-slate-600 dark:text-slate-300',
};

const TIPOS: { id: TipoAviso; label: string }[] = [
  { id: 'agua', label: 'Agua' },
  { id: 'toma', label: 'Proteína' },
  { id: 'dormir', label: 'Dormir' },
  { id: 'levantar', label: 'Levantarme' },
  { id: 'entreno', label: 'Entreno' },
  { id: 'recordatorio', label: 'Agenda' },
  { id: 'comida', label: 'Comidas' },
  { id: 'proceso', label: 'Control' },
];

/** Qué hace el guerrero cuando se confirma cada tipo de aviso. */
const ACCION_DE_AVISO: Partial<Record<TipoAviso, AccionGuerrero>> = {
  agua: 'agua',
  toma: 'proteina',
  dormir: 'dormir',
  levantar: 'levantar',
  entreno: 'entrenar',
};

/** La bandeja: lo pendiente solo sale cuando se confirma. Además, cómo va el día y los ajustes. */
import { Ayuda } from '../shared/ayuda/ayuda';
import { CumplimientoGlobalVista } from './cumplimiento-global/cumplimiento-global';
import { LogrosVista } from './logros/logros';
import { CelebracionesService } from '../core/services/celebraciones';
import { Anillo } from '../shared/anillo/anillo';
import { AccionGuerrero } from '../shared/guerrero/guerrero';
import { QueEs } from '../shared/que-es/que-es';

type Seccion = 'pendientes' | 'dia' | 'cumplimiento' | 'logros' | 'ajustes';
const SECCIONES: Seccion[] = ['pendientes', 'dia', 'cumplimiento', 'logros', 'ajustes'];

@Component({
  selector: 'app-avisos',
  templateUrl: './avisos.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    QueEs,
    Anillo,
    Ayuda,
    CumplimientoGlobalVista,
    LogrosVista,
    Pestanas,
    RouterLink,
    ButtonModule,
    InputTextModule,
    MessageModule,
    TamanoVaso,
  ],
})
export class Avisos implements OnInit {
  private destroyRef = inject(DestroyRef);
  private ruta = inject(ActivatedRoute);

  protected seccion = signal<Seccion>(
    SECCIONES.find((x) => x === this.ruta.snapshot.queryParamMap.get('seccion')) ?? 'pendientes',
  );
  protected pestanas = computed((): Pestana<Seccion>[] => [
    {
      id: 'pendientes',
      label: 'Pendientes',
      icon: 'pi pi-inbox',
      contador: this.pendientes().length,
    },
    { id: 'dia', label: 'Tu día', icon: 'pi pi-sun' },
    { id: 'cumplimiento', label: 'Cumplimiento', icon: 'pi pi-chart-pie' },
    { id: 'logros', label: 'Logros', icon: 'pi pi-trophy' },
    { id: 'ajustes', label: 'Ajustes', icon: 'pi pi-sliders-h' },
  ]);

  constructor() {
    guardarSeccionEnUrl(this.seccion);
  }
  protected servicio = inject(AvisosService);
  protected push = inject(PushService);
  protected celular = inject(NotificacionesCelularService);
  protected celebraciones = inject(CelebracionesService);

  protected iconos = ICONOS;
  protected estilos = ESTILOS;
  protected tipos = TIPOS;
  protected comidas = TIEMPOS_COMIDA;
  protected clasesChip = clasesChip;
  protected hora = formatearHora;
  protected num = formatearNumero;

  protected error = signal('');
  protected guardando = signal(false);
  protected confirmando = signal<number | null>(null);
  protected guardado = signal(false);

  // ── Ajustes (agua, horas y qué avisos llegan) ─────────────────────
  protected litros = signal<number | null>(null);
  protected vasoMl = signal<number | null>(250);
  /** Qué se anotó con el último clic ("Vaso anotado a las 8:15 a. m."). */
  protected anotado = signal('');
  protected levantarse = signal('');
  protected dormir = signal('');
  protected entreno = signal('');
  /** Horas distintas por día de la semana (1 = lunes): lo vacío usa la hora general. */
  protected horasSemana = signal<Record<string, { levantarse: string; dormir: string }>>({});
  /** Una hora para todos los días, o una por cada día de la semana: es una cosa o la otra. */
  protected modoHoras = signal<'general' | 'por_dia'>('general');
  protected semanaCompleta = computed(() =>
    this.diasSemana.every((d) => {
      const h = this.horasSemana()[d.id];
      return !!h?.levantarse && !!h?.dormir && h.levantarse !== h.dormir;
    }),
  );
  /** Entre qué horas se reparte el agua; vacío usa levantarse + 1 h y acostarse − 1 h. */
  protected aguaDesde = signal('');
  protected aguaHasta = signal('');
  /** Cambios de horas que la app propone según cuándo la persona anota sus cosas. */
  protected sugerencias = signal<SugerenciaDeHoras[]>([]);
  protected aplicando = signal<string | null>(null);
  /** A qué hora come cada tiempo del plan (la de referencia si no la cambió). */
  protected tiemposComida = signal<HoraDeComida[]>([]);
  protected diasSemana = [
    { id: '1', nombre: 'Lunes' },
    { id: '2', nombre: 'Martes' },
    { id: '3', nombre: 'Miércoles' },
    { id: '4', nombre: 'Jueves' },
    { id: '5', nombre: 'Viernes' },
    { id: '6', nombre: 'Sábado' },
    { id: '7', nombre: 'Domingo' },
  ];
  protected apagados = signal<TipoAviso[]>([]);

  protected vasosMeta = computed(() => {
    const l = this.litros();
    return l === null || Number.isNaN(l) || !vasoValido(this.vasoMl())
      ? null
      : Math.ceil((l * 1000) / (this.vasoMl() as number));
  });
  protected ajustesValidos = computed(() => {
    const l = this.litros();
    const aguaBien = l === null || (!Number.isNaN(l) && l >= 0.25 && l <= 8);
    return (
      aguaBien &&
      vasoValido(this.vasoMl()) &&
      (this.modoHoras() === 'por_dia'
        ? this.semanaCompleta()
        : !(this.dormir() && this.dormir() === this.levantarse()))
    );
  });

  /** Se actualiza cada minuto para que "hace 5 min" no se quede viejo. */
  private ahora = signal(Date.now());
  /** Lo más nuevo arriba, como una bandeja de notificaciones. */
  protected pendientes = computed(() =>
    [...this.servicio.avisos()].sort(
      (a, b) => new Date(b.programada_para).getTime() - new Date(a.programada_para).getTime(),
    ),
  );
  protected hoy = this.servicio.hoy;
  /** El promedio de sueño de los últimos 7 días. */
  protected sueno = signal<Sueno | null>(null);
  protected registrandoSueno = signal(false);
  /** Respondiendo «a qué hora te levantaste» cuando no se anotó a tiempo (la única vez que se escribe una hora). */
  protected diciendoHora = signal(false);
  protected horaDicha = signal('');
  protected registrandoSiesta = signal(false);
  protected diciendoHoraSiesta = signal(false);
  protected horaSiesta = signal('');
  protected faltanVasos = computed(() => {
    const a = this.hoy()?.agua;
    return a ? Math.max(0, a.meta - a.vasos) : 0;
  });

  ngOnInit(): void {
    const reloj = window.setInterval(() => this.ahora.set(Date.now()), 60000);
    this.destroyRef.onDestroy(() => window.clearInterval(reloj));
    this.servicio.cargar().subscribe({
      error: (e) => this.error.set(mensajeError(e, 'No pudimos cargar tus avisos.')),
    });
    this.servicio.cargarHoy().subscribe({ error: () => undefined });
    this.cargarSueno();
    this.cargarSugerencias();
    this.servicio.cargarHabitos().subscribe({
      next: (h) => {
        this.litros.set(h.agua_ml === null ? null : h.agua_ml / 1000);
        this.vasoMl.set(h.vaso_ml);
        this.levantarse.set(h.hora_levantarse?.slice(0, 5) ?? '');
        this.dormir.set(h.hora_dormir?.slice(0, 5) ?? '');
        this.entreno.set(h.hora_entreno?.slice(0, 5) ?? '');
        this.horasSemana.set(
          Object.fromEntries(
            Object.entries(h.horas_semana ?? {}).map(([d, v]) => [
              d,
              { levantarse: v.levantarse ?? '', dormir: v.dormir ?? '' },
            ]),
          ),
        );
        this.modoHoras.set(Object.keys(h.horas_semana ?? {}).length ? 'por_dia' : 'general');
        this.tiemposComida.set(h.tiempos_comida ?? []);
        this.aguaDesde.set(h.horas_agua?.inicio ?? '');
        this.aguaHasta.set(h.horas_agua?.fin ?? '');
        this.apagados.set(h.avisos_apagados);
      },
      error: () => undefined,
    });
    void this.push.iniciar();
  }

  /** "ahora", "hace 12 min", "hace 2 h" o la hora si ya pasó más de medio día. */
  protected cuando(aviso: Aviso): string {
    const minutos = Math.floor((this.ahora() - new Date(aviso.programada_para).getTime()) / 60000);
    if (minutos < 1) return 'Ahora';
    if (minutos < 60) return `Hace ${minutos} min`;
    if (minutos < 12 * 60) return `Hace ${Math.floor(minutos / 60)} h`;
    return this.tiempo(aviso);
  }

  protected tiempo(aviso: Aviso): string {
    return new Date(aviso.programada_para).toLocaleTimeString('es-CO', {
      hour: 'numeric',
      minute: '2-digit',
    });
  }

  protected nombreComida(tiempo: string, hora?: string | null): string {
    if (tiempo.startsWith('otro')) return `Otra toma${hora ? ` · ${formatearHora(hora)}` : ''}`;
    return this.comidas[tiempo as TiempoComida]?.label ?? tiempo;
  }

  protected confirmar(aviso: Aviso): void {
    this.confirmando.set(aviso.id);
    this.error.set('');
    this.servicio.confirmar(aviso).subscribe({
      next: () => {
        this.confirmando.set(null);
        this.celebraciones.registro(ACCION_DE_AVISO[aviso.tipo]);
        this.servicio.cargarHoy().subscribe({ error: () => undefined });
      },
      error: (e) => {
        this.confirmando.set(null);
        this.error.set(mensajeError(e, 'No pudimos confirmarlo. Intenta de nuevo.'));
      },
    });
  }

  private descartadas(): string[] {
    try {
      return JSON.parse(localStorage.getItem('cdg_sugerencias_descartadas') ?? '[]') as string[];
    } catch {
      return [];
    }
  }

  protected cargarSugerencias(): void {
    this.servicio.sugerenciasDeHoras().subscribe({
      next: (l) =>
        this.sugerencias.set(
          l.filter((s) => !this.descartadas().includes(`${s.id}:${s.sugerida}`)),
        ),
      error: () => undefined,
    });
  }

  /** La persona acepta el cambio: se guarda y se actualiza todo lo que depende de esas horas. */
  protected aplicarSugerencia(s: SugerenciaDeHoras): void {
    this.aplicando.set(s.id);
    this.error.set('');
    this.servicio.guardarHabitos(s.cambios).subscribe({
      next: (h) => {
        this.aplicando.set(null);
        this.sugerencias.update((l) => l.filter((x) => x.id !== s.id));
        this.cargarSugerencias();
        this.servicio.cargarHoy().subscribe({ error: () => undefined });
        this.servicio.cargar().subscribe({ error: () => undefined });
        this.tiemposComida.set(h.tiempos_comida ?? []);
        this.levantarse.set(h.hora_levantarse?.slice(0, 5) ?? '');
        this.dormir.set(h.hora_dormir?.slice(0, 5) ?? '');
        this.aguaDesde.set(h.horas_agua?.inicio ?? '');
        this.aguaHasta.set(h.horas_agua?.fin ?? '');
        void this.celular.actualizar();
      },
      error: (e) => {
        this.aplicando.set(null);
        this.error.set(mensajeError(e, 'No pudimos aplicar ese cambio.'));
      },
    });
  }

  /** «Así está bien»: no se vuelve a proponer ese mismo cambio. */
  protected descartarSugerencia(s: SugerenciaDeHoras): void {
    try {
      localStorage.setItem(
        'cdg_sugerencias_descartadas',
        JSON.stringify([...this.descartadas(), `${s.id}:${s.sugerida}`]),
      );
    } catch {
      // Sin almacenamiento puede volver a salir: no pasa nada.
    }
    this.sugerencias.update((l) => l.filter((x) => x.id !== s.id));
  }

  protected cargarSueno(): void {
    this.servicio.sueno().subscribe({ next: (s) => this.sueno.set(s), error: () => undefined });
  }

  /** «Me levanté» o «Me acosté»: se anota la hora y se actualiza el promedio. */
  protected responderLevantar(): void {
    if (!this.horaDicha()) return;
    this.error.set('');
    this.registrandoSueno.set(true);
    this.servicio.registrarLevantar(this.horaDicha()).subscribe({
      next: () => {
        this.registrandoSueno.set(false);
        this.diciendoHora.set(false);
        this.servicio.cargarHoy().subscribe({ error: () => undefined });
        this.servicio.cargar().subscribe({ error: () => undefined });
        this.cargarSueno();
      },
      error: (e) => {
        this.registrandoSueno.set(false);
        this.error.set(mensajeError(e, 'No pudimos anotarlo. Intenta de nuevo.'));
      },
    });
  }

  protected siesta(accion: 'iniciar' | 'terminar', hora?: string): void {
    this.error.set('');
    this.registrandoSiesta.set(true);
    const peticion =
      accion === 'iniciar' ? this.servicio.iniciarSiesta() : this.servicio.terminarSiesta(hora);
    peticion.subscribe({
      next: () => {
        this.registrandoSiesta.set(false);
        this.diciendoHoraSiesta.set(false);
        this.servicio.cargarHoy().subscribe({ error: () => undefined });
      },
      error: (e) => {
        this.registrandoSiesta.set(false);
        this.error.set(mensajeError(e, 'No pudimos anotar la siesta. Intenta de nuevo.'));
        this.servicio.cargarHoy().subscribe({ error: () => undefined });
      },
    });
  }

  protected anotarSueno(que: 'levantar' | 'dormir'): void {
    this.error.set('');
    this.registrandoSueno.set(true);
    const peticion =
      que === 'levantar' ? this.servicio.registrarLevantar() : this.servicio.registrarDormir();
    peticion.subscribe({
      next: () => {
        this.registrandoSueno.set(false);
        this.celebraciones.registro(que === 'levantar' ? 'levantar' : 'dormir');
        this.servicio.cargarHoy().subscribe({ error: () => undefined });
        this.servicio.cargar().subscribe({ error: () => undefined });
        this.cargarSueno();
      },
      error: (e) => {
        this.registrandoSueno.set(false);
        this.error.set(mensajeError(e, 'No pudimos anotarlo. Intenta de nuevo.'));
      },
    });
  }

  protected elegirModoHoras(modo: 'general' | 'por_dia'): void {
    this.modoHoras.set(modo);
    // Al pasar a una hora por día, cada día parte de la hora de siempre para que solo cambie lo que difiere.
    if (modo === 'por_dia') {
      this.horasSemana.update((h) =>
        Object.fromEntries(
          this.diasSemana.map((d) => [
            d.id,
            {
              levantarse: h[d.id]?.levantarse || this.levantarse(),
              dormir: h[d.id]?.dormir || this.dormir(),
            },
          ]),
        ),
      );
    }
  }

  protected fijarHoraSemana(dia: string, campo: 'levantarse' | 'dormir', valor: string): void {
    this.horasSemana.update((h) => {
      const actual = h[dia] ?? { levantarse: '', dormir: '' };
      return { ...h, [dia]: { ...actual, [campo]: valor } };
    });
  }

  protected fijarHoraComida(tiempo: string, valor: string): void {
    this.tiemposComida.update((l) =>
      l.map((t) =>
        t.tiempo === tiempo && valor
          ? { ...t, hora: valor, personalizada: valor !== t.referencia }
          : t,
      ),
    );
  }

  protected restablecerHoraComida(tiempo: string): void {
    this.tiemposComida.update((l) =>
      l.map((t) => (t.tiempo === tiempo ? { ...t, hora: t.referencia, personalizada: false } : t)),
    );
  }

  // ── Cambiar las horas de un solo día (hoy o mañana) ───────────────
  protected cambiandoDia = signal<'hoy' | 'manana' | null>(null);
  protected cambioLevantarse = signal('');
  protected cambioDormir = signal('');
  protected guardandoDia = signal(false);

  protected abrirCambioDia(cual: 'hoy' | 'manana'): void {
    const horas = this.hoy()?.horario[cual];
    this.cambioLevantarse.set(horas?.levantarse ?? '');
    this.cambioDormir.set(horas?.dormir ?? '');
    this.cambiandoDia.set(cual);
  }

  protected guardarCambioDia(quitar = false): void {
    const cual = this.cambiandoDia();
    if (!cual) return;
    const fecha = cual === 'hoy' ? hoyISO() : sumarDias(hoyISO(), 1);
    this.guardandoDia.set(true);
    this.error.set('');
    this.servicio
      .guardarHorario(fecha, {
        hora_levantarse: quitar ? null : this.cambioLevantarse() || null,
        hora_dormir: quitar ? null : this.cambioDormir() || null,
      })
      .subscribe({
        next: () => {
          this.guardandoDia.set(false);
          this.cambiandoDia.set(null);
          this.servicio.cargarHoy().subscribe({ error: () => undefined });
          this.servicio.cargar().subscribe({ error: () => undefined });
          void this.celular.actualizar();
        },
        error: (e) => {
          this.guardandoDia.set(false);
          this.error.set(mensajeError(e, 'No pudimos guardar las horas de ese día.'));
        },
      });
  }

  /** «30 min antes de lo previsto», «15 min después…» o «a la hora prevista». */
  protected frenteALoPrevisto(min: number | null): string {
    if (min === null) return '';
    if (Math.abs(min) < 5) return 'a la hora prevista';
    const m = Math.abs(min);
    const cuanto = m >= 60 ? this.duracion(m / 60) : `${m} min`;
    return `${cuanto} ${min < 0 ? 'antes' : 'después'} de lo previsto`;
  }

  /** 7,75 → «7 h 45 min». */
  protected duracion(horas: number): string {
    const minutos = Math.round(horas * 60);
    const h = Math.floor(minutos / 60);
    const m = minutos % 60;
    return m ? `${h} h ${m} min` : `${h} h`;
  }

  /** Un vaso que ya te tomaste, sin esperar el aviso. */
  protected unVaso(): void {
    this.error.set('');
    this.servicio.registrarAgua().subscribe({
      next: (r) => {
        this.anotado.set(`Vaso de ${r.ml} ml anotado a las ${this.horaDe(r.momento)}`);
        this.celebraciones.registro('agua');
        this.servicio.cargarHoy().subscribe({ error: () => undefined });
        this.servicio.cargar().subscribe({ error: () => undefined });
      },
      error: (e) => this.error.set(mensajeError(e, 'No pudimos anotar el vaso.')),
    });
  }

  /** Hora local de un instante ("8:15 a. m."). */
  protected horaDe(instante: string): string {
    return new Date(instante).toLocaleTimeString('es-CO', { hour: 'numeric', minute: '2-digit' });
  }

  protected leerLitros(texto: string): void {
    this.litros.set(parsearDecimal(texto));
  }

  protected alternarTipo(tipo: TipoAviso): void {
    this.apagados.update((l) => (l.includes(tipo) ? l.filter((t) => t !== tipo) : [...l, tipo]));
  }

  protected guardar(): void {
    if (!this.ajustesValidos()) return;
    this.guardando.set(true);
    this.guardado.set(false);
    this.error.set('');
    const l = this.litros();
    this.servicio
      .guardarHabitos({
        agua_ml: l === null ? null : Math.round(l * 1000),
        vaso_ml: this.vasoMl() ?? 250,
        hora_levantarse: this.levantarse() || null,
        hora_dormir: this.dormir() || null,
        hora_entreno: this.entreno() || null,
        avisos_apagados: this.apagados(),
        horas_agua: {
          ...(this.aguaDesde() ? { inicio: this.aguaDesde() } : {}),
          ...(this.aguaHasta() ? { fin: this.aguaHasta() } : {}),
        },
        // Con una hora para todos los días no queda ninguna por día: es una cosa o la otra.
        horas_semana:
          this.modoHoras() === 'general'
            ? {}
            : Object.fromEntries(
                this.diasSemana.map((d) => [
                  d.id,
                  {
                    levantarse: this.horasSemana()[d.id].levantarse,
                    dormir: this.horasSemana()[d.id].dormir,
                  },
                ]),
              ),
        horas_comida: Object.fromEntries(
          this.tiemposComida()
            .filter((t) => t.hora !== t.referencia)
            .map((t) => [t.tiempo, t.hora]),
        ),
      })
      .subscribe({
        next: () => {
          this.guardando.set(false);
          this.guardado.set(true);
          this.servicio.cargarHoy().subscribe({ error: () => undefined });
          void this.celular.actualizar();
        },
        error: (e) => {
          this.guardando.set(false);
          this.error.set(mensajeError(e, 'No pudimos guardar tus ajustes.'));
        },
      });
  }

  protected async alternarCelular(): Promise<void> {
    this.error.set('');
    try {
      if (this.celular.estado() === 'activo') await this.celular.desactivar();
      else await this.celular.activar();
    } catch {
      this.error.set('No pudimos activar las notificaciones en este celular.');
    }
  }

  protected probandoCelular = signal(false);
  protected resultadoPrueba = signal('');

  protected async probarCelular(): Promise<void> {
    this.error.set('');
    this.resultadoPrueba.set('');
    this.probandoCelular.set(true);
    try {
      const n = await this.celular.probar();
      this.resultadoPrueba.set(
        n
          ? 'Enviada: debe llegarte en unos segundos.'
          : 'Firebase no pudo entregarla. Intenta de nuevo.',
      );
    } catch (e) {
      this.error.set(mensajeError(e, 'No pudimos enviar la prueba.'));
    } finally {
      this.probandoCelular.set(false);
    }
  }

  protected async alternarPush(): Promise<void> {
    this.error.set('');
    try {
      if (this.push.estado() === 'activo') await this.push.desactivar();
      else await this.push.activar();
    } catch {
      this.error.set('No pudimos activar las notificaciones en este dispositivo.');
    }
  }
}
