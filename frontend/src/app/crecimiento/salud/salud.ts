import {
  ChangeDetectionStrategy,
  Component,
  OnInit,
  computed,
  inject,
  input,
  signal,
} from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ButtonModule } from 'primeng/button';
import { InputTextModule } from 'primeng/inputtext';
import { MessageModule } from 'primeng/message';

import { ProyectoCrecimiento } from '../../core/models/crecimiento.model';
import { EstadoSalud, TomaSalud } from '../../core/models/salud.model';
import { CrecimientoService } from '../../core/services/crecimiento';
import { SaludService } from '../../core/services/salud';
import { clasesChip } from '../../shared/chip';
import { mensajeError } from '../../shared/errores';
import { PlanesSuplementos } from './planes-suplementos';
import { diasEntre, formatearFecha, hoyISO, sumarDias } from '../../shared/fechas';

const NIVELES = [1, 2, 3, 4, 5];

/**
 * Salud: el protocolo Fadiman de microdosis (calendario de 4 días, ciclo y descanso, y lo que la persona anota) y
 * el control de otros suplementos. Una sola pantalla para los dos tipos de proyecto (`fadiman` y
 * `otros_suplementos`). La app no sugiere sustancias ni dosis: lo escribe la persona.
 */
@Component({
  selector: 'app-salud',
  templateUrl: './salud.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [ReactiveFormsModule, ButtonModule, InputTextModule, MessageModule, PlanesSuplementos],
})
export class Salud implements OnInit {
  readonly proyecto = input.required<ProyectoCrecimiento>();

  private servicio = inject(SaludService);
  private crecimiento = inject(CrecimientoService);
  private fb = inject(FormBuilder);

  protected niveles = NIVELES;
  protected clasesChip = clasesChip;
  protected fecha = (iso: string) => formatearFecha(iso, 'dia');

  protected estado = signal<EstadoSalud | null>(null);
  protected cargando = signal(true);
  protected guardando = signal(false);
  protected error = signal('');
  protected aviso = signal('');
  protected editandoAjustes = signal(false);
  protected animo = signal<number | null>(null);
  protected energia = signal<number | null>(null);

  protected esProtocolo = computed(() => this.proyecto().tipo === 'fadiman');
  protected sinEmpezar = computed(() => !this.estado()?.ajustes?.inicio);
  protected dosis = computed(() => (this.estado()?.tomas ?? []).filter((t) => t.clase === 'dosis'));
  protected observaciones = computed(() =>
    (this.estado()?.tomas ?? []).filter((t) => t.clase === 'observacion'),
  );
  protected avance = computed(() => {
    const c = this.estado()?.primer_ciclo;
    return c && c.previstas ? Math.round((100 * c.hechas) / c.previstas) : 0;
  });

  protected ajustes = this.fb.nonNullable.group({
    sustancia: ['', [Validators.maxLength(60)]],
    dosis: ['', [Validators.maxLength(40)]],
    // Solo para la pantalla: si ya empezó, el día 1 es uno pasado; si no, uno de hoy en adelante.
    ya_empezo: [false],
    inicio: [hoyISO(), Validators.required],
    semanas_ciclo: [4, [Validators.required, Validators.min(4), Validators.max(8)]],
    semanas_descanso: [2, [Validators.required, Validators.min(2), Validators.max(4)]],
    avisar: [true],
    hora_aviso: ['08:00', Validators.required],
  });
  private valores = toSignal(this.ajustes.valueChanges, {
    initialValue: this.ajustes.getRawValue(),
  });
  protected hoy = hoyISO();
  protected desdeMin = computed(() => sumarDias(this.hoy, this.valores().ya_empezo ? -120 : 0));
  protected desdeMax = computed(() =>
    this.valores().ya_empezo ? this.hoy : sumarDias(this.hoy, 30),
  );
  /** Dónde cae hoy según lo que escribió (el servidor calcula lo mismo al guardar). */
  protected vista = computed(() => {
    const v = this.valores();
    if (!v.inicio) return '';
    const corridos = diasEntre(v.inicio, this.hoy);
    if (corridos < 0)
      return `Empiezas en ${-corridos} ${corridos === -1 ? 'día' : 'días'}: ese día es tu día 1.`;
    const ciclo = (v.semanas_ciclo ?? 4) * 7;
    const pos = corridos % (ciclo + (v.semanas_descanso ?? 2) * 7);
    if (pos >= ciclo)
      return `Hoy estarías en descanso, semana ${Math.floor((pos - ciclo) / 7) + 1}.`;
    return `Hoy sería el día ${(pos % 4) + 1} del ciclo, semana ${Math.floor(pos / 7) + 1} de ${v.semanas_ciclo}.`;
  });
  protected toma = this.fb.nonNullable.group({
    nombre: ['', [Validators.required, Validators.maxLength(60)]],
    cantidad: ['', [Validators.required, Validators.maxLength(40)]],
    nota: ['', [Validators.maxLength(300)]],
  });
  protected observacion = this.fb.nonNullable.group({ nota: ['', [Validators.maxLength(300)]] });

  ngOnInit(): void {
    this.servicio.cargar(this.proyecto().id).subscribe({
      next: (e) => this.recibir(e),
      error: (e) => {
        this.cargando.set(false);
        this.error.set(mensajeError(e, 'No pudimos cargar esta sección.'));
      },
    });
  }

  protected recibir(e: EstadoSalud): void {
    this.estado.set(e);
    this.cargando.set(false);
    this.error.set('');
    const a = e.ajustes;
    if (a) {
      this.ajustes.patchValue({
        sustancia: a.sustancia,
        dosis: a.dosis,
        ya_empezo: !!a.inicio && a.inicio <= this.hoy,
        inicio: a.inicio || this.hoy,
        semanas_ciclo: a.semanas_ciclo,
        semanas_descanso: a.semanas_descanso,
        avisar: a.avisar,
        hora_aviso: a.hora_aviso,
      });
    }
  }

  private fallo(e: unknown, respaldo: string): void {
    this.guardando.set(false);
    this.error.set(mensajeError(e, respaldo));
  }

  protected guardarAjustes(): void {
    if (this.ajustes.invalid) return;
    this.guardando.set(true);
    this.crecimiento
      .actualizarProyecto(this.proyecto().id, { datos: this.datosAjustes() })
      .subscribe({
        next: () => {
          this.editandoAjustes.set(false);
          this.aviso.set('Guardado.');
          this.servicio.cargar(this.proyecto().id).subscribe({
            next: (e) => {
              this.guardando.set(false);
              this.recibir(e);
            },
            error: (e) => this.fallo(e, 'No pudimos cargar esta sección.'),
          });
        },
        error: (e) => this.fallo(e, 'No pudimos guardar tus ajustes.'),
      });
  }

  private datosAjustes(): Record<string, unknown> {
    const { ya_empezo, ...datos } = this.ajustes.getRawValue();
    void ya_empezo;
    return datos;
  }

  /** La toma del protocolo usa la sustancia y la cantidad de los ajustes. */
  protected anotarToma(): void {
    this.enviar({}, 'Toma anotada.');
  }

  protected anotarObservacion(): void {
    this.enviar(
      {
        clase: 'observacion',
        animo: this.animo(),
        energia: this.energia(),
        nota: this.observacion.getRawValue().nota,
      },
      'Anotado cómo estás.',
      () => {
        this.animo.set(null);
        this.energia.set(null);
        this.observacion.reset();
      },
    );
  }

  protected anotarSuplemento(): void {
    if (this.toma.invalid) return;
    this.enviar(this.toma.getRawValue(), 'Toma anotada.', () => this.toma.reset());
  }

  protected usarFrecuente(f: { nombre: string; cantidad: string }): void {
    this.toma.patchValue(f);
  }

  private enviar(
    cuerpo: Parameters<SaludService['anotar']>[1],
    mensaje: string,
    despues?: () => void,
  ): void {
    this.guardando.set(true);
    this.aviso.set('');
    this.servicio.anotar(this.proyecto().id, cuerpo).subscribe({
      next: (e) => {
        this.guardando.set(false);
        this.recibir(e);
        this.aviso.set(mensaje);
        despues?.();
      },
      error: (e) => this.fallo(e, 'No pudimos anotarlo.'),
    });
  }

  protected borrar(t: TomaSalud): void {
    this.servicio.borrar(this.proyecto().id, t.id).subscribe({
      next: (e) => this.recibir(e),
      error: (e) => this.fallo(e, 'No pudimos borrarlo.'),
    });
  }
}
