import {
  Component,
  ChangeDetectionStrategy,
  OnInit,
  computed,
  inject,
  signal,
} from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Observable } from 'rxjs';
import { ButtonModule } from 'primeng/button';
import { DialogModule } from 'primeng/dialog';
import { InputTextModule } from 'primeng/inputtext';
import { MessageModule } from 'primeng/message';
import { SelectButtonModule } from 'primeng/selectbutton';

import { SuplementoService } from '../../core/services/suplemento';
import { ProcesoService } from '../../core/services/proceso';
import { Recordatorio } from '../../core/models/agenda.model';
import {
  Suplemento,
  SuplementoPayload,
  TipoSuplemento,
} from '../../core/models/suplemento.model';
import {
  DURACIONES_SUPLEMENTO,
  EXTENSIONES_SUPLEMENTO,
  TIPOS_SUPLEMENTO,
} from '../../core/constants/proceso';
import { DecimalInput } from '../../shared/decimal-input';
import { cuandoEs, formatearFecha, formatearNumero } from '../../shared/fechas';
import { clasesChip } from '../../shared/chip';
import { mensajeError } from '../../shared/errores';
import {
  avanceSuplemento,
  duracionEnPalabras,
  nombreSuplemento,
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
@Component({
  selector: 'app-suplementos',
  templateUrl: './suplementos.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    ReactiveFormsModule,
    ButtonModule,
    DialogModule,
    InputTextModule,
    MessageModule,
    SelectButtonModule,
    DecimalInput,
  ],
})
export class Suplementos implements OnInit {
  private fb = inject(NonNullableFormBuilder);
  protected servicio = inject(SuplementoService);
  private procesos = inject(ProcesoService);

  protected tipos = TIPOS_SUPLEMENTO;
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
    duracion_dias: this.fb.control<number | null>(90),
    duracion_confirmada: this.fb.control(false),
    porciones_envase: this.fb.control<number | null>(null, [
      Validators.min(1),
      Validators.max(500),
      Validators.pattern(/^\d+$/),
    ]),
    porciones_dia: this.fb.control<number | null>(1, [
      Validators.required,
      Validators.min(0.5),
      Validators.max(10),
    ]),
  });

  ngOnInit(): void {
    this.servicio.cargar().subscribe({
      error: (err) => this.error.set(mensajeError(err, 'No pudimos cargar tus suplementos.')),
    });
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
    } else if (s) {
      this.cargarFormulario(
        modo === 'reemplazar'
          ? { tipo: s.tipo, ...this.porDefecto(s.tipo), duracion_confirmada: true }
          : s,
      );
    }
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
      porciones_dia: 1,
    };
  }

  private cargarFormulario(v: SuplementoPayload & { tipo: TipoSuplemento }): void {
    this.form.reset({
      tipo: v.tipo,
      nombre: v.nombre,
      duracion_dias: v.duracion_dias,
      duracion_confirmada: v.duracion_confirmada,
      porciones_envase: v.porciones_envase,
      porciones_dia: Number(v.porciones_dia),
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
      duracion_dias: v.duracion_dias,
      duracion_confirmada: v.duracion_confirmada,
      porciones_envase: v.porciones_envase,
      porciones_dia: v.porciones_dia ?? 1,
    };
  }

  protected guardar(): void {
    const modo = this.modo();
    const s = this.actual();
    if (this.form.invalid) return;
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
