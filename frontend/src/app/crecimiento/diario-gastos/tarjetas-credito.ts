import { ChangeDetectionStrategy, Component, inject, input, output, signal } from '@angular/core';
import { NgTemplateOutlet } from '@angular/common';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ButtonModule } from 'primeng/button';
import { InputTextModule } from 'primeng/inputtext';

import { ProyectoCrecimiento } from '../../core/models/crecimiento.model';
import {
  EstadoDiario,
  TarjetaCredito,
  TarjetaPayload,
} from '../../core/models/diario-gastos.model';
import { DiarioGastosService } from '../../core/services/diario-gastos';
import { mensajeError } from '../../shared/errores';
import { formatearFecha } from '../../shared/fechas';

const PESOS = new Intl.NumberFormat('es-CO', {
  style: 'currency',
  currency: 'COP',
  maximumFractionDigits: 0,
});

/**
 * Las tarjetas de crédito del diario: agregarlas, cambiarlas o quitarlas, y por cada una lo que va en su
 * corte, la factura por pagar y lo que queda del cupo. Las compras se anotan en el registro eligiendo la
 * tarjeta (`anotarCon`), así cuentan en el mes como cualquier gasto.
 */
@Component({
  selector: 'app-tarjetas-credito',
  templateUrl: './tarjetas-credito.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [NgTemplateOutlet, ReactiveFormsModule, ButtonModule, InputTextModule],
})
export class TarjetasCredito {
  readonly proyecto = input.required<ProyectoCrecimiento>();
  readonly estado = input.required<EstadoDiario>();
  readonly cambio = output<EstadoDiario>();
  readonly anotarCon = output<number>();

  private servicio = inject(DiarioGastosService);
  private fb = inject(FormBuilder);

  /** La tarjeta que se está editando: su id, «nueva» o ninguna. */
  protected editando = signal<number | 'nueva' | null>(null);
  protected confirmarQuitar = signal<number | null>(null);
  protected guardando = signal(false);
  protected error = signal('');

  protected form = this.fb.nonNullable.group({
    nombre: ['', [Validators.required, Validators.maxLength(40)]],
    ultimos: ['', [Validators.pattern(/^\d{4}$/)]],
    cupo: [''],
    dia_corte: ['', [Validators.min(1), Validators.max(31)]],
    dia_pago: ['', [Validators.min(1), Validators.max(31)]],
    avisar: [true],
  });

  protected pesos(n: number): string {
    return PESOS.format(n);
  }

  protected fecha(iso: string): string {
    return formatearFecha(iso, 'grafica');
  }

  protected usado(t: TarjetaCredito): number {
    return t.cupo ? Math.min(100, Math.round((t.deuda / t.cupo) * 100)) : 0;
  }

  protected nueva(): void {
    this.form.reset();
    this.error.set('');
    this.editando.set('nueva');
  }

  protected editar(t: TarjetaCredito): void {
    this.form.reset({
      nombre: t.nombre,
      ultimos: t.ultimos,
      cupo: t.cupo ? String(t.cupo) : '',
      dia_corte: t.dia_corte ? String(t.dia_corte) : '',
      dia_pago: t.dia_pago ? String(t.dia_pago) : '',
      avisar: t.avisar,
    });
    this.error.set('');
    this.editando.set(t.id);
  }

  protected cancelar(): void {
    this.editando.set(null);
  }

  private datos(): TarjetaPayload {
    const v = this.form.getRawValue();
    const numero = (texto: string) => Number(String(texto).replace(/[^\d]/g, '')) || null;
    return {
      nombre: v.nombre.trim(),
      ultimos: v.ultimos.trim(),
      cupo: numero(v.cupo),
      dia_corte: numero(v.dia_corte),
      dia_pago: numero(v.dia_pago),
      avisar: v.avisar,
    };
  }

  protected guardar(): void {
    const id = this.editando();
    if (this.form.invalid || id === null) return;
    this.guardando.set(true);
    const pedido =
      id === 'nueva'
        ? this.servicio.agregarTarjeta(this.proyecto().id, this.datos())
        : this.servicio.cambiarTarjeta(this.proyecto().id, id, this.datos());
    pedido.subscribe({
      next: (e) => {
        this.guardando.set(false);
        this.editando.set(null);
        this.cambio.emit(e);
      },
      error: (e) => {
        this.guardando.set(false);
        this.error.set(mensajeError(e, 'No pudimos guardar la tarjeta.'));
      },
    });
  }

  /** Dos toques: el primero pregunta, el segundo la quita. */
  protected quitar(t: TarjetaCredito): void {
    if (this.confirmarQuitar() !== t.id) {
      this.confirmarQuitar.set(t.id);
      return;
    }
    this.confirmarQuitar.set(null);
    this.servicio.quitarTarjeta(this.proyecto().id, t.id).subscribe({
      next: (e) => this.cambio.emit(e),
      error: (e) => this.error.set(mensajeError(e, 'No pudimos quitar la tarjeta.')),
    });
  }
}
