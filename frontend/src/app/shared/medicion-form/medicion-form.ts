import { Component, ChangeDetectionStrategy, input } from '@angular/core';
import { FormControl, FormGroup, NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { InputTextModule } from 'primeng/inputtext';
import { SelectButtonModule } from 'primeng/selectbutton';

import { MedicionPayload, OrigenMedicion } from '../../core/models/proceso.model';
import { ORIGENES_MEDICION } from '../../core/constants/proceso';
import { hoyISO } from '../fechas';
import { DecimalInput } from '../decimal-input';

const PERIMETROS = [
  { campo: 'cintura_cm', label: 'Cintura' },
  { campo: 'abdomen_cm', label: 'Abdomen' },
  { campo: 'cadera_cm', label: 'Cadera' },
  { campo: 'brazo_cm', label: 'Brazo' },
  { campo: 'muslo_cm', label: 'Muslo' },
  { campo: 'pierna_cm', label: 'Pierna' },
] as const;

const PLIEGUES = [
  { campo: 'pliegue_triceps_mm', label: 'Tríceps' },
  { campo: 'pliegue_biceps_mm', label: 'Bíceps' },
  { campo: 'pliegue_subescapular_mm', label: 'Subescapular' },
  { campo: 'pliegue_supraespinal_mm', label: 'Supraespinal' },
  { campo: 'pliegue_abdominal_mm', label: 'Abdominal' },
  { campo: 'pliegue_muslo_mm', label: 'Muslo' },
  { campo: 'pliegue_pierna_mm', label: 'Pierna' },
  { campo: 'pliegue_cresta_iliaca_mm', label: 'Cresta ilíaca' },
] as const;

type CampoOpcional = (typeof PERIMETROS)[number]['campo'] | (typeof PLIEGUES)[number]['campo'];

export type MedicionFormGroup = FormGroup<
  {
    fecha: FormControl<string>;
    origen: FormControl<OrigenMedicion>;
    peso_kg: FormControl<number | null>;
    talla_cm: FormControl<number | null>;
    nota: FormControl<string>;
  } & Record<CampoOpcional, FormControl<number | null>>
>;

export function crearMedicionForm(fb: NonNullableFormBuilder, talla: number | null): MedicionFormGroup {
  const opcional = (min: number, max: number) =>
    fb.control<number | null>(null, [Validators.min(min), Validators.max(max)]);
  return fb.group({
    fecha: fb.control(hoyISO(), Validators.required),
    origen: fb.control<OrigenMedicion>('propia'),
    peso_kg: fb.control<number | null>(null, [Validators.required, Validators.min(20), Validators.max(300)]),
    talla_cm: fb.control<number | null>(talla, [Validators.min(100), Validators.max(250)]),
    nota: fb.control(''),
    ...Object.fromEntries(PERIMETROS.map((p) => [p.campo, opcional(10, 250)])),
    ...Object.fromEntries(PLIEGUES.map((p) => [p.campo, opcional(1, 80)])),
  } as MedicionFormGroup['controls']);
}

/** Convierte el formulario en el payload de la API, sin los campos vacíos. */
export function leerMedicion(form: MedicionFormGroup, conFecha: boolean): MedicionPayload {
  const { fecha, ...resto } = form.getRawValue();
  const limpio = Object.fromEntries(Object.entries(resto).filter(([, v]) => v !== null && v !== ''));
  return { ...(conFecha ? { fecha } : {}), ...limpio } as MedicionPayload;
}

/** Campos de una medición corporal: peso y talla, y opcionalmente perímetros y pliegues. */
@Component({
  selector: 'app-medicion-form',
  templateUrl: './medicion-form.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    DecimalInput, ReactiveFormsModule, InputTextModule, SelectButtonModule],
})
export class MedicionForm {
  readonly form = input.required<MedicionFormGroup>();
  /** Muestra la fecha (para registrar mediciones pasadas, p. ej. la de una consulta). */
  readonly conFecha = input(false);

  protected readonly perimetros = PERIMETROS;
  protected readonly pliegues = PLIEGUES;
  protected readonly origenes = ORIGENES_MEDICION;
  protected readonly hoy = hoyISO();

  protected imc(): number | null {
    const { peso_kg, talla_cm } = this.form().getRawValue();
    if (!peso_kg || !talla_cm || Number.isNaN(peso_kg) || talla_cm < 100) return null;
    return Math.round((peso_kg / (talla_cm / 100) ** 2) * 100) / 100;
  }
}
