import { Component, ChangeDetectionStrategy, input } from '@angular/core';
import { FormControl, FormGroup, NonNullableFormBuilder, ReactiveFormsModule } from '@angular/forms';
import { SelectButtonModule } from 'primeng/selectbutton';

import { ConfigEntrenamiento } from '../../core/models/proceso.model';
import { CONFIG_ENTRENAMIENTO_INICIAL, DIAS, DURACIONES, ENFOQUES, NIVELES } from '../../core/constants/proceso';

export type EntrenamientoFormGroup = FormGroup<{
  [K in keyof ConfigEntrenamiento]: FormControl<ConfigEntrenamiento[K]>;
}>;

export function crearEntrenamientoForm(
  fb: NonNullableFormBuilder,
  inicial: ConfigEntrenamiento | null = null,
): EntrenamientoFormGroup {
  const c = inicial ?? CONFIG_ENTRENAMIENTO_INICIAL;
  return fb.group({
    nivel_actividad: fb.control(c.nivel_actividad),
    dias_entrenamiento: fb.control(c.dias_entrenamiento),
    duracion_sesion: fb.control(c.duracion_sesion),
    enfoque_entrenamiento: fb.control(c.enfoque_entrenamiento),
  });
}

/** Enfoque, nivel, días y duración: lo que necesita la rutina. */
@Component({
  selector: 'app-entrenamiento-form',
  templateUrl: './entrenamiento-form.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [ReactiveFormsModule, SelectButtonModule],
})
export class EntrenamientoForm {
  readonly form = input.required<EntrenamientoFormGroup>();

  protected readonly enfoques = ENFOQUES;
  protected readonly niveles = NIVELES;
  protected readonly dias = DIAS;
  protected readonly duraciones = DURACIONES;

  protected clasesOpcion(activa: boolean): string {
    const base =
      'flex items-center gap-3 p-3 rounded-xl border-2 text-left transition-colors w-full focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-guerrero-red';
    return activa
      ? `${base} border-guerrero-red bg-red-50 dark:bg-guerrero-red/10 text-guerrero-red`
      : `${base} border-gray-200 dark:border-dark-700 text-gray-600 dark:text-gray-400 hover:border-gray-300 dark:hover:border-gray-600`;
  }
}
