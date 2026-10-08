import {
  Component,
  ChangeDetectionStrategy,
  inject,
  signal,
  computed,
  OnInit,
} from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { NonNullableFormBuilder } from '@angular/forms';
import { Observable, map } from 'rxjs';
import { ButtonModule } from 'primeng/button';
import { ChartModule } from 'primeng/chart';
import { DialogModule } from 'primeng/dialog';
import { MessageModule } from 'primeng/message';
import { ProgressSpinnerModule } from 'primeng/progressspinner';

import { AuthService } from '../../core/services/auth';
import { FotoService, FotosPorPose } from '../../core/services/foto';
import { MedicionService } from '../../core/services/medicion';
import { NotificacionService } from '../../core/services/notificaciones';
import { ProcesoService } from '../../core/services/proceso';
import { ThemeService } from '../../core/services/theme';
import { FotoProgreso, Medicion, Pose } from '../../core/models/proceso.model';
import { POSES } from '../../core/constants/proceso';
import {
  MedicionForm,
  crearMedicionForm,
  leerMedicion,
} from '../../shared/medicion-form/medicion-form';
import { Foto } from '../../shared/foto/foto';
import { SelectorFotos } from '../../shared/selector-fotos/selector-fotos';
import { CompararFotos, FotoAmpliada } from './comparar-fotos/comparar-fotos';
import { formatearFecha, formatearNumero } from '../../shared/fechas';
import { mensajeError } from '../../shared/errores';

type ModoRegistro = 'nueva' | 'inicial';

/** Historial de mediciones corporales y registro de nuevas (incluida la inicial del proceso). */
@Component({
  selector: 'app-medidas',
  templateUrl: './medidas.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    ButtonModule,
    ChartModule,
    DialogModule,
    MessageModule,
    ProgressSpinnerModule,
    MedicionForm,
    Foto,
    SelectorFotos,
    CompararFotos,
  ],
})
export class Medidas implements OnInit {
  private fb = inject(NonNullableFormBuilder);
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private auth = inject(AuthService);
  private servicio = inject(MedicionService);
  private fotos = inject(FotoService);
  private notificaciones = inject(NotificacionService);
  private theme = inject(ThemeService);
  protected procesos = inject(ProcesoService);

  protected mediciones = signal<Medicion[]>([]);
  protected cargando = signal(true);
  protected modo = signal<ModoRegistro | null>(null);
  protected guardando = signal(false);
  protected error = signal('');
  protected confirmarEliminar = signal<number | null>(null);
  protected formatearFecha = formatearFecha;
  protected poses = POSES;

  /** Fotos elegidas en el diálogo de registro; se suben al guardar la medición. */
  protected fotosNuevas = signal<FotosPorPose>({});

  /** Medición cuyas fotos se están viendo o completando. */
  protected verFotosDe = signal<number | null>(null);
  protected fotosAgregar = signal<FotosPorPose>({});
  protected hayFotosAgregar = computed(() => Object.keys(this.fotosAgregar()).length > 0);
  protected subiendoFotos = signal(false);
  protected errorFotos = signal('');
  protected confirmarEliminarFoto = signal<number | null>(null);
  protected ampliada = signal<FotoAmpliada | null>(null);
  protected num = formatearNumero;

  protected form = crearMedicionForm(this.fb, this.auth.usuario()?.estatura ?? null);

  protected ultima = computed(() => this.mediciones()[0] ?? null);

  protected medicionFotos = computed(
    () => this.mediciones().find((m) => m.id === this.verFotosDe()) ?? null,
  );

  /** Poses que aún se pueden agregar a la medición abierta. */
  protected posesLibres = computed<Pose[]>(() => {
    const m = this.medicionFotos();
    if (!m?.admite_fotos) return [];
    return POSES.map((p) => p.value).filter((pose) => !m.fotos.some((f) => f.pose === pose));
  });

  /** La medición inicial todavía admite fotos y le faltan: se invita a completarlas. */
  protected inicialSinFotos = computed(() => {
    const inicial = this.mediciones().find((m) => m.es_inicial);
    return inicial?.admite_fotos && inicial.fotos.length < POSES.length ? inicial : null;
  });

  /** Cambio de peso respecto a la medición inicial del proceso en curso. */
  protected cambio = computed(() => {
    const inicial = this.procesos.actual()?.medicion_inicial;
    const ultima = this.ultima();
    if (!inicial || !ultima || inicial.id === ultima.id) return null;
    return Math.round((ultima.peso_kg - inicial.peso_kg) * 10) / 10;
  });

  /** Verde si el cambio va en la dirección del objetivo del proceso. */
  protected tonoCambio = computed(() => {
    const c = this.cambio();
    const p = this.procesos.actual();
    if (!c || !p) return 'text-gray-900 dark:text-white';
    const sube = p.fase === 'volumen' || (p.fase === '' && p.objetivo === 'ganar_musculo');
    const baja = p.fase === 'definicion' || (p.fase === '' && p.objetivo === 'bajar_peso');
    if ((sube && c > 0) || (baja && c < 0)) return 'text-green-700 dark:text-green-400';
    if ((sube && c < 0) || (baja && c > 0)) return 'text-amber-700 dark:text-amber-400';
    return 'text-gray-900 dark:text-white';
  });

  protected chartData = computed(() => {
    const serie = [...this.mediciones()].reverse();
    if (serie.length < 2) return null;
    return {
      labels: serie.map((m) => formatearFecha(m.fecha, 'grafica')),
      datasets: [
        {
          label: 'Peso (kg)',
          data: serie.map((m) => m.peso_kg),
          borderColor: '#C0392B',
          backgroundColor: 'rgba(192,57,43,0.08)',
          pointBackgroundColor: serie.map((m) => (m.es_inicial ? '#D4AF37' : '#C0392B')),
          pointRadius: serie.map((m) => (m.es_inicial ? 6 : 4)),
          tension: 0.3,
          fill: true,
        },
      ],
    };
  });

  protected chartOptions = computed(() => {
    const texto = this.theme.isDark() ? '#9ca3af' : '#6b7280';
    const grilla = this.theme.isDark() ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)';
    return {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: { label: (ctx: { raw: number }) => ` ${formatearNumero(ctx.raw)} kg` },
        },
      },
      scales: {
        x: { ticks: { color: texto, font: { size: 11 } }, grid: { color: grilla } },
        y: {
          ticks: {
            color: texto,
            font: { size: 11 },
            callback: (v: number) => `${formatearNumero(v)} kg`,
          },
          grid: { color: grilla },
        },
      },
    };
  });

  ngOnInit(): void {
    this.cargar();
    this.procesos.cargar().subscribe(() => {
      const pideInicial = this.route.snapshot.queryParamMap.get('medicion') === 'inicial';
      if (pideInicial && this.procesos.medicionInicialPendiente()) this.abrir('inicial');
    });
  }

  private cargar(): void {
    this.servicio.listar().subscribe({
      next: (data) => {
        this.mediciones.set(data);
        this.cargando.set(false);
      },
      error: () => this.cargando.set(false),
    });
  }

  protected abrir(modo: ModoRegistro): void {
    this.error.set('');
    this.fotosNuevas.set({});
    this.form.reset();
    this.form.controls.talla_cm.setValue(
      this.ultima()?.talla_cm ?? this.auth.usuario()?.estatura ?? null,
    );
    this.modo.set(modo);
  }

  protected cerrar(): void {
    this.modo.set(null);
    if (this.route.snapshot.queryParamMap.has('medicion')) {
      this.router.navigate([], { queryParams: {}, replaceUrl: true });
    }
  }

  protected guardar(): void {
    const modo = this.modo();
    if (!modo || this.form.invalid) return;
    this.guardando.set(true);
    this.error.set('');
    const actual = this.procesos.actual();
    const medicionId: Observable<number> =
      modo === 'inicial' && actual
        ? this.procesos
            .registrarMedicionInicial(actual.id, leerMedicion(this.form, false))
            .pipe(map((p) => p.medicion_inicial!.id))
        : this.servicio.registrar(leerMedicion(this.form, true)).pipe(map((m) => m.id));
    medicionId.subscribe({
      next: (id) => {
        this.notificaciones.dismiss();
        this.subirFotosNuevas(id);
      },
      error: (err) => {
        this.error.set(mensajeError(err, 'No pudimos guardar la medición.'));
        this.guardando.set(false);
      },
    });
  }

  /** La medición ya quedó guardada: si las fotos fallan se avisa y se pueden agregar desde la lista. */
  private subirFotosNuevas(medicionId: number): void {
    const terminar = (error = '') => {
      this.guardando.set(false);
      this.cerrar();
      this.error.set(error);
      this.cargar();
    };
    this.fotos.subirVarias(medicionId, this.fotosNuevas()).subscribe({
      next: () => terminar(),
      error: (err) =>
        terminar(
          mensajeError(
            err,
            'La medición quedó guardada, pero no pudimos subir las fotos. Agrégalas desde la lista.',
          ),
        ),
    });
  }

  protected abrirFotos(m: Medicion): void {
    this.errorFotos.set('');
    this.fotosAgregar.set({});
    this.confirmarEliminarFoto.set(null);
    this.verFotosDe.set(m.id);
  }

  protected cerrarFotos(): void {
    this.verFotosDe.set(null);
  }

  protected subirFotos(): void {
    const m = this.medicionFotos();
    if (!m) return;
    this.subiendoFotos.set(true);
    this.errorFotos.set('');
    this.fotos.subirVarias(m.id, this.fotosAgregar()).subscribe({
      next: (nuevas) => {
        this.subiendoFotos.set(false);
        this.fotosAgregar.set({});
        this.agregarFotos(m.id, nuevas);
      },
      error: (err) => {
        this.subiendoFotos.set(false);
        this.errorFotos.set(mensajeError(err, 'No pudimos subir las fotos.'));
        this.cargar();
      },
    });
  }

  protected eliminarFoto(foto: FotoProgreso): void {
    const m = this.medicionFotos();
    if (!m) return;
    this.fotos.eliminar(foto.id).subscribe({
      next: () => {
        this.confirmarEliminarFoto.set(null);
        this.mediciones.update((lista) =>
          lista.map((x) =>
            x.id === m.id ? { ...x, fotos: x.fotos.filter((f) => f.id !== foto.id) } : x,
          ),
        );
      },
      error: (err) => {
        this.confirmarEliminarFoto.set(null);
        this.errorFotos.set(mensajeError(err, 'No pudimos eliminar la foto.'));
      },
    });
  }

  private agregarFotos(medicionId: number, nuevas: FotoProgreso[]): void {
    const orden = (f: FotoProgreso) => POSES.findIndex((p) => p.value === f.pose);
    this.mediciones.update((lista) =>
      lista.map((x) =>
        x.id === medicionId
          ? { ...x, fotos: [...x.fotos, ...nuevas].sort((a, b) => orden(a) - orden(b)) }
          : x,
      ),
    );
  }

  protected nombrePose(pose: Pose): string {
    return POSES.find((p) => p.value === pose)?.label ?? pose;
  }

  protected eliminar(m: Medicion): void {
    this.servicio.eliminar(m.id).subscribe({
      next: () => {
        this.confirmarEliminar.set(null);
        this.mediciones.update((lista) => lista.filter((x) => x.id !== m.id));
      },
      error: (err) => {
        this.confirmarEliminar.set(null);
        this.error.set(mensajeError(err, 'No pudimos eliminar la medición.'));
      },
    });
  }
}
