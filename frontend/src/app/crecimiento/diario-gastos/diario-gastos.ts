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
  GastoAnotado,
  RubroMes,
} from '../../core/models/diario-gastos.model';
import { CrecimientoService } from '../../core/services/crecimiento';
import { DiarioGastosService } from '../../core/services/diario-gastos';
import { clasesChip } from '../../shared/chip';
import { mensajeError } from '../../shared/errores';
import { formatearFecha, hoyISO, sumarDias } from '../../shared/fechas';
import { Pestana, Pestanas } from '../../shared/pestanas/pestanas';

type Seccion = 'registro' | 'mes' | 'no_mensuales' | 'hormiga' | 'resumen' | 'guia';
type Modo = 'cerebral' | 'emocional' | 'mixto';

const PESTANAS: Pestana<Seccion>[] = [
  { id: 'registro', label: 'Registro', icon: 'pi pi-pencil' },
  { id: 'mes', label: 'Del mes', icon: 'pi pi-list' },
  { id: 'no_mensuales', label: 'Anuales', icon: 'pi pi-calendar' },
  { id: 'hormiga', label: 'Hormiga', icon: 'pi pi-shopping-bag' },
  { id: 'resumen', label: 'Resumen', icon: 'pi pi-chart-pie' },
  { id: 'guia', label: '¿Cerebral o emocional?', icon: 'pi pi-question-circle' },
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

function mesDe(iso: string): string {
  return iso.slice(0, 7);
}

function moverMes(mes: string, n: number): string {
  const [a, m] = mes.split('-').map(Number);
  const d = new Date(a, m - 1 + n, 1);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
}

/** Lo escrito en un campo de pesos → número entero (quita puntos, comas y el signo). */
function aPesos(texto: string): number {
  const n = Number(String(texto).replace(/[^\d]/g, ''));
  return Number.isFinite(n) ? n : 0;
}

/**
 * Diario de gastos («Sana tus finanzas», capítulo 2, paso 1), mes a mes: lo que se gasta de verdad cada día, la
 * relación de gastos del mes (cerebral, emocional o mixto), los gastos no mensuales aprovisionados, los gastos
 * hormiga y el resumen.
 */
@Component({
  selector: 'app-diario-gastos',
  templateUrl: './diario-gastos.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [NgTemplateOutlet, ButtonModule, InputTextModule, MessageModule, Pestanas],
})
export class DiarioGastos implements OnInit {
  readonly proyecto = input.required<ProyectoCrecimiento>();

  private servicio = inject(DiarioGastosService);
  private crecimiento = inject(CrecimientoService);

  protected pestanas = PESTANAS;
  protected meses = MESES;
  protected clasesChip = clasesChip;
  protected hoy = hoyISO();
  protected haceUnaSemana = sumarDias(hoyISO(), -7);

  protected seccion = signal<Seccion>('registro');
  protected mes = signal(mesDe(hoyISO()));
  protected estado = signal<EstadoDiario | null>(null);
  protected cargando = signal(true);
  protected guardando = signal(false);
  protected error = signal('');
  protected aviso = signal('');

  protected tituloMes = computed(() => {
    const [a, m] = this.mes().split('-').map(Number);
    return `${MESES[m - 1]} ${a}`;
  });
  protected esMesActual = computed(() => this.mes() === mesDe(hoyISO()));
  protected nombreCategoria = computed(
    () => new Map((this.estado()?.categorias ?? []).map((c) => [c.id, c.nombre])),
  );

  // ── Registro ──
  protected gValor = signal('');
  protected gDescripcion = signal('');
  protected gCategoria = signal('');
  protected gClase = signal<ClaseGasto | null>(null);
  protected gFecha = signal(hoyISO());
  protected puedeAnotar = computed(
    () =>
      aPesos(this.gValor()) > 0 &&
      !!this.gDescripcion().trim() &&
      !!this.gCategoria() &&
      !!this.gClase(),
  );
  /** Lo anotado del mes, por día (lo más reciente arriba). */
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

  // ── Del mes ──
  protected borrador = signal<RubroMes[]>([]);
  protected modos = signal<Modo[]>([]);
  protected cambiado = signal(false);
  protected nuevoRubro = signal<Partial<Record<string, string>>>({});
  protected totalesBorrador = computed(() => {
    const r = this.borrador();
    const total = r.reduce((s, x) => s + x.valor, 0);
    const cerebral = r.reduce((s, x) => s + x.cerebral, 0);
    return { total, cerebral, emocional: total - cerebral };
  });

  // ── Anuales y hormiga ──
  protected nNombre = signal('');
  protected nValor = signal('');
  protected nPeriodo = signal<'anual' | 'semestral'>('anual');
  protected nMes = signal(new Date().getMonth() + 1);
  protected nClase = signal<ClaseGasto | null>(null);
  protected hNombre = signal('');
  protected hValor = signal('');
  protected hDias = signal('30');
  protected hClase = signal<ClaseGasto | null>(null);

  // ── Ajustes del aviso ──
  protected avisar = signal(true);
  protected horaAviso = signal('20:00');

  ngOnInit(): void {
    this.cargar();
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

  private aplicar(e: EstadoDiario): void {
    this.estado.set(e);
    this.borrador.set(e.rubros.map((r) => ({ ...r })));
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

  /** Cada cambio responde el mes entero: se pinta tal cual. */
  private listo(mensaje = ''): (e: EstadoDiario) => void {
    return (e) => {
      this.cargando.set(false);
      this.guardando.set(false);
      this.error.set('');
      this.aviso.set(mensaje);
      this.aplicar(e);
    };
  }

  protected cargar(): void {
    this.cargando.set(true);
    this.servicio
      .mes(this.proyecto().id, this.mes())
      .subscribe({ next: this.listo(), error: this.fallo('No pudimos cargar tu diario.') });
  }

  protected moverMes(n: number): void {
    this.mes.set(moverMes(this.mes(), n));
    this.aviso.set('');
    this.cargar();
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
      })
      .subscribe({
        next: (e) => {
          this.gValor.set('');
          this.gDescripcion.set('');
          this.gClase.set(null);
          this.mes.set(mesDe(this.gFecha()));
          this.listo('Anotado.')(e);
        },
        error: this.fallo('No pudimos anotarlo.'),
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

  // ── Del mes ──
  private modoDe(r: RubroMes): Modo {
    if (r.valor && r.cerebral === 0) return 'emocional';
    if (r.cerebral && r.cerebral < r.valor) return 'mixto';
    return 'cerebral';
  }

  protected rubrosDe(categoria: string): { r: RubroMes; i: number }[] {
    return this.borrador()
      .map((r, i) => ({ r, i }))
      .filter((x) => x.r.categoria === categoria);
  }

  protected totalDe(categoria: string): number {
    return this.rubrosDe(categoria).reduce((s, x) => s + x.r.valor, 0);
  }

  private cambiar(i: number, cambio: Partial<RubroMes>): void {
    this.borrador.update((l) =>
      l.map((r, j) => {
        if (j !== i) return r;
        const n = { ...r, ...cambio };
        n.cerebral = Math.min(n.cerebral, n.valor);
        n.emocional = n.valor - n.cerebral;
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

  protected quitarRubro(i: number): void {
    this.borrador.update((l) => l.filter((_, j) => j !== i));
    this.modos.update((l) => l.filter((_, j) => j !== i));
    this.cambiado.set(true);
  }

  protected agregarRubro(categoria: string): void {
    const nombre = (this.nuevoRubro()[categoria] ?? '').trim();
    if (!nombre) return;
    this.borrador.update((l) => [...l, { categoria, nombre, valor: 0, cerebral: 0, emocional: 0 }]);
    this.modos.update((l) => [...l, 'cerebral']);
    this.nuevoRubro.update((n) => ({ ...n, [categoria]: '' }));
    this.cambiado.set(true);
  }

  protected escribirNuevo(categoria: string, texto: string): void {
    this.nuevoRubro.update((n) => ({ ...n, [categoria]: texto }));
  }

  protected guardarMes(): void {
    this.guardando.set(true);
    this.servicio
      .guardarRubros(
        this.proyecto().id,
        this.mes(),
        this.borrador().map(({ categoria, nombre, valor, cerebral }) => ({
          categoria,
          nombre,
          valor,
          cerebral,
        })),
      )
      .subscribe({
        next: this.listo(`Guardados los gastos de ${this.tituloMes()}.`),
        error: this.fallo('No pudimos guardar los gastos del mes.'),
      });
  }

  protected deDonde(): string {
    const de = this.estado()?.rubros_de ?? '';
    if (de === 'guardado') return '';
    if (de === 'plantilla')
      return 'Esta es la lista del libro en blanco: pon el valor de lo que pagas cada mes y guarda.';
    const [a, m] = de.split('-').map(Number);
    return `Viene copiado de ${MESES[m - 1]} ${a}: ajusta lo que cambió y guarda.`;
  }

  // ── Anuales y hormiga ──
  protected crearNoMensual(): void {
    if (!this.nNombre().trim() || !aPesos(this.nValor()) || !this.nClase()) return;
    this.guardando.set(true);
    this.servicio
      .crear(
        this.proyecto().id,
        'no-mensuales',
        {
          nombre: this.nNombre().trim(),
          valor: aPesos(this.nValor()),
          periodicidad: this.nPeriodo(),
          mes_pago: this.nMes(),
          clase: this.nClase(),
        },
        this.mes(),
      )
      .subscribe({
        next: (e) => {
          this.nNombre.set('');
          this.nValor.set('');
          this.nClase.set(null);
          this.listo()(e);
        },
        error: this.fallo('No pudimos guardarlo.'),
      });
  }

  protected crearHormiga(): void {
    if (!this.hNombre().trim() || !aPesos(this.hValor()) || !this.hClase()) return;
    this.guardando.set(true);
    this.servicio
      .crear(
        this.proyecto().id,
        'hormiga',
        {
          nombre: this.hNombre().trim(),
          valor_dia: aPesos(this.hValor()),
          dias_mes: Math.min(31, Math.max(1, Number(this.hDias()) || 30)),
          clase: this.hClase(),
        },
        this.mes(),
      )
      .subscribe({
        next: (e) => {
          this.hNombre.set('');
          this.hValor.set('');
          this.hClase.set(null);
          this.listo()(e);
        },
        error: this.fallo('No pudimos guardarlo.'),
      });
  }

  protected quitar(lista: 'no-mensuales' | 'hormiga', id: number): void {
    this.servicio
      .borrar(this.proyecto().id, lista, id, this.mes())
      .subscribe({ next: this.listo(), error: this.fallo('No pudimos quitarlo.') });
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

  protected leer(e: Event): string {
    return (e.target as HTMLInputElement).value;
  }
}
