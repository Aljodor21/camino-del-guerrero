import {
  ChangeDetectionStrategy,
  Component,
  OnInit,
  computed,
  inject,
  signal,
} from '@angular/core';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { Observable, concat, defer } from 'rxjs';
import { toArray } from 'rxjs/operators';
import { ButtonModule } from 'primeng/button';
import { InputTextModule } from 'primeng/inputtext';
import { MessageModule } from 'primeng/message';
import { TextareaModule } from 'primeng/textarea';

import { MinutaService } from '../../core/services/minuta';
import { ProcesoService } from '../../core/services/proceso';
import { SuplementoService } from '../../core/services/suplemento';
import {
  GrupoMinuta,
  MinutaPayload,
  OrigenMinuta,
  PorcionesMinuta,
  ReglaPorFuera,
  TiempoComida,
} from '../../core/models/minuta.model';
import { Suplemento, TipoSuplemento, Toma } from '../../core/models/suplemento.model';
import { OPCIONES_POR_FUERA, TIEMPOS_COMIDA, porcionesDe } from '../../core/constants/nutricion';
import { EtiquetaSuplemento } from '../../shared/etiqueta-suplemento/etiqueta-suplemento';
import { TomasSuplemento } from '../../shared/tomas-suplemento/tomas-suplemento';
import { clasesChip } from '../../shared/chip';
import { mensajeError } from '../../shared/errores';
import { formatearFecha, formatearNumero, hoyISO } from '../../shared/fechas';
import { PeriodoPlan } from '../../shared/periodo-plan/periodo-plan';
import { tiemposDe } from '../../shared/minuta';
import {
  Etiqueta,
  erroresEtiqueta,
  etiquetaDe,
  etiquetaVacia,
  payloadEtiqueta,
  scoopsFaltantes,
  tipoSuplemento,
} from '../../shared/suplementos';
import { EditorMinuta } from '../editor-minuta/editor-minuta';
import { TablaMinuta } from '../tabla-minuta/tabla-minuta';

type Paso = 'origen' | 'minuta' | 'suplementos' | 'fuera';
const PASOS: Paso[] = ['origen', 'minuta', 'suplementos', 'fuera'];
const MAX_BYTES = 10 * 1024 * 1024;

/** Un suplemento en la minuta: el que ya tiene o uno que se agrega aquí. */
interface SuplementoEnMinuta {
  existente: Suplemento | null;
  tipo: TipoSuplemento;
  nombre: string;
  activo: boolean;
  etiqueta: Etiqueta;
  tomas: Toma[];
}

/**
 * Arma el plan de comida: la minuta de la nutricionista (llenando la plantilla, a
 * mano o desde su PDF) o la que calcula la IA; luego ubica los suplementos y las
 * comidas por fuera. Al guardarla, la minuta queda fija.
 */
@Component({
  selector: 'app-cargar-minuta',
  templateUrl: './cargar-minuta.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    RouterLink,
    ButtonModule,
    InputTextModule,
    MessageModule,
    TextareaModule,
    EditorMinuta,
    TablaMinuta,
    EtiquetaSuplemento,
    TomasSuplemento,
    PeriodoPlan,
  ],
})
export class CargarMinuta implements OnInit {
  private minutas = inject(MinutaService);
  private procesos = inject(ProcesoService);
  private suplementos = inject(SuplementoService);
  private router = inject(Router);
  private route = inject(ActivatedRoute);

  protected tiemposComida = TIEMPOS_COMIDA;
  protected opcionesPorFuera = OPCIONES_POR_FUERA;
  protected clasesChip = clasesChip;
  protected porcionesDe = porcionesDe;
  protected num = formatearNumero;
  protected claseOpcion =
    'w-full text-left flex flex-col gap-1 rounded-xl border border-gray-200 dark:border-dark-700 bg-white dark:bg-dark-800 px-4 py-4 hover:border-guerrero-red focus-visible:outline-2 focus-visible:outline-guerrero-red';

  protected paso = signal<Paso>('origen');
  protected numeroPaso = computed(() => PASOS.indexOf(this.paso()) + 1);
  protected totalPasos = PASOS.length;
  protected trabajando = signal(false);
  protected error = signal('');
  protected aviso = signal('');
  protected guardada = signal(false);

  // ── La minuta ─────────────────────────────────────────────────────
  protected origen = signal<OrigenMinuta | null>(null);
  protected porciones = signal<PorcionesMinuta>({});
  protected kcal = signal<number | null>(null);
  protected proteina = signal<number | null>(null);
  protected menuEjemplo = signal<MinutaPayload['menu_ejemplo']>({});
  protected recomendaciones = signal('');
  protected explicacion = signal('');
  /** PDF o foto de lo que dio la nutricionista, como respaldo. */
  protected original = signal<File | null>(null);
  protected leidoDelPdf = signal(false);
  protected tiempos = computed(() => tiemposDe(this.porciones()));
  protected minutaLista = computed(() => this.tiempos().length > 0);

  // ── Suplementos y comidas por fuera ───────────────────────────────
  protected enMinuta = signal<SuplementoEnMinuta[]>([]);
  protected sinSuplementos = computed(() => this.enMinuta().every((s) => !s.existente));
  protected porFuera = signal<Partial<Record<TiempoComida, ReglaPorFuera>>>({});

  /** El proceso recién creado en el onboarding (puede ser uno programado). */
  private proceso = Number(this.route.snapshot.queryParamMap.get('proceso')) || undefined;

  // ── Periodo de un plan nuevo ──────────────────────────────────────
  /** Ya había un plan: este lo reemplaza y puede traer su propio periodo. */
  protected esPlanNuevo = computed(() => !this.proceso && this.minutas.vigente() !== null);
  /** Lo que se sugiere: el mismo tiempo que ya tiene el proceso (hasta su control). */
  protected sugerida = computed(() => {
    const fin = this.procesos.vigente()?.fecha_fin_plan;
    return fin && fin > hoyISO()
      ? { titulo: `Hasta mi control (${formatearFecha(fin)})`, fecha: fin }
      : null;
  });
  /** undefined: falta elegir; null: sin definir. */
  protected periodo = signal<string | null | undefined>(undefined);
  protected puedeGuardar = computed(() => !this.esPlanNuevo() || this.periodo() !== undefined);

  ngOnInit(): void {
    if (this.minutas.minutas() === null) this.minutas.cargar().subscribe();
    const pedido = this.route.snapshot.queryParamMap.get('origen');
    if (pedido === 'ia' || pedido === 'nutricionista') this.elegirOrigen(pedido);
  }

  // ── Paso 1: quién arma el plan ────────────────────────────────────
  protected elegirOrigen(origen: OrigenMinuta): void {
    this.origen.set(origen);
    this.error.set('');
    this.paso.set('minuta');
    if (origen === 'ia') this.calcular();
  }

  // ── Paso 2a: la plantilla de la nutricionista ─────────────────────
  private archivoElegido(evento: Event): File | null {
    const entrada = evento.target as HTMLInputElement;
    const archivo = entrada.files?.[0] ?? null;
    entrada.value = '';
    if (archivo && archivo.size > MAX_BYTES) {
      this.error.set('El archivo pesa más de 10 MB.');
      return null;
    }
    return archivo;
  }

  /** Un PDF se lee para llenar la tabla; una foto queda adjunta para llenarla a mano. */
  protected subirOriginal(evento: Event): void {
    const archivo = this.archivoElegido(evento);
    if (!archivo) return;
    this.aviso.set('');
    this.leidoDelPdf.set(false);
    if (archivo.type === 'application/pdf') this.llenarDesdePdf(archivo);
    else this.original.set(archivo);
  }

  private llenarDesdePdf(archivo: File): void {
    this.trabajando.set(true);
    this.error.set('');
    this.aviso.set('');
    this.minutas.leerPdf(archivo).subscribe({
      next: (leido) => {
        this.porciones.set(leido.porciones);
        this.kcal.set(leido.kcal);
        this.proteina.set(leido.proteina_g_kg);
        this.menuEjemplo.set(leido.menu_ejemplo);
        this.recomendaciones.set(leido.recomendaciones);
        this.original.set(archivo);
        this.leidoDelPdf.set(true);
        this.trabajando.set(false);
      },
      error: (err) => {
        this.original.set(archivo);
        this.aviso.set(
          mensajeError(err, 'No reconocemos ese PDF.') +
            ' Lo dejamos adjunto: llena la tabla con lo que dice.',
        );
        this.trabajando.set(false);
      },
    });
  }

  protected numero(evento: Event): number | null {
    const valor = (evento.target as HTMLInputElement).valueAsNumber;
    return Number.isFinite(valor) && valor > 0 ? valor : null;
  }

  // ── Paso 2b: la que calcula la IA ─────────────────────────────────
  protected calcular(): void {
    this.trabajando.set(true);
    this.error.set('');
    this.minutas.calcular(this.proceso).subscribe({
      next: (calculada) => {
        this.porciones.set(calculada.porciones);
        this.kcal.set(calculada.kcal);
        this.proteina.set(calculada.proteina_g_kg);
        this.recomendaciones.set(calculada.recomendaciones);
        this.explicacion.set(calculada.explicacion);
        this.trabajando.set(false);
      },
      error: (err) => {
        this.error.set(mensajeError(err, 'No pudimos calcular tu plan. Intenta de nuevo.'));
        this.trabajando.set(false);
      },
    });
  }

  protected irASuplementos(): void {
    this.trabajando.set(true);
    this.error.set('');
    this.suplementos.cargar().subscribe({
      next: () => {
        this.enMinuta.set(this.suplementosIniciales());
        this.trabajando.set(false);
        this.paso.set('suplementos');
      },
      error: (err) => {
        this.error.set(mensajeError(err, 'No pudimos cargar tus suplementos.'));
        this.trabajando.set(false);
      },
    });
  }

  private suplementosIniciales(): SuplementoEnMinuta[] {
    const activos = this.suplementos.activos();
    if (activos.length) {
      return activos.map((s) => ({
        existente: s,
        tipo: s.tipo,
        nombre: s.nombre || s.tipo_nombre,
        activo: true,
        etiqueta: etiquetaDe(s),
        tomas: s.tomas.filter((t) => t.tiempo === 'otro' || this.tiempos().includes(t.tiempo)),
      }));
    }
    return [
      {
        existente: null,
        tipo: 'proteina',
        nombre: '',
        activo: false,
        etiqueta: etiquetaVacia(),
        tomas: [],
      },
    ];
  }

  // ── Paso 3: suplementos ───────────────────────────────────────────
  /** Todos los activos con la etiqueta bien escrita y la porción completa repartida. */
  protected suplementosValidos = computed(() =>
    this.enMinuta()
      .filter((s) => s.activo)
      .every(
        (s) =>
          Object.keys(erroresEtiqueta(s.etiqueta)).length === 0 &&
          scoopsFaltantes(s.tomas, s.etiqueta.scoops) === 0,
      ),
  );

  protected actualizar(i: number, cambios: Partial<SuplementoEnMinuta>): void {
    this.enMinuta.update((lista) => lista.map((s, j) => (j === i ? { ...s, ...cambios } : s)));
  }

  protected alternarActivo(i: number): void {
    this.actualizar(i, { activo: !this.enMinuta()[i].activo });
  }

  protected irAPorFuera(): void {
    this.trabajando.set(true);
    this.minutas.preferencias().subscribe({
      next: (p) => {
        this.porFuera.set(p.por_fuera);
        this.trabajando.set(false);
        this.paso.set('fuera');
      },
      error: () => {
        this.trabajando.set(false);
        this.paso.set('fuera');
      },
    });
  }

  // ── Paso 4: por fuera y guardar ───────────────────────────────────
  protected reglaDe(tiempo: TiempoComida): ReglaPorFuera | null {
    return this.porFuera()[tiempo] ?? null;
  }

  protected elegirPorFuera(tiempo: TiempoComida, regla: ReglaPorFuera | null): void {
    this.porFuera.update((actual) => {
      const siguiente = { ...actual };
      if (regla) siguiente[tiempo] = regla;
      else delete siguiente[tiempo];
      return siguiente;
    });
  }

  protected volver(): void {
    const anterior = PASOS[PASOS.indexOf(this.paso()) - 1];
    this.error.set('');
    if (anterior) this.paso.set(anterior);
  }

  protected guardar(): void {
    const origen = this.origen();
    if (!origen) return;
    this.trabajando.set(true);
    this.error.set('');
    const minuta: MinutaPayload = {
      origen,
      proceso: this.proceso,
      porciones: this.porciones(),
      kcal: this.kcal(),
      proteina_g_kg: this.proteina(),
      menu_ejemplo: this.menuEjemplo(),
      recomendaciones: this.recomendaciones().trim(),
      // Solo si el periodo cambia: la fecha de control no se toca porque sí.
      ...(this.esPlanNuevo() && this.periodo() !== (this.procesos.vigente()?.fecha_fin_plan ?? null)
        ? { fecha_fin_plan: this.periodo() }
        : {}),
    };
    this.minutas.guardar(minuta, origen === 'nutricionista' ? this.original() : null).subscribe({
      next: () => {
        this.guardada.set(true);
        this.guardarLoDemas();
      },
      error: (err) => {
        this.error.set(mensajeError(err, 'No pudimos guardar tu plan.'));
        this.trabajando.set(false);
      },
    });
  }

  /** La minuta ya quedó; los suplementos y las comidas por fuera se guardan después. */
  private guardarLoDemas(): void {
    const pasos: Observable<unknown>[] = this.enMinuta()
      .filter((s) => s.activo)
      .map((s) => {
        const ubicacion = { ...payloadEtiqueta(s.etiqueta), tomas: s.tomas };
        if (s.existente) {
          return defer(() => this.suplementos.actualizar(s.existente!.id, ubicacion));
        }
        return defer(() =>
          this.suplementos.crear({
            tipo: s.tipo,
            nombre: s.nombre.trim(),
            duracion_dias: tipoSuplemento(s.tipo).duracionUsual,
            duracion_confirmada: false,
            porciones_envase: null,
            ...ubicacion,
          }),
        );
      });
    pasos.push(defer(() => this.minutas.guardarPreferencias({ por_fuera: this.porFuera() })));
    concat(...pasos)
      .pipe(toArray())
      .subscribe({
        next: () => this.router.navigate(['/nutricion']),
        error: (err) => {
          this.trabajando.set(false);
          this.error.set(
            mensajeError(err, 'Tu plan quedó guardado, pero no pudimos ubicar tus suplementos.') +
              ' Puedes ajustarlo en Progreso › Agenda.',
          );
        },
      });
  }
}
