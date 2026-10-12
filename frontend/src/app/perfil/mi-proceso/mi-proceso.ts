import {
  Component,
  ChangeDetectionStrategy,
  inject,
  signal,
  computed,
  OnInit,
} from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ButtonModule } from 'primeng/button';
import { InputTextModule } from 'primeng/inputtext';
import { TextareaModule } from 'primeng/textarea';
import { MessageModule } from 'primeng/message';

import { ProcesoService } from '../../core/services/proceso';
import { Modulo, Proceso } from '../../core/models/proceso.model';
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
  host: { class: 'block space-y-6' },
  imports: [
    DecimalInput,
    RouterLink,
    ReactiveFormsModule,
    ButtonModule,
    InputTextModule,
    TextareaModule,
    MessageModule,
    EntrenamientoForm,
  ],
})
export class MiProceso implements OnInit {
  private fb = inject(NonNullableFormBuilder);
  protected procesos = inject(ProcesoService);
  private router = inject(Router);

  protected proceso = this.procesos.vigente;
  protected historial = signal<Proceso[]>([]);
  protected guardando = signal(false);
  protected confirmandoBorrado = signal(false);
  /** El módulo que se está por quitar (pide confirmación). */
  protected quitando = signal<Modulo | null>(null);
  protected readonly modulos: { id: Modulo; nombre: string; icono: string; aviso: string }[] = [
    {
      id: 'alimentacion',
      nombre: 'Alimentación',
      icono: 'pi pi-heart',
      aviso:
        'Se borra tu plan de comida, menús, lista de mercado, suplementos y lo que contaste de tus comidas. El entrenamiento sigue igual.',
    },
    {
      id: 'entrenamiento',
      nombre: 'Entrenamiento',
      icono: 'pi pi-bolt',
      aviso:
        'Se borra tu rutina, tus implementos y tus sesiones registradas. La alimentación sigue igual.',
    },
  ];
  protected quitandoCargando = signal(false);
  protected borrando = signal(false);
  protected error = signal('');
  protected guardado = signal(false);
  protected formatearFecha = formatearFecha;
  protected num = formatearNumero;

  protected form = this.fb.group({
    peso_objetivo: this.fb.control<number | null>(null, [Validators.min(20), Validators.max(300)]),
    fecha_fin_plan: this.fb.control(''),
    notas: this.fb.control(''),
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

  /** La fecha meta se puede poner una vez; ya puesta, no se mueve. */
  protected finPlanFijo = computed(() => !!this.proceso()?.fecha_fin_plan);

  protected anteriores = computed(() => {
    const vigente = this.proceso()?.id;
    return this.historial().filter((p) => p.id !== vigente);
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
    });
    this.entrenamientoForm.reset(p.entrenamiento ?? CONFIG_ENTRENAMIENTO_INICIAL);
    if (p.fecha_fin_plan) this.form.controls.fecha_fin_plan.disable({ emitEvent: false });
  }

  protected guardar(): void {
    const p = this.proceso();
    if (!p || this.form.invalid) return;
    const v = this.form.getRawValue();
    const nuevaFecha = this.finPlanFijo() ? {} : { fecha_fin_plan: v.fecha_fin_plan || null };
    this.guardando.set(true);
    this.error.set('');
    this.guardado.set(false);
    this.procesos
      .actualizar(p.id, {
        peso_objetivo: v.peso_objetivo,
        ...nuevaFecha,
        notas: v.notas.trim(),
        ...(p.incluye_entrenamiento ? { entrenamiento: this.entrenamientoForm.getRawValue() } : {}),
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

  protected quitarModulo(modulo: Modulo): void {
    const p = this.proceso();
    if (!p) return;
    this.quitandoCargando.set(true);
    this.error.set('');
    this.procesos.quitarModulo(p.id, modulo).subscribe({
      next: () => {
        this.quitandoCargando.set(false);
        this.quitando.set(null);
        this.llenarFormulario();
      },
      error: (err) => {
        this.error.set(mensajeError(err, 'No pudimos quitar el módulo.'));
        this.quitandoCargando.set(false);
      },
    });
  }

  protected borrarProceso(): void {
    const p = this.proceso();
    if (!p) return;
    this.borrando.set(true);
    this.procesos.eliminarTodo(p.id).subscribe({
      next: () =>
        this.procesos.refrescar().subscribe(() => {
          this.borrando.set(false);
          void this.router.navigate(['/onboarding']);
        }),
      error: (err) => {
        this.error.set(mensajeError(err, 'No pudimos borrar el proceso.'));
        this.borrando.set(false);
        this.confirmandoBorrado.set(false);
      },
    });
  }
}
