import {
  Component,
  ChangeDetectionStrategy,
  OnInit,
  computed,
  inject,
  signal,
} from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Observable } from 'rxjs';
import { ButtonModule } from 'primeng/button';
import { DialogModule } from 'primeng/dialog';
import { InputTextModule } from 'primeng/inputtext';
import { MessageModule } from 'primeng/message';
import { SelectButtonModule } from 'primeng/selectbutton';

import { SuplementoService } from '../../core/services/suplemento';
import { FotoSuplemento } from '../../shared/foto-suplemento';
import { VisorService } from '../../core/services/visor';
import { parsearDecimal } from '../../shared/decimal-input';
import { MinutaService } from '../../core/services/minuta';
import { TIEMPOS_COMIDA } from '../../core/constants/nutricion';
import { ProcesoService } from '../../core/services/proceso';
import { Recordatorio } from '../../core/models/agenda.model';
import {
  Suplemento,
  SuplementoPayload,
  TablaNutricional,
  TipoSuplemento,
  Toma,
} from '../../core/models/suplemento.model';
import {
  DURACIONES_SUPLEMENTO,
  EXTENSIONES_SUPLEMENTO,
  TIPOS_SUPLEMENTO,
} from '../../core/constants/proceso';
import { EtiquetaSuplemento } from '../../shared/etiqueta-suplemento/etiqueta-suplemento';
import { TomasSuplemento } from '../../shared/tomas-suplemento/tomas-suplemento';
import { cuandoEs, formatearFecha, formatearHora, formatearNumero } from '../../shared/fechas';
import { clasesChip } from '../../shared/chip';
import { mensajeError } from '../../shared/errores';
import {
  Etiqueta,
  avanceSuplemento,
  duracionEnPalabras,
  erroresEtiqueta,
  etiquetaDe,
  etiquetaVacia,
  nombreSuplemento,
  payloadEtiqueta,
  scoopsFaltantes,
  tipoSuplemento,
} from '../../shared/suplementos';

/** Qué muestra el diálogo. Los tres últimos resuelven un recordatorio sugerido. */
type Modo = 'nuevo' | 'editar' | 'reemplazar' | 'confirmar' | 'reponer' | 'revisar';

const TITULOS: Record<Modo, string> = {
  nuevo: 'Agregar suplemento',
  editar: 'Editar suplemento',
  reemplazar: 'Cambiar de producto',
  confirmar: 'Confirma la duración',
  reponer: 'Envase nuevo',
  revisar: '¿Qué sigue?',
};

/** Suplementos del proceso: cuánto llevan, cuándo se acaba el envase y qué sigue al terminar. */
type CampoTabla = keyof TablaNutricional;
const CAMPOS_TABLA: { id: CampoTabla; label: string; max: number }[] = [
  { id: 'porcion_g', label: 'Porción (g)', max: 1000 },
  { id: 'liquido_ml', label: 'Se prepara con (ml)', max: 3000 },
  { id: 'kcal', label: 'Calorías (kcal)', max: 1500 },
  { id: 'proteina_g', label: 'Proteína (g)', max: 200 },
  { id: 'carbohidratos_g', label: 'Carbohidratos (g)', max: 300 },
  { id: 'grasa_g', label: 'Grasa (g)', max: 200 },
];

import { Ayuda } from '../../shared/ayuda/ayuda';

@Component({
  selector: 'app-suplementos',
  templateUrl: './suplementos.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [Ayuda, 
    ReactiveFormsModule,
    ButtonModule,
    DialogModule,
    InputTextModule,
    MessageModule,
    SelectButtonModule,
    EtiquetaSuplemento,
    TomasSuplemento,
    FotoSuplemento,
  ],
})
export class Suplementos implements OnInit {
  private fb = inject(NonNullableFormBuilder);
  protected servicio = inject(SuplementoService);
  private procesos = inject(ProcesoService);
  private minutas = inject(MinutaService);

  /** Con plan de la nutricionista, el suplemento se ubica en una comida de la minuta. */
  protected minuta = this.minutas.vigente;

  /** La hipercalórica es un tipo de proteína: se escribe en el nombre, no es otra categoría. */
  protected tipos = TIPOS_SUPLEMENTO.filter((t) => t.value !== 'hipercalorico');
  protected duraciones = DURACIONES_SUPLEMENTO;
  protected extensiones = EXTENSIONES_SUPLEMENTO;
  protected confirmaciones = [
    { label: 'Sí, me lo indicaron', value: true },
    { label: 'No estoy seguro', value: false },
  ];
  protected formatearFecha = formatearFecha;
  protected cuandoEs = cuandoEs;
  protected num = formatearNumero;
  protected nombre = nombreSuplemento;
  protected duracionEnPalabras = duracionEnPalabras;
  protected avance = avanceSuplemento;

  protected error = signal('');
  protected modo = signal<Modo | null>(null);
  protected actual = signal<Suplemento | null>(null);
  protected guardando = signal(false);
  protected confirmarEliminar = signal(false);
  protected extension = signal(EXTENSIONES_SUPLEMENTO[0].value);

  protected titulo = computed(() => {
    const modo = this.modo();
    return modo ? TITULOS[modo] : '';
  });
  /** Modos sin formulario: el error va al pie del diálogo. */
  protected esResolucion = computed(() =>
    ['confirmar', 'reponer', 'revisar'].includes(this.modo() ?? ''),
  );
  protected finPlan = computed(() => this.procesos.vigente()?.fecha_fin_plan ?? null);

  protected form = this.fb.group({
    tipo: this.fb.control<TipoSuplemento>('proteina'),
    nombre: this.fb.control('', Validators.maxLength(120)),
    info_url: this.fb.control('', [Validators.maxLength(500), Validators.pattern(/^(https?:\/\/\S+)?$/i)]),
    duracion_dias: this.fb.control<number | null>(90),
    duracion_confirmada: this.fb.control(false),
  });

  /** La tabla nutricional por porción, como texto de cada campo (también vive fuera del formulario). */
  protected camposTabla = CAMPOS_TABLA;
  protected tabla = signal<Record<CampoTabla, string>>(this.tablaVacia());
  protected leyendoTabla = signal(false);
  protected notaTabla = signal('');

  private tablaVacia(): Record<CampoTabla, string> {
    return { porcion_g: '', liquido_ml: '', kcal: '', proteina_g: '', carbohidratos_g: '', grasa_g: '' };
  }

  private tablaDe(s: Suplemento | null): Record<CampoTabla, string> {
    const t = s?.tabla_nutricional;
    const texto = (v: number | undefined) => (v === undefined ? '' : String(v).replace('.', ','));
    return t
      ? {
          porcion_g: texto(t.porcion_g),
          liquido_ml: texto(t.liquido_ml),
          kcal: texto(t.kcal),
          proteina_g: texto(t.proteina_g),
          carbohidratos_g: texto(t.carbohidratos_g),
          grasa_g: texto(t.grasa_g),
        }
      : this.tablaVacia();
  }

  protected escribirTabla(campo: CampoTabla, valor: string): void {
    this.tabla.update((t) => ({ ...t, [campo]: valor }));
    this.notaTabla.set('');
  }

  /** null si no escribió nada; si escribió algo, calorías y proteína son obligatorias. */
  private tablaPayload(): TablaNutricional | null {
    const t = this.tabla();
    const nums = Object.fromEntries(
      CAMPOS_TABLA.map((c) => [c.id, parsearDecimal(t[c.id])]),
    ) as Record<CampoTabla, number | null>;
    if (CAMPOS_TABLA.every((c) => nums[c.id] === null)) return null;
    const resultado: Partial<TablaNutricional> = {};
    for (const c of CAMPOS_TABLA) {
      if (nums[c.id] !== null) (resultado as Record<string, number>)[c.id] = nums[c.id]!;
    }
    return resultado as TablaNutricional;
  }

  protected errorTabla = computed(() => {
    const t = this.tabla();
    const vacia = CAMPOS_TABLA.every((c) => t[c.id].trim() === '');
    if (vacia) return '';
    for (const c of CAMPOS_TABLA) {
      const n = parsearDecimal(t[c.id]);
      if (n !== null && (Number.isNaN(n) || n > c.max)) return `${c.label}: escribe un número hasta ${c.max}.`;
    }
    return parsearDecimal(t.kcal) === null || parsearDecimal(t.proteina_g) === null
      ? 'Faltan las calorías y los gramos de proteína por porción.'
      : '';
  });

  /** La IA lee la etiqueta que subiste y propone la tabla; tú la revisas y guardas. */
  protected leerTabla(): void {
    const s = this.actual();
    if (!s) return;
    this.leyendoTabla.set(true);
    this.error.set('');
    this.notaTabla.set('');
    this.servicio.leerTabla(s.id).subscribe({
      next: ({ tabla, nota }) => {
        this.tabla.set(
          this.tablaDe({ tabla_nutricional: tabla } as Suplemento),
        );
        this.notaTabla.set(nota || 'Revisa que coincida con tu etiqueta y guarda.');
        // Si la etiqueta dice con cuánto líquido se prepara y aún no lo habías escrito, se propone.
        if (tabla.liquido_ml && this.etiqueta().liquido && this.etiqueta().liquidoMl === null) {
          this.etiqueta.update((e) => ({ ...e, liquidoMl: tabla.liquido_ml! }));
        }
        this.leyendoTabla.set(false);
      },
      error: (err) => {
        this.error.set(mensajeError(err, 'No pudimos leer la etiqueta.'));
        this.leyendoTabla.set(false);
      },
    });
  }

  /** Lo que dice la etiqueta y en qué comidas se toma: viven fuera del formulario. */
  protected etiqueta = signal<Etiqueta>(etiquetaVacia());
  protected tomas = signal<Toma[]>([]);
  protected etiquetaValida = computed(
    () =>
      Object.keys(erroresEtiqueta(this.etiqueta())).length === 0 &&
      scoopsFaltantes(this.tomas(), this.etiqueta().scoops) === 0,
  );

  private ruta = inject(ActivatedRoute);
  private visor = inject(VisorService);

  ngOnInit(): void {
    // Si se llega desde "Mi proteína" (#suplementos), se baja hasta aquí cuando ya cargó la lista.
    const irAqui = this.ruta.snapshot.fragment === 'suplementos';
    this.servicio.cargar().subscribe({
      next: () => {
        if (irAqui) setTimeout(() => document.getElementById('suplementos')?.scrollIntoView({ block: 'start' }), 100);
      },
      error: (err) => this.error.set(mensajeError(err, 'No pudimos cargar tus suplementos.')),
    });
    if (this.minutas.minutas() === null)
      this.minutas.cargar().subscribe({ error: () => undefined });
  }

  /** "3 scoops en las onces y 3 en el algo · porción de 150 g (6 scoops)". */
  protected ubicacion(s: Suplemento): string {
    const partes: string[] = [];
    if (s.tomas.length) {
      const donde = s.tomas.map((t) => {
        const cuanto = t.scoops
          ? `${formatearNumero(t.scoops, 1)} ${t.scoops === 1 ? 'scoop' : 'scoops'} en `
          : 'En ';
        const donde =
          t.tiempo === 'otro' ? `a las ${t.hora ? formatearHora(t.hora) : 'la hora que elegiste'}` : TIEMPOS_COMIDA[t.tiempo].con;
        return `${cuanto}${donde}`;
      });
      partes.push(donde.join(' y '));
    }
    if (s.porcion_g) {
      const scoops = s.scoops_porcion
        ? ` (${formatearNumero(s.scoops_porcion, 1)} ${s.scoops_porcion === 1 ? 'scoop' : 'scoops'})`
        : '';
      partes.push(`porción de ${formatearNumero(s.porcion_g, 1)} g${scoops}`);
    }
    const texto = partes.join(' · ');
    return texto ? texto.charAt(0).toUpperCase() + texto.slice(1) : '';
  }

  /** Abre lo que resuelve un recordatorio sugerido desde la agenda. */
  resolver(r: Recordatorio): void {
    const s = r.suplemento !== null ? this.servicio.porId(r.suplemento) : undefined;
    if (!s || !r.motivo) return;
    this.abrir(r.motivo, s);
  }

  protected abrir(modo: Modo, s: Suplemento | null = null): void {
    this.error.set('');
    this.confirmarEliminar.set(false);
    this.actual.set(s);
    this.extension.set(EXTENSIONES_SUPLEMENTO[0].value);
    if (modo === 'nuevo') {
      this.cargarFormulario({ tipo: 'proteina', ...this.porDefecto('proteina') });
      this.etiqueta.set(etiquetaVacia());
      this.tomas.set([]);
      this.tabla.set(this.tablaVacia());
    } else if (s) {
      const nuevo = modo === 'reemplazar';
      this.cargarFormulario(
        nuevo ? { tipo: s.tipo, ...this.porDefecto(s.tipo), duracion_confirmada: true } : s,
      );
      // Otro producto empieza con su etiqueta, pero sigue tomándose en las mismas comidas.
      this.etiqueta.set(nuevo ? etiquetaVacia() : etiquetaDe(s));
      this.tomas.set(nuevo ? s.tomas.map((t) => ({ ...t, scoops: null })) : s.tomas);
      this.tabla.set(nuevo ? this.tablaVacia() : this.tablaDe(s));
    }
    this.notaTabla.set('');
    this.modo.set(modo);
  }

  protected cerrar(): void {
    this.modo.set(null);
  }

  private porDefecto(tipo: TipoSuplemento): SuplementoPayload {
    return {
      nombre: '',
      duracion_dias: tipoSuplemento(tipo).duracionUsual,
      duracion_confirmada: false,
      porciones_envase: null,
      peso_envase_g: null,
      porcion_g: null,
      scoops_porcion: null,
      porciones_dia: 1,
      liquido: '',
      liquido_ml: null,
      leche_ml: null,
      leche_nutricional: null,
    };
  }

  private cargarFormulario(v: SuplementoPayload & { tipo: TipoSuplemento }): void {
    this.form.reset({
      tipo: v.tipo,
      nombre: v.nombre,
      info_url: v.info_url ?? '',
      duracion_dias: v.duracion_dias,
      duracion_confirmada: v.duracion_confirmada,
    });
  }

  protected clasesChip = clasesChip;

  /** Al cambiar el tipo de uno nuevo se propone su duración usual. */
  protected cambiarTipo(tipo: TipoSuplemento): void {
    this.form.patchValue({ duracion_dias: tipoSuplemento(tipo).duracionUsual });
  }

  private payload(): SuplementoPayload {
    const v = this.form.getRawValue();
    return {
      nombre: v.nombre.trim(),
      info_url: v.info_url.trim(),
      duracion_dias: v.duracion_dias,
      duracion_confirmada: v.duracion_confirmada,
      porciones_envase: null,
      ...payloadEtiqueta(this.etiqueta()),
      ...(this.minuta() ? { tomas: this.tomas() } : {}),
      tabla_nutricional: this.tablaPayload(),
    };
  }

  protected guardar(): void {
    const modo = this.modo();
    const s = this.actual();
    if (this.form.invalid || !this.etiquetaValida() || this.errorTabla()) return;
    if (modo === 'nuevo') {
      this.ejecutar(this.servicio.crear({ ...this.payload(), tipo: this.form.getRawValue().tipo }));
    } else if (modo === 'editar' && s) {
      this.ejecutar(this.servicio.actualizar(s.id, this.payload()));
    } else if (modo === 'reemplazar' && s) {
      this.ejecutar(this.servicio.accion(s.id, 'reemplazar', this.payload()));
    }
  }

  /** Confirma la duración asumida tal cual o con la que el usuario corrigió. */
  protected confirmar(duracion: number | null): void {
    const s = this.actual();
    if (!s) return;
    this.ejecutar(
      this.servicio.actualizar(s.id, { duracion_dias: duracion, duracion_confirmada: true }),
    );
  }

  protected abrirEnvase(s: Suplemento): void {
    this.ejecutar(this.servicio.accion(s.id, 'abrir-envase'));
  }

  protected continuar(): void {
    const s = this.actual();
    if (s) this.ejecutar(this.servicio.accion(s.id, 'continuar', { dias: this.extension() }));
  }

  /** Qué falta por adjuntar, para ofrecerlo en la tarjeta ('' si ya está todo). */
  protected faltaAdjunto(s: Suplemento): string {
    const info = !!(s.info_url || s.info_archivo_tipo);
    if (!s.tiene_foto && !info) return 'Agregar foto e información nutricional';
    if (!s.tiene_foto) return 'Agregar foto de la proteína';
    if (!info) return 'Agregar información nutricional (enlace, foto o PDF)';
    return '';
  }

  /** Abre la edición del suplemento justo en lo que falta adjuntar. */
  protected agregarInfo(s: Suplemento): void {
    this.abrir('editar', s);
    const destino = s.info_archivo_tipo && !s.tabla_nutricional ? 'sp-tabla' : s.tiene_foto ? 'sp-info' : 'sp-foto';
    setTimeout(() => document.getElementById(destino)?.scrollIntoView({ block: 'center' }), 150);
  }

  // ── Foto del producto (al instante, como el archivo de la etiqueta) ──
  protected subiendoFoto = signal(false);
  /** Cambia con cada foto nueva, para que la miniatura se vuelva a pedir. */
  protected fotoVersion = signal(0);

  protected elegirFoto(evento: Event): void {
    const campo = evento.target as HTMLInputElement;
    const archivo = campo.files?.[0];
    campo.value = '';
    const s = this.actual();
    if (!archivo || !s) return;
    this.cambiarFoto(this.servicio.subirFoto(s.id, archivo));
  }

  protected quitarFoto(): void {
    const s = this.actual();
    if (s) this.cambiarFoto(this.servicio.quitarFoto(s.id));
  }

  private cambiarFoto(peticion: Observable<Suplemento>): void {
    this.subiendoFoto.set(true);
    this.error.set('');
    peticion.subscribe({
      next: (s) => {
        this.actual.set(s);
        this.fotoVersion.update((v) => v + 1);
        this.subiendoFoto.set(false);
      },
      error: (err) => {
        this.subiendoFoto.set(false);
        this.error.set(mensajeError(err, 'No pudimos guardar la foto.'));
      },
    });
  }

  // ── Información nutricional (enlace en el formulario; archivo aparte, al instante) ──
  protected subiendoInfo = signal(false);

  protected elegirInfo(evento: Event): void {
    const campo = evento.target as HTMLInputElement;
    const archivo = campo.files?.[0];
    campo.value = '';
    const s = this.actual();
    if (!archivo || !s) return;
    this.cambiarInfo(this.servicio.subirInfo(s.id, archivo));
  }

  protected quitarInfo(): void {
    const s = this.actual();
    if (s) this.cambiarInfo(this.servicio.quitarInfo(s.id));
  }

  private cambiarInfo(peticion: Observable<Suplemento>): void {
    this.subiendoInfo.set(true);
    this.error.set('');
    peticion.subscribe({
      next: (s) => {
        this.actual.set(s);
        this.subiendoInfo.set(false);
      },
      error: (err) => {
        this.subiendoInfo.set(false);
        this.error.set(mensajeError(err, 'No pudimos guardar el archivo.'));
      },
    });
  }

  /** Abre la etiqueta (foto o PDF) en una ventana dentro de la app. */
  protected verInfo(s: Suplemento): void {
    this.visor.abrir(`Etiqueta · ${s.nombre || s.tipo_nombre}`, this.servicio.verInfo(s.id));
  }

  /** Abre la foto del producto en grande, dentro de la app. */
  protected verFoto(s: Suplemento): void {
    this.visor.abrir(`${s.nombre || s.tipo_nombre}`, this.servicio.verFoto(s.id));
  }

  protected terminar(): void {
    const s = this.actual();
    if (s) this.ejecutar(this.servicio.accion(s.id, 'terminar'));
  }

  protected eliminar(): void {
    const s = this.actual();
    if (s) this.ejecutar(this.servicio.eliminar(s.id));
  }

  private ejecutar(peticion: Observable<unknown>): void {
    this.guardando.set(true);
    this.error.set('');
    peticion.subscribe({
      next: () => {
        this.guardando.set(false);
        this.cerrar();
      },
      error: (err) => {
        this.error.set(mensajeError(err, 'No pudimos guardar el cambio.'));
        this.guardando.set(false);
      },
    });
  }
}
