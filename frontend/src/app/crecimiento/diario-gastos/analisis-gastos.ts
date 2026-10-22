import { ChangeDetectionStrategy, Component, computed, input, output, signal } from '@angular/core';
import { NgTemplateOutlet } from '@angular/common';

import { ClaseGasto, EstadoDiario, GastoAnotado } from '../../core/models/diario-gastos.model';
import { clasesChip } from '../../shared/chip';
import { formatearFecha, hoyISO } from '../../shared/fechas';

type Clase = 'todo' | ClaseGasto;
/** Con qué se pagó: todo, sin tarjeta, con cualquier tarjeta o con una («Visa ·1234»). */
type Medio = 'todo' | 'registro' | 'tarjeta' | string;
type Orden = 'valor' | 'fecha';

const PESOS = new Intl.NumberFormat('es-CO', {
  style: 'currency',
  currency: 'COP',
  maximumFractionDigits: 0,
});

/** Las marcas del eje de los días: cada semana. */
const MARCAS = [1, 8, 15, 22, 29];

function suma(l: GastoAnotado[]): number {
  return l.reduce((s, g) => s + g.valor, 0);
}

/** «Domicilio », «domicilio» y «Domicilio» son lo mismo. */
function clave(texto: string): string {
  return texto.trim().toLocaleLowerCase('es-CO');
}

/**
 * El registro del mes mirado de cerca: cifras, el gasto día por día y cada categoría con lo que se gastó en
 * ella (qué, cuándo, con qué y lo que más se repite). Todo se calcula aquí con lo que ya trae el diario, y los
 * filtros (cerebral o emocional, con o sin tarjeta) mandan sobre todo lo de abajo.
 */
@Component({
  selector: 'app-analisis-gastos',
  templateUrl: './analisis-gastos.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [NgTemplateOutlet],
})
export class AnalisisGastos {
  readonly estado = input.required<EstadoDiario>();
  /** Pasar un gasto a otra categoría: lo guarda el diario y todo se recalcula con lo que responde. */
  readonly cambiarCategoria = output<{ gasto: GastoAnotado; categoria: string }>();

  protected clasesChip = clasesChip;
  protected marcas = MARCAS;
  protected hoy = hoyISO();

  protected clase = signal<Clase>('todo');
  protected medio = signal<Medio>('todo');
  protected abierta = signal<string | null>(null);
  protected orden = signal<Orden>('valor');
  protected dia = signal<string | null>(null);

  protected clases: { id: Clase; label: string }[] = [
    { id: 'todo', label: 'Todo' },
    { id: 'cerebral', label: 'Cerebral' },
    { id: 'emocional', label: 'Emocional' },
  ];

  /** Las tarjetas con las que se compró algo este mes (también las retiradas). */
  protected tarjetas = computed(() => [
    ...new Set(
      this.estado()
        .registro.map((g) => g.tarjeta)
        .filter(Boolean),
    ),
  ]);

  protected medios = computed<{ id: Medio; label: string }[]>(() => {
    const tarjetas = this.tarjetas();
    if (!tarjetas.length) return [];
    return [
      { id: 'todo', label: 'Con y sin tarjeta' },
      { id: 'registro', label: 'Sin tarjeta' },
      ...(tarjetas.length > 1
        ? [{ id: 'tarjeta', label: 'Con tarjeta' }, ...tarjetas.map((t) => ({ id: t, label: t }))]
        : [{ id: 'tarjeta', label: 'Con tarjeta' }]),
    ];
  });

  protected gastos = computed(() => {
    const c = this.clase();
    const m = this.medio();
    return this.estado().registro.filter(
      (g) =>
        (c === 'todo' || g.clase === c) &&
        (m === 'todo' ||
          (m === 'registro' && !g.tarjeta) ||
          (m === 'tarjeta' && !!g.tarjeta) ||
          g.tarjeta === m),
    );
  });

  /** Lo planeado solo se compara cuando se mira todo lo pagado (el plan no sabe con qué se paga). */
  private planDe = computed(() => {
    const c = this.clase();
    const de = (r: EstadoDiario['rubros'][number]) =>
      c === 'todo' ? r.mensual : c === 'cerebral' ? r.mensual_cerebral : r.mensual_emocional;
    return (categoria?: string) =>
      this.medio() === 'todo'
        ? this.estado()
            .rubros.filter((r) => !categoria || r.categoria === categoria)
            .reduce((s, r) => s + de(r), 0)
        : 0;
  });

  private mes = computed(() => {
    const [anio, mes, dia] = this.hoy.split('-').map(Number);
    return { anio, mes, hoy: dia, dias: new Date(anio, mes, 0).getDate() };
  });

  protected cifras = computed(() => {
    const gastos = this.gastos();
    const { hoy, dias } = this.mes();
    const total = suma(gastos);
    // Desde que empezó el diario este mes (o desde el primer gasto anotado, si es antes), hasta hoy.
    const primero = Math.min(
      hoy - Math.max(1, this.estado().resumen.dias_transcurridos) + 1,
      ...this.estado().registro.map((g) => Number(g.fecha.slice(8))),
    );
    const porDia = new Array<number>(hoy - primero + 1).fill(0);
    for (const g of gastos) {
      const i = Number(g.fecha.slice(8)) - primero;
      if (i >= 0 && i < porDia.length) porDia[i] += g.valor;
    }
    // El día típico es la mediana: un pago grande (el arriendo) no se multiplica por los días que faltan.
    const ordenados = [...porDia].sort((a, b) => a - b);
    const medio = Math.floor(ordenados.length / 2);
    const tipico = Math.round(
      ordenados.length % 2 ? ordenados[medio] : (ordenados[medio - 1] + ordenados[medio]) / 2,
    );
    const plan = this.planDe()();
    const mayor = gastos.reduce<GastoAnotado | null>(
      (m, g) => (!m || g.valor > m.valor ? g : m),
      null,
    );
    return {
      total,
      n: gastos.length,
      promedio: Math.round(total / porDia.length),
      tipico,
      proyeccion: total + tipico * (dias - hoy),
      plan,
      mayor,
      emocional: suma(gastos.filter((g) => g.clase === 'emocional')),
      registro: suma(gastos.filter((g) => !g.tarjeta)),
      tarjeta: suma(gastos.filter((g) => g.tarjeta)),
      porTarjeta: this.tarjetas()
        .map((t) => ({ nombre: t, valor: suma(gastos.filter((g) => g.tarjeta === t)) }))
        .filter((t) => t.valor),
    };
  });

  /** Cada día del mes con lo cerebral y lo emocional; los que no han llegado quedan vacíos. */
  protected dias = computed(() => {
    const { anio, mes, hoy, dias } = this.mes();
    const porFecha = new Map<string, GastoAnotado[]>();
    for (const g of this.gastos()) porFecha.set(g.fecha, [...(porFecha.get(g.fecha) ?? []), g]);
    const lista = Array.from({ length: dias }, (_, i) => {
      const iso = `${anio}-${String(mes).padStart(2, '0')}-${String(i + 1).padStart(2, '0')}`;
      const gastos = porFecha.get(iso) ?? [];
      const cerebral = suma(gastos.filter((g) => g.clase === 'cerebral'));
      const emocional = suma(gastos.filter((g) => g.clase === 'emocional'));
      return {
        iso,
        n: i + 1,
        gastos,
        cerebral,
        emocional,
        total: cerebral + emocional,
        futuro: i + 1 > hoy,
      };
    });
    const planDia = Math.round(this.cifras().plan / dias);
    const tope = Math.max(planDia, ...lista.map((d) => d.total)) || 1;
    return { lista, tope, planDia };
  });

  protected diaElegido = computed(
    () => this.dias().lista.find((d) => d.iso === this.dia()) ?? null,
  );

  protected categorias = computed(() => {
    const e = this.estado();
    const gastos = this.gastos();
    const total = suma(gastos);
    const plan = this.planDe();
    const lista = e.categorias
      .map((c) => {
        const deAqui = gastos.filter((g) => g.categoria === c.id);
        const anotado = suma(deAqui);
        const grupos = new Map<string, { descripcion: string; veces: number; valor: number }>();
        for (const g of deAqui) {
          const k = clave(g.descripcion);
          const x = grupos.get(k) ?? { descripcion: g.descripcion.trim(), veces: 0, valor: 0 };
          grupos.set(k, { ...x, veces: x.veces + 1, valor: x.valor + g.valor });
        }
        return {
          id: c.id,
          nombre: c.nombre,
          plan: plan(c.id),
          anotado,
          parte: total ? Math.round((anotado / total) * 100) : 0,
          cerebral: suma(deAqui.filter((g) => g.clase === 'cerebral')),
          emocional: suma(deAqui.filter((g) => g.clase === 'emocional')),
          tarjeta: suma(deAqui.filter((g) => g.tarjeta)),
          gastos: deAqui,
          repetidos: [...grupos.values()]
            .filter((x) => x.veces > 1)
            .sort((a, b) => b.valor - a.valor)
            .slice(0, 3),
        };
      })
      .filter((c) => c.plan || c.anotado)
      .sort((a, b) => b.anotado - a.anotado || b.plan - a.plan);
    const escala = Math.max(1, ...lista.map((c) => Math.max(c.anotado, c.plan)));
    return { lista, escala };
  });

  protected mayores = computed(() =>
    [...this.gastos()].sort((a, b) => b.valor - a.valor).slice(0, 5),
  );

  protected ordenados(gastos: GastoAnotado[]): GastoAnotado[] {
    return [...gastos].sort((a, b) =>
      this.orden() === 'valor' ? b.valor - a.valor : b.fecha.localeCompare(a.fecha) || b.id - a.id,
    );
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

  protected alto(valor: number): number {
    return (valor / this.dias().tope) * 100;
  }

  protected ancho(valor: number): number {
    return (valor / this.categorias().escala) * 100;
  }

  protected moverA(gasto: GastoAnotado, e: Event): void {
    const categoria = (e.target as HTMLSelectElement).value;
    if (categoria !== gasto.categoria) this.cambiarCategoria.emit({ gasto, categoria });
  }

  protected abrir(id: string): void {
    this.abierta.update((a) => (a === id ? null : id));
  }

  /** Tocar el mismo día otra vez lo suelta. */
  protected elegirDia(iso: string): void {
    this.dia.update((d) => (d === iso ? null : iso));
  }
}
