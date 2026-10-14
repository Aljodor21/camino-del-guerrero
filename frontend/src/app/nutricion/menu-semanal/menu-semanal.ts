import {
  ChangeDetectionStrategy,
  Component,
  OnInit,
  computed,
  inject,
  signal,
} from '@angular/core';
import { Observable } from 'rxjs';
import { ButtonModule } from 'primeng/button';
import { DialogModule } from 'primeng/dialog';
import { InputTextModule } from 'primeng/inputtext';
import { MessageModule } from 'primeng/message';
import { ProgressSpinnerModule } from 'primeng/progressspinner';

import { RouterLink } from '@angular/router';

import { ComidasService } from '../../core/services/comidas';
import { RegistroComida } from '../../core/models/comidas.model';
import { AvisosService } from '../../core/services/avisos';
import { MenuService } from '../../core/services/menu';
import {
  ComidaMenu,
  ComponenteComida,
  MotivoCambio,
  OpcionIntercambio,
  SuplementoEnComida,
} from '../../core/models/minuta.model';
import {
  GRUPOS_MINUTA,
  MOTIVOS_CAMBIO,
  ORDEN_GRUPOS,
  porcionesDe,
} from '../../core/constants/nutricion';
import { clasesChip } from '../../shared/chip';
import { mensajeError } from '../../shared/errores';
import { fechaLocal, formatearFecha, formatearHora, hoyISO, sumarDias } from '../../shared/fechas';
import { Anillo } from '../../shared/anillo/anillo';
import { Guerrero } from '../../shared/guerrero/guerrero';

type Paso = 'inicio' | 'alimento' | 'intercambios' | 'otra';

function lunesDe(iso: string): string {
  const dia = fechaLocal(iso).getDay();
  return sumarDias(iso, dia === 0 ? -6 : 1 - dia);
}

/** El menú de la semana: solo alimentos de la lista de intercambios en las porciones de la minuta. */
import { Ayuda } from '../../shared/ayuda/ayuda';

@Component({
  selector: 'app-menu-semanal',
  templateUrl: './menu-semanal.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    RouterLink,
    Anillo,
    Guerrero,
    Ayuda,
    ButtonModule,
    DialogModule,
    InputTextModule,
    MessageModule,
    ProgressSpinnerModule,
  ],
  styles: `
    .nodo-hecho {
      animation: nodo-pop 0.5s cubic-bezier(0.3, 1.6, 0.5, 1);
    }
    .nodo-ahora {
      animation: nodo-pulso 2s ease-in-out infinite;
    }
    .detalle-comida {
      animation: detalle-entra 0.25s ease-out;
    }
    @keyframes nodo-pop {
      0% {
        transform: scale(0.4);
      }
      100% {
        transform: scale(1);
      }
    }
    @keyframes nodo-pulso {
      0%,
      100% {
        box-shadow: 0 0 0 0 rgb(220 38 38 / 0.45);
      }
      50% {
        box-shadow: 0 0 0 8px rgb(220 38 38 / 0);
      }
    }
    @keyframes detalle-entra {
      from {
        opacity: 0;
        transform: translateY(-4px);
      }
    }
    @media (prefers-reduced-motion: reduce) {
      .nodo-hecho,
      .nodo-ahora,
      .detalle-comida {
        animation: none;
      }
    }
  `,
})
export class MenuSemanal implements OnInit {
  protected servicio = inject(MenuService);
  private contadas = inject(ComidasService);
  /** Lo que ya se contó de la semana que se ve. */
  protected registros = signal<RegistroComida[]>([]);

  protected motivos = MOTIVOS_CAMBIO;
  protected porcionesDe = porcionesDe;
  protected claseOpcion =
    'w-full text-left flex flex-col gap-0.5 rounded-xl border border-gray-200 dark:border-dark-700 px-4 py-3 hover:border-guerrero-red focus-visible:outline-2 focus-visible:outline-guerrero-red disabled:opacity-50';
  protected clasesChip = clasesChip;
  protected formatearFecha = formatearFecha;

  private semanaActual = lunesDe(hoyISO());
  protected semana = signal(this.semanaActual);
  protected hoy = hoyISO();
  protected formatearHora = formatearHora;
  private avisos = inject(AvisosService);
  /** A qué hora come cada tiempo del plan. */
  protected horas = signal<Record<string, string>>({});
  /** Las que la persona abrió, y las que cerró aunque sea la que toca ahora. */
  protected abiertas = signal<number[]>([]);
  protected cerradas = signal<number[]>([]);
  protected diaSeleccionado = signal(hoyISO());
  protected cargando = signal(true);
  protected armando = signal(false);
  protected error = signal('');
  protected confirmarRearmar = signal(false);

  protected esSemanaActual = computed(() => this.semana() === this.semanaActual);
  protected esSiguiente = computed(() => this.semana() === sumarDias(this.semanaActual, 7));
  protected tituloSemana = computed(() => {
    const desde = this.semana();
    return `${formatearFecha(desde, 'grafica')} – ${formatearFecha(sumarDias(desde, 6), 'grafica')}`;
  });
  protected dias = computed(() =>
    Array.from({ length: 7 }, (_, i) => {
      const iso = sumarDias(this.semana(), i);
      const fecha = fechaLocal(iso);
      return {
        iso,
        nombre: fecha.toLocaleDateString('es-CO', { weekday: 'short' }).replace('.', ''),
        numero: fecha.getDate(),
        hoy: iso === hoyISO(),
      };
    }),
  );
  protected comidas = computed(() =>
    (this.servicio.menu()?.comidas ?? []).filter((c) => c.fecha === this.diaSeleccionado()),
  );
  /** De cada comida del día que se ve: su registro, si ya se contó, y cuánto de lo pedido se comió. */
  protected avance = computed(() => {
    const dia = this.diaSeleccionado();
    const delDia = this.registros().filter((r) => r.fecha === dia);
    const porTiempo = new Map(
      delDia.map((r) => {
        const g = Object.values(r.grupos ?? {});
        const pedido = g.reduce((s, x) => s + (x?.pedido ?? 0), 0);
        const comido = g.reduce((s, x) => s + (x?.comido ?? 0), 0);
        return [r.tiempo, pedido ? Math.round((comido / pedido) * 100) : 100] as const;
      }),
    );
    const todas = this.comidas();
    const hechas = todas.filter((c) => porTiempo.has(c.tiempo)).length;
    const valores = [...porTiempo.values()];
    return {
      porTiempo,
      hechas,
      total: todas.length,
      // Lo que va del día: cada comida contada suma su porcentaje y las que faltan, cero.
      porcentaje: todas.length
        ? Math.round(valores.reduce((a, b) => a + b, 0) / todas.length)
        : null,
      comido: valores.length
        ? Math.round(valores.reduce((a, b) => a + b, 0) / valores.length)
        : null,
      puedeContar: dia <= hoyISO(),
    };
  });
  /** La comida que sigue hoy: la primera que aún no se cuenta. */
  protected siguiente = computed(() =>
    this.diaSeleccionado() === hoyISO()
      ? (this.comidas().find((c) => !this.avance().porTiempo.has(c.tiempo)) ?? null)
      : null,
  );

  protected alternar(id: number, abierta: boolean): void {
    if (abierta) {
      this.abiertas.update((l) => l.filter((x) => x !== id));
      this.cerradas.update((l) => [...l, id]);
    } else {
      this.cerradas.update((l) => l.filter((x) => x !== id));
      this.abiertas.update((l) => [...l, id]);
    }
  }

  protected delDia = computed(() =>
    (this.servicio.menu()?.durante_el_dia ?? []).map((p) => porcionesDe(p.grupo, p.porciones)),
  );

  // ── "No puedo con esta comida" ─────────────────────────────────────
  protected comida = signal<ComidaMenu | null>(null);
  protected paso = signal<Paso>('inicio');
  protected componente = signal<ComponenteComida | null>(null);
  protected opciones = signal<OpcionIntercambio[]>([]);
  protected filtro = signal('');
  protected motivo = signal<MotivoCambio | null>(null);
  protected trabajando = signal(false);
  protected errorCambio = signal('');
  protected opcionesFiltradas = computed(() => {
    const texto = this.normalizar(this.filtro());
    return this.opciones().filter((o) => this.normalizar(o.nombre).includes(texto));
  });
  protected componentesCambiables = computed(() =>
    (this.comida()?.componentes ?? []).filter((c) => c.grupo !== 'libres'),
  );

  ngOnInit(): void {
    this.cargar();
  }

  /** Carga la semana; la actual o la siguiente se arman solas si aún no existen. */
  protected cargar(): void {
    this.cargando.set(true);
    this.error.set('');
    this.avisos.cargarHabitos().subscribe({
      next: (h) =>
        this.horas.set(Object.fromEntries(h.tiempos_comida.map((x) => [x.tiempo, x.hora]))),
      error: () => undefined,
    });
    this.contadas.registros(this.semana(), sumarDias(this.semana(), 6)).subscribe({
      next: (r) => this.registros.set(r),
      error: () => this.registros.set([]),
    });
    this.servicio.cargar(this.semana()).subscribe({
      next: (menu) => {
        this.cargando.set(false);
        if (!menu && (this.esSemanaActual() || this.esSiguiente())) this.armar();
      },
      error: (err) => {
        this.error.set(mensajeError(err, 'No pudimos cargar tu menú.'));
        this.cargando.set(false);
      },
    });
  }

  protected armar(): void {
    this.confirmarRearmar.set(false);
    this.armando.set(true);
    this.error.set('');
    this.servicio.generar(this.semana()).subscribe({
      next: () => this.armando.set(false),
      error: (err) => {
        this.error.set(mensajeError(err, 'No pudimos armar tu menú. Intenta de nuevo.'));
        this.armando.set(false);
      },
    });
  }

  protected moverSemana(semanas: number): void {
    this.semana.update((s) => sumarDias(s, semanas * 7));
    const hoy = hoyISO();
    const dentro = hoy >= this.semana() && hoy <= sumarDias(this.semana(), 6);
    this.diaSeleccionado.set(dentro ? hoy : this.semana());
    this.cargar();
  }

  protected grupo(nombre: string): string {
    return GRUPOS_MINUTA[nombre as keyof typeof GRUPOS_MINUTA] ?? nombre;
  }

  /** "3 scoops, en lugar de 1 porción de lácteos". */
  protected reemplazoTexto(s: SuplementoEnComida): string {
    const partes = ORDEN_GRUPOS.filter((g) => s.reemplaza[g]).map((g) =>
      porcionesDe(g, s.reemplaza[g]!),
    );
    const scoops = s.scoops
      ? `${s.scoops.toLocaleString('es-CO')} ${s.scoops === 1 ? 'scoop' : 'scoops'}, `
      : '';
    return scoops + (partes.length ? `en lugar de ${partes.join(' y ')}` : 'además de la comida');
  }

  // ── Diálogo de cambio ─────────────────────────────────────────────
  protected abrirCambio(c: ComidaMenu): void {
    this.comida.set(c);
    this.paso.set('inicio');
    this.componente.set(null);
    this.motivo.set(null);
    this.filtro.set('');
    this.errorCambio.set('');
  }

  protected cerrarCambio(): void {
    this.comida.set(null);
  }

  protected elegirComponente(c: ComponenteComida): void {
    const comida = this.comida();
    if (!comida) return;
    this.componente.set(c);
    this.opciones.set([]);
    this.filtro.set('');
    this.paso.set('intercambios');
    this.trabajando.set(true);
    this.servicio.opciones(comida.id, c.id).subscribe({
      next: (opciones) => {
        this.opciones.set(opciones);
        this.trabajando.set(false);
      },
      error: (err) => {
        this.errorCambio.set(mensajeError(err, 'No pudimos traer los intercambios.'));
        this.trabajando.set(false);
      },
    });
  }

  protected usarIntercambio(o: OpcionIntercambio): void {
    const comida = this.comida();
    const c = this.componente();
    if (comida && c) this.ejecutar(this.servicio.cambiarAlimento(comida.id, c.id, o.id));
  }

  protected pedirOtra(): void {
    const comida = this.comida();
    const motivo = this.motivo();
    if (comida && motivo) this.ejecutar(this.servicio.sugerir(comida.id, motivo));
  }

  protected alternarPorFuera(): void {
    const comida = this.comida();
    if (comida) this.ejecutar(this.servicio.porFuera(comida.id, !comida.por_fuera));
  }

  private ejecutar(peticion: Observable<unknown>): void {
    this.trabajando.set(true);
    this.errorCambio.set('');
    peticion.subscribe({
      next: () => {
        this.trabajando.set(false);
        this.cerrarCambio();
      },
      error: (err) => {
        this.errorCambio.set(mensajeError(err, 'No pudimos cambiar la comida.'));
        this.trabajando.set(false);
      },
    });
  }

  private normalizar(texto: string): string {
    return texto.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
  }
}
