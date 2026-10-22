import {
  ChangeDetectionStrategy,
  Component,
  OnInit,
  computed,
  inject,
  input,
  signal,
} from '@angular/core';
import { NgTemplateOutlet } from '@angular/common';
import { ButtonModule } from 'primeng/button';
import { InputTextModule } from 'primeng/inputtext';
import { MessageModule } from 'primeng/message';

import { ProyectoCrecimiento } from '../../core/models/crecimiento.model';
import {
  ClaseGasto,
  EstadoDiario,
  Frecuencia,
  GastoAnotado,
  RubroPayload,
} from '../../core/models/diario-gastos.model';
import { CrecimientoService } from '../../core/services/crecimiento';
import { DiarioGastosService } from '../../core/services/diario-gastos';
import { clasesChip } from '../../shared/chip';
import { mensajeError } from '../../shared/errores';
import { formatearFecha, hoyISO, sumarDias } from '../../shared/fechas';
import { Pestana, Pestanas } from '../../shared/pestanas/pestanas';
import { AnalisisGastos } from './analisis-gastos';
import { TarjetasCredito } from './tarjetas-credito';

type Seccion = 'gastos' | 'registro' | 'tarjetas' | 'resumen' | 'guia';
type Modo = 'cerebral' | 'emocional' | 'mixto';

const PESTANAS: Pestana<Seccion>[] = [
  { id: 'gastos', label: 'Mis gastos', icon: 'pi pi-list' },
  { id: 'registro', label: 'Registro', icon: 'pi pi-pencil' },
  { id: 'tarjetas', label: 'Tarjetas', icon: 'pi pi-credit-card' },
  { id: 'resumen', label: 'Resumen', icon: 'pi pi-chart-pie' },
  { id: 'guia', label: '¿Cerebral o emocional?', icon: 'pi pi-question-circle' },
];

const FRECUENCIAS: { id: Frecuencia; label: string }[] = [
  { id: 'mensual', label: 'Cada mes' },
  { id: 'anual', label: 'Al año' },
  { id: 'semestral', label: '2 al año' },
  { id: 'hormiga', label: 'Diario (hormiga)' },
];

const MESES = [
  'enero',
  'febrero',
  'marzo',
  'abril',
  'mayo',
  'junio',
  'julio',
  'agosto',
  'septiembre',
  'octubre',
  'noviembre',
  'diciembre',
];

const PESOS = new Intl.NumberFormat('es-CO', {
  style: 'currency',
  currency: 'COP',
  maximumFractionDigits: 0,
});

/** Lo que cae en el mes de un pago, según cada cuánto se paga (igual que el servidor). */
function factor(r: Pick<RubroPayload, 'frecuencia' | 'dias_mes'>): number {
  return { mensual: 1, anual: 1 / 12, semestral: 2 / 12, hormiga: r.dias_mes }[r.frecuencia];
}

/** Lo escrito en un campo de pesos → número entero (quita puntos, comas y el signo). */
function aPesos(texto: string): number {
  const n = Number(String(texto).replace(/[^\d]/g, ''));
  return Number.isFinite(n) ? n : 0;
}

/**
 * Diario de gastos («Sana tus finanzas», capítulo 2, paso 1): la lista de gastos del ejercicio (categoría, rubro,
 * valor, cerebral y emocional) donde cada gasto dice cada cuánto se paga y todo suma un solo gasto mensual, más el
 * registro de lo que se gasta de verdad este mes.
 */
@Component({
  selector: 'app-diario-gastos',
  templateUrl: './diario-gastos.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    NgTemplateOutlet,
    ButtonModule,
    InputTextModule,
    MessageModule,
    Pestanas,
    TarjetasCredito,
    AnalisisGastos,
  ],
})
export class DiarioGastos implements OnInit {
  readonly proyecto = input.required<ProyectoCrecimiento>();

  private servicio = inject(DiarioGastosService);
  private crecimiento = inject(CrecimientoService);

  protected pestanas = PESTANAS;
  protected frecuencias = FRECUENCIAS;
  protected meses = MESES;
  protected clasesChip = clasesChip;
  protected hoy = hoyISO();
  protected haceUnaSemana = sumarDias(hoyISO(), -7);

  protected seccion = signal<Seccion>('gastos');
  protected estado = signal<EstadoDiario | null>(null);
  protected cargando = signal(true);
  protected guardando = signal(false);
  protected error = signal('');
  protected aviso = signal('');
  protected nombreCategoria = computed(
    () => new Map((this.estado()?.categorias ?? []).map((c) => [c.id, c.nombre])),
  );

  // ── Mis gastos ──
  protected borrador = signal<RubroPayload[]>([]);
  protected modos = signal<Modo[]>([]);
  protected cambiado = signal(false);
  protected nuevoRubro = signal<Partial<Record<string, string>>>({});
  /** El total del mes con lo que lleva escrito (aún sin guardar). */
  protected totales = computed(() => {
    let total = 0;
    let cerebral = 0;
    for (const r of this.borrador()) {
      total += Math.ceil(r.valor * factor(r));
      cerebral += Math.ceil(r.cerebral * factor(r));
    }
    return { total, cerebral, emocional: total - cerebral };
  });

  // ── Registro ──
  protected gValor = signal('');
  protected gDescripcion = signal('');
  protected gCategoria = signal('');
  protected gClase = signal<ClaseGasto | null>(null);
  protected gFecha = signal(hoyISO());
  /** Con qué se pagó: una tarjeta de crédito (y a cuántas cuotas) o nada (efectivo, débito…). */
  protected gTarjeta = signal<number | null>(null);
  protected gCuotas = signal(1);
  protected puedeAnotar = computed(
    () =>
      aPesos(this.gValor()) > 0 &&
      !!this.gDescripcion().trim() &&
      !!this.gCategoria() &&
      !!this.gClase(),
  );
  protected cuota = computed(() => Math.ceil(aPesos(this.gValor()) / this.gCuotas()));
  protected porDia = computed(() => {
    const dias = new Map<string, GastoAnotado[]>();
    for (const g of this.estado()?.registro ?? []) {
      dias.set(g.fecha, [...(dias.get(g.fecha) ?? []), g]);
    }
    return [...dias].map(([fecha, gastos]) => ({
      fecha,
      gastos,
      total: gastos.reduce((s, g) => s + g.valor, 0),
    }));
  });

  // ── Ajustes del aviso ──
  protected avisar = signal(true);
  protected horaAviso = signal('20:00');

  ngOnInit(): void {
    this.servicio
      .cargar(this.proyecto().id)
      .subscribe({ next: this.listo(), error: this.fallo('No pudimos cargar tu diario.') });
  }

  protected pesos(n: number): string {
    return PESOS.format(n);
  }

  protected fecha(iso: string): string {
    return iso === this.hoy ? 'Hoy' : formatearFecha(iso, 'dia');
  }

  protected porcentaje(parte: number, total: number): number {
    return total ? Math.round((parte / total) * 100) : 0;
  }

  protected mensual(r: RubroPayload): number {
    return Math.ceil(r.valor * factor(r));
  }

  protected leer(e: Event): string {
    return (e.target as HTMLInputElement).value;
  }

  private aplicar(e: EstadoDiario): void {
    this.estado.set(e);
    this.borrador.set(
      e.rubros.map(({ categoria, nombre, frecuencia, valor, cerebral, dias_mes, mes_pago }) => ({
        categoria,
        nombre,
        frecuencia,
        valor,
        cerebral,
        dias_mes,
        mes_pago,
      })),
    );
    this.modos.set(e.rubros.map((r) => this.modoDe(r)));
    this.cambiado.set(false);
    this.avisar.set(e.ajustes.avisar);
    this.horaAviso.set(e.ajustes.hora_aviso);
  }

  private fallo(texto: string): (e: unknown) => void {
    return (e) => {
      this.cargando.set(false);
      this.guardando.set(false);
      this.error.set(mensajeError(e, texto));
    };
  }

  /** Cada cambio responde el diario entero: se pinta tal cual. */
  private listo(mensaje = ''): (e: EstadoDiario) => void {
    return (e) => {
      this.cargando.set(false);
      this.guardando.set(false);
      this.error.set('');
      this.aviso.set(mensaje);
      this.aplicar(e);
    };
  }

  // ── Mis gastos ──
  private modoDe(r: Pick<RubroPayload, 'valor' | 'cerebral'>): Modo {
    if (r.valor && r.cerebral === 0) return 'emocional';
    if (r.cerebral && r.cerebral < r.valor) return 'mixto';
    return 'cerebral';
  }

  protected rubrosDe(categoria: string): { r: RubroPayload; i: number }[] {
    return this.borrador()
      .map((r, i) => ({ r, i }))
      .filter((x) => x.r.categoria === categoria);
  }

  protected totalDe(categoria: string): number {
    return this.rubrosDe(categoria).reduce((s, x) => s + this.mensual(x.r), 0);
  }

  private cambiar(i: number, cambio: Partial<RubroPayload>): void {
    this.borrador.update((l) =>
      l.map((r, j) => {
        if (j !== i) return r;
        const n = { ...r, ...cambio };
        n.cerebral = Math.min(n.cerebral, n.valor);
        return n;
      }),
    );
    this.cambiado.set(true);
  }

  protected fijarValor(i: number, texto: string): void {
    const valor = aPesos(texto);
    const modo = this.modos()[i];
    const r = this.borrador()[i];
    this.cambiar(i, {
      valor,
      cerebral:
        modo === 'cerebral' ? valor : modo === 'emocional' ? 0 : Math.min(r.cerebral, valor),
    });
  }

  protected fijarModo(i: number, modo: Modo): void {
    this.modos.update((l) => l.map((m, j) => (j === i ? modo : m)));
    const r = this.borrador()[i];
    this.cambiar(i, {
      cerebral: modo === 'cerebral' ? r.valor : modo === 'emocional' ? 0 : Math.round(r.valor / 2),
    });
  }

  protected fijarCerebral(i: number, texto: string): void {
    this.cambiar(i, { cerebral: aPesos(texto) });
  }

  protected fijarFrecuencia(i: number, frecuencia: Frecuencia): void {
    this.cambiar(i, { frecuencia });
  }

  protected fijarDias(i: number, texto: string): void {
    this.cambiar(i, { dias_mes: Math.min(31, Math.max(1, Number(texto) || 30)) });
  }

  protected fijarMesPago(i: number, texto: string): void {
    this.cambiar(i, { mes_pago: Number(texto) || null });
  }

  protected quitarRubro(i: number): void {
    this.borrador.update((l) => l.filter((_, j) => j !== i));
    this.modos.update((l) => l.filter((_, j) => j !== i));
    this.cambiado.set(true);
  }

  protected escribirNuevo(categoria: string, texto: string): void {
    this.nuevoRubro.update((n) => ({ ...n, [categoria]: texto }));
  }

  protected agregarRubro(categoria: string): void {
    const nombre = (this.nuevoRubro()[categoria] ?? '').trim();
    if (!nombre) return;
    this.borrador.update((l) => [
      ...l,
      {
        categoria,
        nombre,
        frecuencia: 'mensual',
        valor: 0,
        cerebral: 0,
        dias_mes: 30,
        mes_pago: null,
      },
    ]);
    this.modos.update((l) => [...l, 'cerebral']);
    this.nuevoRubro.update((n) => ({ ...n, [categoria]: '' }));
    this.cambiado.set(true);
  }

  protected guardarGastos(): void {
    this.guardando.set(true);
    this.servicio.guardarRubros(this.proyecto().id, this.borrador()).subscribe({
      next: this.listo('Guardado.'),
      error: this.fallo('No pudimos guardar tus gastos.'),
    });
  }

  /** Lo que se ve debajo del rubro cuando no es de cada mes. */
  protected detalle(i: number): string {
    const r = this.estado()?.rubros[i];
    const b = this.borrador()[i];
    if (!b?.valor || b.frecuencia === 'mensual') return '';
    const mes = this.pesos(this.mensual(b));
    if (b.frecuencia === 'hormiga') {
      return `${this.pesos(b.valor)} × ${b.dias_mes} días = ${mes} al mes · ${this.pesos(this.mensual(b) * 12)} al año`;
    }
    const anio = b.valor * (b.frecuencia === 'semestral' ? 2 : 1);
    let texto = `${this.pesos(anio)} al año ÷ 12 = ${mes} al mes`;
    // Lo de los meses que faltan sale del servidor ya guardado.
    if (r && r.nombre === b.nombre && r.meses_faltan !== undefined && !this.cambiado()) {
      texto += r.meses_faltan
        ? ` · si empiezas ahora: ${this.pesos(r.ahorro_hasta_pago ?? 0)} al mes por ${r.meses_faltan} ${r.meses_faltan === 1 ? 'mes' : 'meses'}`
        : ' · este mes toca pagarlo';
    }
    return texto;
  }

  // ── Registro ──
  protected anotar(): void {
    if (!this.puedeAnotar()) return;
    this.guardando.set(true);
    this.servicio
      .anotar(this.proyecto().id, {
        fecha: this.gFecha(),
        valor: aPesos(this.gValor()),
        descripcion: this.gDescripcion().trim(),
        categoria: this.gCategoria(),
        clase: this.gClase()!,
        tarjeta: this.gTarjeta(),
        cuotas: this.gTarjeta() ? this.gCuotas() : 1,
      })
      .subscribe({
        next: (e) => {
          this.gValor.set('');
          this.gDescripcion.set('');
          this.gClase.set(null);
          this.gTarjeta.set(null);
          this.gCuotas.set(1);
          this.listo('Anotado.')(e);
        },
        error: this.fallo('No pudimos anotarlo.'),
      });
  }

  protected fijarCuotas(texto: string): void {
    this.gCuotas.set(Math.min(48, Math.max(1, Math.round(Number(texto)) || 1)));
  }

  /** Desde una tarjeta: el registro queda listo con esa tarjeta elegida. */
  protected anotarConTarjeta(id: number): void {
    this.gTarjeta.set(id);
    this.aviso.set('');
    this.seccion.set('registro');
  }

  protected tarjetaCambio(e: EstadoDiario): void {
    this.listo()(e);
    // Si quitó la tarjeta elegida en el registro, vuelve a «sin tarjeta».
    if (!e.tarjetas.some((t) => t.id === this.gTarjeta())) this.gTarjeta.set(null);
  }

  /** Pasa el gasto a otra categoría; el diario vuelve recalculado. */
  protected cambiarCategoria(g: GastoAnotado, categoria: string): void {
    if (!categoria || categoria === g.categoria) return;
    this.servicio.cambiarCategoria(this.proyecto().id, g.id, categoria).subscribe({
      next: this.listo(`«${g.descripcion}» pasó a ${this.nombreCategoria().get(categoria)}.`),
      error: this.fallo('No pudimos cambiar la categoría.'),
    });
  }

  protected borrarGasto(g: GastoAnotado): void {
    this.servicio
      .borrarGasto(this.proyecto().id, g.id)
      .subscribe({ next: this.listo(), error: this.fallo('No pudimos borrarlo.') });
  }

  protected hoyNoGaste(): void {
    this.guardando.set(true);
    this.servicio.sinGasto(this.proyecto().id, this.hoy).subscribe({
      next: this.listo('Listo: hoy no gastaste nada.'),
      error: this.fallo('No pudimos guardarlo.'),
    });
  }

  protected guardarAjustes(avisar: boolean, hora: string): void {
    this.avisar.set(avisar);
    this.horaAviso.set(hora);
    this.crecimiento
      .actualizarProyecto(this.proyecto().id, { datos: { avisar, hora_aviso: hora } })
      .subscribe({
        next: () =>
          this.aviso.set(
            avisar ? `Te aviso a las ${hora} si no has anotado.` : 'Sin aviso diario.',
          ),
        error: this.fallo('No pudimos guardar el aviso.'),
      });
  }
}
