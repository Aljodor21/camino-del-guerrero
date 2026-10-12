import { Directive, ElementRef, forwardRef, inject } from '@angular/core';
import {
  AbstractControl,
  ControlValueAccessor,
  NG_VALIDATORS,
  NG_VALUE_ACCESSOR,
  ValidationErrors,
  Validator,
} from '@angular/forms';

/** Convierte "63,4" o "63.4" en 63.4; vacío → null; texto inválido → NaN. */
export function parsearDecimal(texto: string): number | null {
  const limpio = texto.trim().replace(',', '.');
  if (!limpio) return null;
  return /^\d+(\.\d+)?$/.test(limpio) ? Number(limpio) : NaN;
}

/**
 * Campo numérico que acepta coma o punto como separador decimal y muestra coma.
 * Nunca ajusta el valor por su cuenta: si está fuera de rango, el control queda inválido.
 */
@Directive({
  selector: 'input[appDecimal]',
  providers: [
    { provide: NG_VALUE_ACCESSOR, useExisting: forwardRef(() => DecimalInput), multi: true },
    { provide: NG_VALIDATORS, useExisting: forwardRef(() => DecimalInput), multi: true },
  ],
  host: {
    inputmode: 'decimal',
    autocomplete: 'off',
    '(input)': 'alEscribir()',
    '(blur)': 'alSalir()',
  },
})
export class DecimalInput implements ControlValueAccessor, Validator {
  private el = inject<ElementRef<HTMLInputElement>>(ElementRef);
  private onChange: (valor: number | null) => void = () => {};
  private onTouched: () => void = () => {};

  writeValue(valor: number | null): void {
    this.el.nativeElement.value =
      valor === null || valor === undefined ? '' : String(valor).replace('.', ',');
  }

  registerOnChange(fn: (valor: number | null) => void): void {
    this.onChange = fn;
  }

  registerOnTouched(fn: () => void): void {
    this.onTouched = fn;
  }

  setDisabledState(deshabilitado: boolean): void {
    this.el.nativeElement.disabled = deshabilitado;
  }

  validate(control: AbstractControl): ValidationErrors | null {
    return typeof control.value === 'number' && Number.isNaN(control.value)
      ? { decimal: true }
      : null;
  }

  protected alEscribir(): void {
    this.onChange(parsearDecimal(this.el.nativeElement.value));
  }

  protected alSalir(): void {
    this.onTouched();
  }
}
