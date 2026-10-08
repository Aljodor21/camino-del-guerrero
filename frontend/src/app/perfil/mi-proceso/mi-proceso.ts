import {
  Component,
  ChangeDetectionStrategy,
  inject,
  signal,
  computed,
  OnInit,
} from '@angular/core';
import { RouterLink } from '@angular/router';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ButtonModule } from 'primeng/button';
import { InputTextModule } from 'primeng/inputtext';
import { TextareaModule } from 'primeng/textarea';
import { ToggleSwitchModule } from 'primeng/toggleswitch';
import { MessageModule } from 'primeng/message';

import { ProcesoService } from '../../core/services/proceso';
import { Proceso } from '../../core/models/proceso.model';
import { CONFIG_ENTRENAMIENTO_INICIAL } from '../../core/constants/proceso';
import {
  EntrenamientoForm,
  crearEntrenamientoForm,
} from '../../shared/entrenamiento-form/entrenamiento-form';
import { formatearFecha, formatearNumero, hoyISO, sumarDias } from '../../shared/fechas';
import { avanceProceso } from '../../shared/avance-proceso';
import { mensajeError } from '../../shared/errores';
import { DecimalInput } from '../../shared/decimal-input';

/** El proceso vigente: datos de inicio (bloqueados), lo editable, el programado y el historial. */
@Component({
  selector: 'app-mi-proceso',
  templateUrl: './mi-proceso.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    DecimalInput,
    RouterLink,
    ReactiveFormsModule,
    ButtonModule,
    InputTextModule,
    TextareaModule,
    ToggleSwitchModule,
    MessageModule,
    EntrenamientoForm,
  ],
})
export class MiProceso implements OnInit {
  private fb = inject(NonNullableFormBuilder);
  protected procesos = inject(ProcesoService);

  protected proceso = this.procesos.vigente;
  protected historial = signal<Proceso[]>([]);
  protected guardando = signal(false);
  protected cancelando = signal(false);
  protected confirmandoCancelacion = signal(false);
  protected error = signal('');
  protected guardado = signal(false);
  protected formatearFecha = formatearFecha;
  protected num = formatearNumero;

  protected form = this.fb.group({
    peso_objetivo: this.fb.control<number | null>(null, [Validators.min(20), Validators.max(300)]),
    fecha_fin_plan: this.fb.control(''),
    notas: this.fb.control(''),
    incluye_alimentacion: this.fb.control(true),
    incluye_entrenamiento: this.fb.control(false),
  });
  protected entrenamientoForm = crearEntrenamientoForm(this.fb);

  protected avance = computed(() => {
    const p = this.proceso();
    return p ? avanceProceso(p) : null;
  });

  /** El fin del plan va después del inicio y, si se cambia, no puede quedar en el pasado. */
  protected minimoFinPlan = computed(() => {
    const p = this.proceso();
    if (!p) return hoyISO();
    const despuesDelInicio = sumarDias(p.fecha_inicio, 1);
    return despuesDelInicio > hoyISO() ? despuesDelInicio : hoyISO();
  });

  protected anteriores = computed(() => {
    const vigentes = [this.procesos.actual()?.id, this.procesos.programado()?.id];
    return this.historial().filter((p) => !vigentes.includes(p.id));
  });

  ngOnInit(): void {
    this.procesos.cargar().subscribe(() => this.llenarFormulario());
    this.procesos.historial().subscribe((h) => this.historial.set(h));
  }

  private llenarFormulario(): void {
    const p = this.proceso();
    if (!p) return;
    this.form.reset({
      peso_objetivo: p.peso_objetivo,
      fecha_fin_plan: p.fecha_fin_plan ?? '',
      notas: p.notas,
      incluye_alimentacion: p.incluye_alimentacion,
      incluye_entrenamiento: p.incluye_entrenamiento,
    });
    this.entrenamientoForm.reset(p.entrenamiento ?? CONFIG_ENTRENAMIENTO_INICIAL);
  }

  protected sinModulos(): boolean {
    const { incluye_alimentacion, incluye_entrenamiento } = this.form.getRawValue();
    return !incluye_alimentacion && !incluye_entrenamiento;
  }

  protected guardar(): void {
    const p = this.proceso();
    if (!p || this.form.invalid || this.sinModulos()) return;
    const v = this.form.getRawValue();
    this.guardando.set(true);
    this.error.set('');
    this.guardado.set(false);
    this.procesos
      .actualizar(p.id, {
        ...v,
        fecha_fin_plan: v.fecha_fin_plan || null,
        notas: v.notas.trim(),
        ...(v.incluye_entrenamiento ? { entrenamiento: this.entrenamientoForm.getRawValue() } : {}),
      })
      .subscribe({
        next: () => {
          this.guardando.set(false);
          this.guardado.set(true);
          this.form.markAsPristine();
          this.entrenamientoForm.markAsPristine();
          setTimeout(() => this.guardado.set(false), 3000);
        },
        error: (err) => {
          this.error.set(mensajeError(err, 'No pudimos guardar los cambios.'));
          this.guardando.set(false);
        },
      });
  }

  protected cancelarProgramado(): void {
    const programado = this.procesos.programado();
    if (!programado) return;
    this.cancelando.set(true);
    this.procesos.cancelarProgramado(programado.id).subscribe({
      next: () =>
        this.procesos.refrescar().subscribe(() => {
          this.cancelando.set(false);
          this.confirmandoCancelacion.set(false);
          this.llenarFormulario();
        }),
      error: (err) => {
        this.error.set(mensajeError(err, 'No pudimos cancelar el proceso programado.'));
        this.cancelando.set(false);
      },
    });
  }
}
