import {
  Component,
  ChangeDetectionStrategy,
  inject,
  signal,
  computed,
  OnInit,
} from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { HttpClient } from '@angular/common/http';
import { ReactiveFormsModule, NonNullableFormBuilder, Validators } from '@angular/forms';
import { firstValueFrom } from 'rxjs';
import { InputTextModule } from 'primeng/inputtext';
import { TextareaModule } from 'primeng/textarea';
import { AutoCompleteModule } from 'primeng/autocomplete';
import { SelectButtonModule } from 'primeng/selectbutton';
import { ButtonModule } from 'primeng/button';
import { MessageModule } from 'primeng/message';
import { ProgressSpinnerModule } from 'primeng/progressspinner';

import { ThemeService } from '../core/services/theme';
import { AuthService } from '../core/services/auth';
import { ProcesoService } from '../core/services/proceso';
import { Implemento } from '../core/models/rutina.model';
import { Usuario } from '../core/models/usuario.model';
import { CrearProcesoPayload, Fase, Objetivo } from '../core/models/proceso.model';
import {
  DURACIONES_SUPLEMENTO,
  FASES,
  FRECUENCIAS_PESO,
  OBJETIVOS,
} from '../core/constants/proceso';
import { PAISES } from '../core/constants/paises';
import {
  MedicionForm,
  crearMedicionForm,
  leerMedicion,
} from '../shared/medicion-form/medicion-form';
import {
  EntrenamientoForm,
  crearEntrenamientoForm,
} from '../shared/entrenamiento-form/entrenamiento-form';
import { SelectorFotos } from '../shared/selector-fotos/selector-fotos';
import { FotoService, FotosPorPose } from '../core/services/foto';
import { AgendaService } from '../core/services/agenda';
import { SuplementoService } from '../core/services/suplemento';
import { CrearSuplementoPayload } from '../core/models/suplemento.model';
import { duracionEnPalabras, tipoSuplemento } from '../shared/suplementos';
import { fechaLocal, formatearFecha, formatearNumero, hoyISO, sumarDias } from '../shared/fechas';
import { clasesChip } from '../shared/chip';
import { mensajeError } from '../shared/errores';

import { environment } from '../../environments/environment';
import { DecimalInput, parsearDecimal } from '../shared/decimal-input';
const API = environment.apiUrl;
const MAX_DIAS_PROGRAMACION = 60;

type Modulos = 'alimentacion' | 'entrenamiento' | 'ambos';
type PasoId =
  | 'modulos'
  | 'perfil'
  | 'objetivo'
  | 'entrenamiento'
  | 'inicio'
  | 'duracion'
  | 'suplementos'
  | 'confirmar';
type Confirmacion = 'si' | 'otro' | 'nose';

/** Lo usual se asume; el usuario lo confirma, lo corrige o lo deja para después. */
interface SuplementoInicial {
  tipo: 'hipercalorico' | 'proteina';
  activo: boolean;
  /** null hasta que el usuario responda: lo asumido no se da por confirmado solo. */
  confirmacion: Confirmacion | null;
  /** Solo cuando la confirmación es 'otro'. */
  duracion: number | null;
  porcionesEnvase: number | null;
  porcionesDia: number | null;
}
type OpcionDuracion = 'control' | 'semanas8' | 'semanas12' | 'sin';
const MAX_DIAS_DURACION = 730;
type OpcionInicio = 'hoy' | 'lunes' | 'otra';

const PASOS: Record<PasoId, { titulo: string; descripcion: string }> = {
  duracion: {
    titulo: '¿Hasta cuándo va?',
    descripcion: 'Así ves en qué semana vas y cuánto falta. Puedes ajustarlo después.',
  },
  suplementos: {
    titulo: '¿Te formularon suplementos?',
    descripcion: 'Van con tu meta. La app te avisa cuándo reponer y cuándo revisar qué sigue.',
  },
  modulos: {
    titulo: '¿Qué quieres manejar?',
    descripcion: 'Puedes agregar el otro módulo más adelante desde tu perfil.',
  },
  perfil: {
    titulo: 'Sobre ti',
    descripcion: 'Con esto se ajustan tus planes a tu cuerpo y a la comida de tu región.',
  },
  objetivo: { titulo: 'Tu objetivo', descripcion: 'Define hacia dónde va este proceso.' },
  entrenamiento: {
    titulo: 'Tu entrenamiento',
    descripcion: 'Cómo, cuánto y con qué vas a entrenar.',
  },
  inicio: {
    titulo: '¿Cuándo empiezas?',
    descripcion: 'El día de inicio y tu medición de ese día son el punto de partida.',
  },
  confirmar: { titulo: 'Revisa y confirma', descripcion: 'Así queda tu proceso.' },
};

@Component({
  selector: 'app-onboarding',
  templateUrl: './onboarding.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    DecimalInput,
    ReactiveFormsModule,
    RouterLink,
    InputTextModule,
    TextareaModule,
    AutoCompleteModule,
    SelectButtonModule,
    ButtonModule,
    MessageModule,
    ProgressSpinnerModule,
    MedicionForm,
    EntrenamientoForm,
    SelectorFotos,
  ],
})
export class Onboarding implements OnInit {
  private http = inject(HttpClient);
  private router = inject(Router);
  private fb = inject(NonNullableFormBuilder);
  private auth = inject(AuthService);
  protected procesos = inject(ProcesoService);
  protected theme = inject(ThemeService);
  private fotos = inject(FotoService);
  private agenda = inject(AgendaService);
  private suplementos = inject(SuplementoService);

  protected readonly objetivos = OBJETIVOS;
  protected readonly fases = FASES;
  protected readonly frecuencias = FRECUENCIAS_PESO;
  protected readonly modulosOpciones: {
    value: Modulos;
    label: string;
    desc: string;
    icon: string;
  }[] = [
    {
      value: 'alimentacion',
      label: 'Alimentación',
      desc: 'Tu plan de comidas, el registro de cada día y recordatorios.',
      icon: 'pi pi-heart',
    },
    {
      value: 'entrenamiento',
      label: 'Entrenamiento',
      desc: 'Rutinas por día, sesiones con temporizador y tu progreso.',
      icon: 'pi pi-bolt',
    },
    {
      value: 'ambos',
      label: 'Camino del Guerrero',
      desc: 'Alimentación y entrenamiento conectados en un mismo proceso.',
      icon: 'pi pi-shield',
    },
  ];

  // ── Estado general ───────────────────────────────────────────────
  protected cargando = signal(true);
  protected enviando = signal(false);
  protected generandoRutina = signal(false);
  protected error = signal('');
  /** Lo que no se pudo completar después de crear el proceso. */
  protected avisos = signal<string[]>([]);
  protected modulos = signal<Modulos | null>(null);
  protected indice = signal(0);

  /** Si ya tiene un proceso, esto es "nuevo proceso", no el primer ingreso. */
  protected esNuevoProceso = computed(() => this.procesos.tieneProceso());

  private incluyeAlimentacion = computed(
    () => this.modulos() === 'alimentacion' || this.modulos() === 'ambos',
  );
  protected incluyeEntrenamiento = computed(
    () => this.modulos() === 'entrenamiento' || this.modulos() === 'ambos',
  );

  protected pasos = computed<PasoId[]>(() => [
    'modulos',
    ...(this.perfilCompleto() ? [] : (['perfil'] as PasoId[])),
    'objetivo',
    ...(this.incluyeEntrenamiento() ? (['entrenamiento'] as PasoId[]) : []),
    'inicio',
    'duracion',
    ...(this.incluyeAlimentacion() ? (['suplementos'] as PasoId[]) : []),
    'confirmar',
  ]);
  protected paso = computed(() => this.pasos()[this.indice()]);
  protected infoPaso = computed(() => PASOS[this.paso()]);
  protected esUltimo = computed(() => this.indice() === this.pasos().length - 1);

  // ── Formularios ──────────────────────────────────────────────────
  protected perfilForm = this.fb.group({
    estatura: this.fb.control<number | null>(null, [
      Validators.required,
      Validators.min(100),
      Validators.max(250),
    ]),
    frecuencia_peso: this.fb.control<15 | 30>(30),
    nacionalidad: this.fb.control('', Validators.required),
    region: this.fb.control('', Validators.required),
    preferencias_alimentarias: this.fb.control(''),
  });

  protected objetivoForm = this.fb.group({
    objetivo: this.fb.control<Objetivo>('ganar_musculo', Validators.required),
    fase: this.fb.control<Fase>(''),
    peso_objetivo: this.fb.control<number | null>(null, [Validators.min(20), Validators.max(300)]),
    notas: this.fb.control(''),
  });

  protected entrenamientoForm = crearEntrenamientoForm(this.fb);
  protected medicionForm = crearMedicionForm(this.fb, null);
  protected fotosIniciales = signal<FotosPorPose>({});

  // ── Implementos (solo si incluye entrenamiento) ──────────────────
  protected implementos = signal<Implemento[]>([]);
  protected seleccionados = signal<number[]>([]);
  protected implementosAdicionales = signal('');

  // ── Fecha de inicio ──────────────────────────────────────────────
  protected readonly hoy = hoyISO();
  protected opcionInicio = signal<OpcionInicio>('hoy');
  protected fechaOtra = signal('');

  /** El nuevo proceso debe iniciar después del día de inicio del actual. */
  protected fechaMinima = computed(() => {
    const actual = this.procesos.actual();
    const despuesDelActual = actual ? sumarDias(actual.fecha_inicio, 1) : this.hoy;
    return despuesDelActual > this.hoy ? despuesDelActual : this.hoy;
  });
  protected fechaMaxima = sumarDias(this.hoy, MAX_DIAS_PROGRAMACION);
  protected puedeIniciarHoy = computed(() => this.fechaMinima() === this.hoy);

  protected proximoLunes = computed(() => {
    let f = sumarDias(this.fechaMinima(), 0);
    do {
      f = sumarDias(f, 1);
    } while (fechaLocal(f).getDay() !== 1);
    return f;
  });

  protected fechaInicio = computed(() => {
    switch (this.opcionInicio()) {
      case 'hoy':
        return this.hoy;
      case 'lunes':
        return this.proximoLunes();
      case 'otra':
        return this.fechaOtra();
    }
  });
  protected iniciaHoy = computed(() => this.fechaInicio() === this.hoy);

  // ── Duración ─────────────────────────────────────────────────────
  protected opcionDuracion = signal<OpcionDuracion>('control');
  protected fechaControl = signal('');
  protected horaControl = signal('');

  protected opcionesDuracion = computed(() => {
    const inicio = this.fechaInicio();
    const semanas = (n: number) => (inicio ? sumarDias(inicio, n * 7 - 1) : '');
    return [
      {
        id: 'control' as const,
        titulo: 'Hasta mi próximo control',
        detalle: 'La fecha que te dio tu profesional',
      },
      {
        id: 'semanas8' as const,
        titulo: '8 semanas',
        detalle: semanas(8) ? `Hasta el ${formatearFecha(semanas(8))}` : '',
      },
      {
        id: 'semanas12' as const,
        titulo: '12 semanas',
        detalle: semanas(12) ? `Hasta el ${formatearFecha(semanas(12))}` : '',
      },
      { id: 'sin' as const, titulo: 'Sin definir', detalle: 'Lo defines más adelante' },
    ];
  });

  protected fechaFinPlan = computed(() => {
    const inicio = this.fechaInicio();
    switch (this.opcionDuracion()) {
      case 'control':
        return this.fechaControl() || null;
      case 'semanas8':
        return sumarDias(inicio, 8 * 7 - 1);
      case 'semanas12':
        return sumarDias(inicio, 12 * 7 - 1);
      case 'sin':
        return null;
    }
  });

  protected minimoControl = computed(() => sumarDias(this.fechaInicio() || this.hoy, 1));
  protected maximoControl = computed(() =>
    sumarDias(this.fechaInicio() || this.hoy, MAX_DIAS_DURACION),
  );

  private duracionValida(): boolean {
    if (this.opcionDuracion() !== 'control') return true;
    const f = this.fechaControl();
    return !!f && f >= this.minimoControl() && f <= this.maximoControl();
  }

  // ── Suplementos ──────────────────────────────────────────────────
  protected readonly confirmaciones: { label: string; value: Confirmacion }[] = [
    { label: 'Sí', value: 'si' },
    { label: 'Otro tiempo', value: 'otro' },
    { label: 'No sé', value: 'nose' },
  ];
  protected suplementosIniciales = signal<SuplementoInicial[]>([
    this.suplementoInicial('hipercalorico'),
    this.suplementoInicial('proteina'),
  ]);
  /** En volumen se asume hipercalórico y proteína hasta que el usuario diga otra cosa. */
  private suplementosPropuestos = false;

  private suplementoInicial(tipo: SuplementoInicial['tipo']): SuplementoInicial {
    return {
      tipo,
      activo: false,
      confirmacion: null,
      duracion: null,
      porcionesEnvase: null,
      porcionesDia: 1,
    };
  }

  protected nombreTipo = (tipo: SuplementoInicial['tipo']) => tipoSuplemento(tipo).label;
  protected duracionUsual = (tipo: SuplementoInicial['tipo']) => tipoSuplemento(tipo).duracionUsual;
  protected duracionEnPalabras = duracionEnPalabras;

  /** "Asumimos que va 3 meses." / "...todo el proceso (hasta el 5 dic 2026)." */
  protected supuesto(tipo: SuplementoInicial['tipo']): string {
    const usual = this.duracionUsual(tipo);
    const fin = this.fechaFinPlan();
    const hasta = usual === null && fin ? ` (hasta el ${formatearFecha(fin)})` : '';
    return `Asumimos que va ${duracionEnPalabras(usual)}${hasta}.`;
  }

  /** Las duraciones para corregir lo asumido: todas menos la usual. */
  protected otrasDuraciones(tipo: SuplementoInicial['tipo']) {
    return DURACIONES_SUPLEMENTO.filter((d) => d.value !== this.duracionUsual(tipo));
  }

  protected cambiarSuplemento(indice: number, cambios: Partial<SuplementoInicial>): void {
    this.suplementosIniciales.update((lista) =>
      lista.map((s, i) => {
        if (i !== indice) return s;
        const nuevo = { ...s, ...cambios };
        if (cambios.confirmacion === 'otro' && nuevo.duracion === null) {
          nuevo.duracion = this.otrasDuraciones(s.tipo)[0].value;
        }
        return nuevo;
      }),
    );
  }

  protected leerPorciones(texto: string): number | null {
    return parsearDecimal(texto);
  }

  private suplementosValidos(): boolean {
    return this.suplementosIniciales()
      .filter((s) => s.activo)
      .every(
        (s) =>
          s.confirmacion !== null &&
          (s.porcionesEnvase === null ||
            (Number.isInteger(s.porcionesEnvase) &&
              s.porcionesEnvase >= 1 &&
              s.porcionesEnvase <= 500)) &&
          s.porcionesDia !== null &&
          s.porcionesDia >= 0.5 &&
          s.porcionesDia <= 10,
      );
  }

  private payloadSuplemento(s: SuplementoInicial, proceso: number): CrearSuplementoPayload {
    return {
      proceso,
      tipo: s.tipo,
      nombre: '',
      duracion_dias: s.confirmacion === 'otro' ? s.duracion : this.duracionUsual(s.tipo),
      duracion_confirmada: s.confirmacion !== 'nose',
      porciones_envase: s.porcionesEnvase,
      porciones_dia: s.porcionesDia ?? 1,
    };
  }

  /** "Proteína · 3 meses, por confirmar" para el resumen. */
  protected resumenSuplementos(): string[] {
    return this.suplementosIniciales()
      .filter((s) => s.activo)
      .map((s) => {
        const p = this.payloadSuplemento(s, 0);
        const duracion = duracionEnPalabras(p.duracion_dias);
        return `${this.nombreTipo(s.tipo)} · ${duracion}${p.duracion_confirmada ? '' : ', por confirmar'}`;
      });
  }

  protected formatearFecha = formatearFecha;
  protected num = formatearNumero;
  protected paisesFiltrados = signal<string[]>([]);

  ngOnInit(): void {
    const u = this.auth.usuario();
    if (u) {
      this.perfilForm.patchValue({
        estatura: u.estatura,
        frecuencia_peso: u.frecuencia_peso,
        nacionalidad: u.nacionalidad,
        region: u.region,
        preferencias_alimentarias: u.preferencias_alimentarias,
      });
      this.medicionForm.controls.talla_cm.setValue(u.estatura);
    }
    this.procesos.cargar(true).subscribe({
      next: () => {
        if (!this.puedeIniciarHoy()) this.opcionInicio.set('lunes');
        this.cargando.set(false);
      },
      error: () => this.cargando.set(false),
    });
    this.http.get<Implemento[]>(`${API}/rutinas/implementos/`).subscribe({
      next: (data) => this.implementos.set(data),
    });
  }

  /** En un proceso nuevo, si el perfil ya está completo no se vuelve a pedir. */
  private perfilCompleto = computed(() => {
    const u = this.auth.usuario();
    return this.esNuevoProceso() && !!u?.estatura && !!u.nacionalidad && !!u.region;
  });

  // ── Navegación ───────────────────────────────────────────────────
  protected pasoValido(): boolean {
    switch (this.paso()) {
      case 'modulos':
        return this.modulos() !== null;
      case 'perfil':
        return this.perfilForm.valid;
      case 'objetivo':
        return this.objetivoForm.valid;
      case 'entrenamiento':
        return this.implementos().length === 0 || this.seleccionados().length > 0;
      case 'inicio':
        return this.fechaInicioValida() && (!this.iniciaHoy() || this.medicionForm.valid);
      case 'duracion':
        return this.duracionValida();
      case 'suplementos':
        return this.suplementosValidos();
      case 'confirmar':
        return true;
    }
  }

  private fechaInicioValida(): boolean {
    const f = this.fechaInicio();
    return !!f && f >= this.fechaMinima() && f <= this.fechaMaxima;
  }

  protected siguiente(): void {
    if (!this.pasoValido()) return;
    if (this.esUltimo()) {
      this.confirmar();
      return;
    }
    this.indice.update((i) => i + 1);
    if (this.paso() === 'inicio' && !this.medicionForm.controls.talla_cm.value) {
      this.medicionForm.controls.talla_cm.setValue(this.perfilForm.controls.estatura.value);
    }
    if (this.paso() === 'suplementos' && !this.suplementosPropuestos) {
      this.suplementosPropuestos = true;
      const volumen = this.objetivoForm.controls.fase.value === 'volumen';
      this.suplementosIniciales.update((lista) => lista.map((s) => ({ ...s, activo: volumen })));
    }
    window.scrollTo({ top: 0 });
  }

  protected anterior(): void {
    this.error.set('');
    this.indice.update((i) => Math.max(0, i - 1));
  }

  protected elegirModulos(valor: Modulos): void {
    this.modulos.set(valor);
  }

  // ── Implementos ──────────────────────────────────────────────────
  protected isSeleccionado(id: number): boolean {
    return this.seleccionados().includes(id);
  }

  protected toggleImplemento(id: number): void {
    const sinImplemento = this.implementos().find((i) => i.es_sin_implemento)?.id;
    const actual = this.seleccionados();
    if (id === sinImplemento) {
      this.seleccionados.set(actual.includes(id) ? [] : [id]);
      return;
    }
    const filtrado = actual.filter((i) => i !== sinImplemento);
    this.seleccionados.set(
      filtrado.includes(id) ? filtrado.filter((i) => i !== id) : [...filtrado, id],
    );
  }

  protected clasesOpcion(activa: boolean): string {
    const base =
      'flex items-center gap-3 p-3 rounded-xl border-2 text-left transition-colors w-full focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-guerrero-red';
    return activa
      ? `${base} border-guerrero-red bg-red-50 dark:bg-guerrero-red/10 text-guerrero-red`
      : `${base} border-gray-200 dark:border-dark-700 text-gray-600 dark:text-gray-400 hover:border-gray-300 dark:hover:border-gray-600`;
  }

  protected clasesChip = clasesChip;

  protected filtrarPaises(query: string): void {
    const q = query.toLowerCase();
    this.paisesFiltrados.set(PAISES.filter((p) => p.toLowerCase().includes(q)));
  }

  // ── Resumen ──────────────────────────────────────────────────────
  protected resumen() {
    const o = this.objetivoForm.getRawValue();
    return {
      modulos: this.modulosOpciones.find((m) => m.value === this.modulos())?.label ?? '',
      objetivo: OBJETIVOS.find((x) => x.value === o.objetivo)?.label ?? '',
      fase: FASES.find((x) => x.value === o.fase && x.value !== '')?.label ?? null,
      pesoObjetivo: o.peso_objetivo,
      notas: o.notas.trim(),
    };
  }

  protected pesoInicial(): number | null {
    return this.medicionForm.controls.peso_kg.value;
  }

  // ── Envío ────────────────────────────────────────────────────────
  private async confirmar(): Promise<void> {
    this.enviando.set(true);
    this.error.set('');
    try {
      if (!this.perfilCompleto()) await this.guardarPerfil();

      const o = this.objetivoForm.getRawValue();
      const payload: CrearProcesoPayload = {
        objetivo: o.objetivo,
        fase: o.fase,
        peso_objetivo: o.peso_objetivo,
        notas: o.notas.trim(),
        incluye_alimentacion: this.incluyeAlimentacion(),
        incluye_entrenamiento: this.incluyeEntrenamiento(),
        fecha_inicio: this.fechaInicio(),
        fecha_fin_plan: this.fechaFinPlan(),
        medicion_inicial: this.iniciaHoy() ? leerMedicion(this.medicionForm, false) : null,
        entrenamiento: this.incluyeEntrenamiento() ? this.entrenamientoForm.getRawValue() : null,
      };
      const proceso = await firstValueFrom(this.procesos.crear(payload));
      if (proceso.medicion_inicial) await this.subirFotosIniciales(proceso.medicion_inicial.id);
      if (this.opcionDuracion() === 'control') await this.agendarControl();
      await this.agregarSuplementos(proceso.id);
    } catch (err) {
      this.error.set(
        mensajeError(err, 'No pudimos crear tu proceso. Revisa los datos e intenta de nuevo.'),
      );
      this.enviando.set(false);
      return;
    }

    if (this.incluyeEntrenamiento()) await this.prepararRutina();
    await firstValueFrom(this.procesos.refrescar());
    this.enviando.set(false);
    if (!this.avisos().length) this.router.navigate(['/inicio']);
  }

  /** El proceso ya existe: si las fotos fallan se avisa y se pueden agregar desde Progreso. */
  private async subirFotosIniciales(medicionId: number): Promise<void> {
    try {
      await firstValueFrom(this.fotos.subirVarias(medicionId, this.fotosIniciales()));
    } catch {
      this.avisos.update((a) => [
        ...a,
        'No pudimos subir tus fotos de inicio. Agrégalas desde Progreso durante esta semana.',
      ]);
    }
  }

  /** El control queda en la agenda para avisar unos días antes. */
  private async agendarControl(): Promise<void> {
    try {
      await firstValueFrom(
        this.agenda.crear({
          tipo: 'control',
          titulo: 'Control de seguimiento',
          fecha: this.fechaControl(),
          hora: this.horaControl() || null,
          nota: '',
          avisar_dias_antes: 3,
        }),
      );
    } catch {
      this.avisos.update((a) => [
        ...a,
        'No pudimos agendar tu control. Agrégalo desde Progreso › Agenda.',
      ]);
    }
  }

  /** Cada uno crea sus recordatorios sugeridos (confirmar, reponer, revisar). */
  private async agregarSuplementos(procesoId: number): Promise<void> {
    const activos = this.suplementosIniciales().filter((s) => s.activo);
    try {
      for (const s of activos) {
        await firstValueFrom(this.suplementos.crear(this.payloadSuplemento(s, procesoId)));
      }
    } catch {
      this.avisos.update((a) => [
        ...a,
        'No pudimos guardar tus suplementos. Agrégalos desde Progreso › Agenda.',
      ]);
    }
  }

  private async guardarPerfil(): Promise<void> {
    const p = this.perfilForm.getRawValue();
    const usuario = await firstValueFrom(this.http.patch<Usuario>(`${API}/usuarios/perfil/`, p));
    this.auth.actualizarUsuario(usuario);
  }

  /** El proceso ya existe: si la rutina falla, se avisa y se puede generar luego desde Rutinas. */
  private async prepararRutina(): Promise<void> {
    this.generandoRutina.set(true);
    try {
      await firstValueFrom(
        this.http.patch(`${API}/usuarios/perfil/`, {
          implementos_adicionales: this.implementosAdicionales(),
        }),
      );
      const existentes = await firstValueFrom(
        this.http.get<{ id: number }[]>(`${API}/rutinas/mis-implementos/`),
      );
      for (const e of existentes) {
        await firstValueFrom(this.http.delete(`${API}/rutinas/mis-implementos/${e.id}/`));
      }
      for (const id of this.seleccionados()) {
        await firstValueFrom(
          this.http.post(`${API}/rutinas/mis-implementos/`, { implemento_id: id }),
        );
      }
      await firstValueFrom(this.http.post(`${API}/nutricion/generar-rutina/`, {}));
    } catch {
      this.avisos.update((a) => [
        ...a,
        'No pudimos preparar tu rutina. Puedes generarla desde la sección Rutinas.',
      ]);
    } finally {
      this.generandoRutina.set(false);
    }
  }

  protected continuar(): void {
    this.router.navigate(['/inicio']);
  }
}
