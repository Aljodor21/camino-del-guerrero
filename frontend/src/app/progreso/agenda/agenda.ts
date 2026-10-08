import {
  Component,
  ChangeDetectionStrategy,
  OnInit,
  computed,
  inject,
  signal,
  viewChild,
} from '@angular/core';
import { NgTemplateOutlet } from '@angular/common';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ButtonModule } from 'primeng/button';
import { DialogModule } from 'primeng/dialog';
import { InputTextModule } from 'primeng/inputtext';
import { MessageModule } from 'primeng/message';
import { ProgressSpinnerModule } from 'primeng/progressspinner';
import { SelectButtonModule } from 'primeng/selectbutton';
import { TextareaModule } from 'primeng/textarea';

import { AgendaService, diasPara } from '../../core/services/agenda';
import {
  Recordatorio,
  RecordatorioPayload,
  TipoRecordatorio,
} from '../../core/models/agenda.model';
import { AVISOS_RECORDATORIO, TIPOS_RECORDATORIO } from '../../core/constants/proceso';
import { cuandoEs, formatearFecha, formatearHora, hoyISO, sumarDias } from '../../shared/fechas';
import { mensajeError } from '../../shared/errores';
import { Suplementos } from '../suplementos/suplementos';

/** Fechas importantes del proceso: controles, mediciones y otros recordatorios. */
@Component({
  selector: 'app-agenda',
  templateUrl: './agenda.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    NgTemplateOutlet,
    ReactiveFormsModule,
    ButtonModule,
    DialogModule,
    InputTextModule,
    MessageModule,
    ProgressSpinnerModule,
    SelectButtonModule,
    TextareaModule,
    Suplementos,
  ],
})
export class Agenda implements OnInit {
  private fb = inject(NonNullableFormBuilder);
  protected agenda = inject(AgendaService);
  private suplementos = viewChild.required(Suplementos);

  protected tipos = TIPOS_RECORDATORIO;
  protected avisos = AVISOS_RECORDATORIO;
  protected hoy = hoyISO();
  protected maximo = sumarDias(this.hoy, 730);
  protected formatearFecha = formatearFecha;
  protected formatearHora = formatearHora;
  protected cuandoEs = cuandoEs;

  protected cargando = signal(true);
  protected error = signal('');
  /** null: cerrado · 'nuevo' · id del que se edita. */
  protected editando = signal<'nuevo' | number | null>(null);
  protected guardando = signal(false);
  protected confirmarEliminar = signal(false);

  protected vencidos = computed(() => this.agenda.pendientes().filter((r) => diasPara(r) < 0));
  protected proximos = computed(() => this.agenda.pendientes().filter((r) => diasPara(r) >= 0));

  protected form = this.fb.group({
    tipo: this.fb.control<TipoRecordatorio>('control'),
    titulo: this.fb.control('', [Validators.required, Validators.maxLength(120)]),
    fecha: this.fb.control('', Validators.required),
    hora: this.fb.control(''),
    avisar_dias_antes: this.fb.control(1),
    nota: this.fb.control('', Validators.maxLength(300)),
  });

  ngOnInit(): void {
    this.agenda.cargar(true).subscribe({
      next: () => this.cargando.set(false),
      error: (err) => {
        this.error.set(mensajeError(err, 'No pudimos cargar tu agenda.'));
        this.cargando.set(false);
      },
    });
  }

  protected icono(tipo: TipoRecordatorio): string {
    if (tipo === 'suplemento') return 'pi pi-box';
    return TIPOS_RECORDATORIO.find((t) => t.value === tipo)?.icon ?? 'pi pi-bookmark';
  }

  /** Los sugeridos no se editan: se abre lo que los resuelve en su suplemento. */
  protected abrir(r: Recordatorio): void {
    if (r.automatico) this.suplementos().resolver(r);
    else this.editar(r);
  }

  protected mes(iso: string): string {
    return formatearFecha(iso, 'grafica').split(' ').at(-1)!.replace('.', '');
  }

  protected dia(iso: string): number {
    return Number(iso.slice(8, 10));
  }

  protected nuevo(): void {
    this.error.set('');
    this.confirmarEliminar.set(false);
    this.form.reset({
      tipo: 'control',
      titulo: TIPOS_RECORDATORIO[0].tituloSugerido,
      fecha: '',
      hora: '',
      avisar_dias_antes: 1,
      nota: '',
    });
    this.editando.set('nuevo');
  }

  private editar(r: Recordatorio): void {
    this.error.set('');
    this.confirmarEliminar.set(false);
    this.form.reset({
      tipo: r.tipo,
      titulo: r.titulo,
      fecha: r.fecha,
      hora: r.hora?.slice(0, 5) ?? '',
      avisar_dias_antes: r.avisar_dias_antes,
      nota: r.nota,
    });
    this.editando.set(r.id);
  }

  /** Al cambiar el tipo, propone su título si el actual era el sugerido de otro tipo o estaba vacío. */
  protected cambiarTipo(tipo: TipoRecordatorio): void {
    const titulo = this.form.controls.titulo.value.trim();
    const sugeridos = TIPOS_RECORDATORIO.map((t) => t.tituloSugerido);
    if (!titulo || sugeridos.includes(titulo)) {
      this.form.controls.titulo.setValue(
        TIPOS_RECORDATORIO.find((t) => t.value === tipo)!.tituloSugerido,
      );
    }
  }

  protected cerrar(): void {
    this.editando.set(null);
  }

  protected guardar(): void {
    const editando = this.editando();
    if (editando === null || this.form.invalid) return;
    const v = this.form.getRawValue();
    const payload: RecordatorioPayload = {
      ...v,
      titulo: v.titulo.trim(),
      nota: v.nota.trim(),
      hora: v.hora || null,
    };
    this.guardando.set(true);
    this.error.set('');
    const peticion =
      editando === 'nuevo' ? this.agenda.crear(payload) : this.agenda.actualizar(editando, payload);
    peticion.subscribe({
      next: () => {
        this.guardando.set(false);
        this.cerrar();
      },
      error: (err) => {
        this.error.set(mensajeError(err, 'No pudimos guardar el recordatorio.'));
        this.guardando.set(false);
      },
    });
  }

  protected completar(r: Recordatorio, completado = true): void {
    if (r.automatico) {
      this.suplementos().resolver(r);
      return;
    }
    this.agenda.actualizar(r.id, { completado }).subscribe({
      error: (err) => this.error.set(mensajeError(err, 'No pudimos actualizar el recordatorio.')),
    });
  }

  protected eliminar(): void {
    const id = this.editando();
    if (typeof id !== 'number') return;
    this.agenda.eliminar(id).subscribe({
      next: () => this.cerrar(),
      error: (err) => this.error.set(mensajeError(err, 'No pudimos eliminar el recordatorio.')),
    });
  }
}
