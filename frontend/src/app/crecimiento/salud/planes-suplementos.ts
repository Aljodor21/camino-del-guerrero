import {
  ChangeDetectionStrategy,
  Component,
  computed,
  inject,
  input,
  output,
  signal,
} from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ButtonModule } from 'primeng/button';
import { InputTextModule } from 'primeng/inputtext';
import { ToggleSwitchModule } from 'primeng/toggleswitch';

import { ProyectoCrecimiento } from '../../core/models/crecimiento.model';
import { EstadoSalud, PlanSuplemento, PlanSuplementoEstado } from '../../core/models/salud.model';
import { CrecimientoService } from '../../core/services/crecimiento';
import { SaludService } from '../../core/services/salud';
import { clasesChip } from '../../shared/chip';
import { mensajeError } from '../../shared/errores';
import { formatearFecha, hoyISO } from '../../shared/fechas';

/** Los días de la semana como los cuenta el servidor (lunes = 0). */
const DIAS = [
  { n: 0, corto: 'L', largo: 'lunes' },
  { n: 1, corto: 'M', largo: 'martes' },
  { n: 2, corto: 'X', largo: 'miércoles' },
  { n: 3, corto: 'J', largo: 'jueves' },
  { n: 4, corto: 'V', largo: 'viernes' },
  { n: 5, corto: 'S', largo: 'sábado' },
  { n: 6, corto: 'D', largo: 'domingo' },
];
const TODOS = DIAS.map((d) => d.n);

/**
 * Los suplementos con su plan (qué, cuánto, qué días, a qué horas y cuánto dura el tratamiento) y las tomas
 * de hoy con «Ya lo tomé». Los avisos salen a cada hora del plan; aquí se arma y se marca.
 */
@Component({
  selector: 'app-planes-suplementos',
  templateUrl: './planes-suplementos.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [ReactiveFormsModule, ButtonModule, InputTextModule, ToggleSwitchModule],
})
export class PlanesSuplementos {
  readonly proyecto = input.required<ProyectoCrecimiento>();
  readonly estado = input.required<EstadoSalud>();
  readonly cambio = output<EstadoSalud>();

  private salud = inject(SaludService);
  private crecimiento = inject(CrecimientoService);
  private fb = inject(FormBuilder);

  protected diasSemana = DIAS;
  protected clasesChip = clasesChip;
  protected fecha = (iso: string) => formatearFecha(iso, 'corta');

  /** El plan que se está editando: su id, «nuevo» o ninguno. */
  protected editando = signal<string | null>(null);
  protected confirmarBorrar = signal<string | null>(null);
  protected guardando = signal(false);
  protected error = signal('');
  protected dias = signal<number[]>(TODOS);
  protected horas = signal<string[]>(['08:00']);
  protected nuevaHora = signal('20:00');

  protected planes = computed(() => this.estado().planes ?? []);
  protected deHoy = computed(() => this.estado().de_hoy ?? []);

  protected form = this.fb.nonNullable.group({
    nombre: ['', [Validators.required, Validators.maxLength(60)]],
    cantidad: ['', [Validators.required, Validators.maxLength(40)]],
    inicio: [hoyISO(), Validators.required],
    con_fin: [true],
    duracion_dias: [30, [Validators.min(1), Validators.max(730)]],
    nota: ['', [Validators.maxLength(200)]],
    avisar: [true],
  });

  protected diasTexto(p: PlanSuplemento): string {
    if (p.dias.length === 7) return 'Todos los días';
    return p.dias.map((n) => DIAS[n].largo).join(', ');
  }

  protected abrir(p: PlanSuplementoEstado | null): void {
    this.error.set('');
    this.confirmarBorrar.set(null);
    this.editando.set(p?.id ?? 'nuevo');
    this.dias.set(p ? [...p.dias] : TODOS);
    this.horas.set(p ? [...p.horas] : ['08:00']);
    this.form.reset({
      nombre: p?.nombre ?? '',
      cantidad: p?.cantidad ?? '',
      inicio: p?.inicio ?? hoyISO(),
      con_fin: p ? p.duracion_dias !== null : true,
      duracion_dias: p?.duracion_dias ?? 30,
      nota: p?.nota ?? '',
      avisar: p?.avisar ?? true,
    });
  }

  protected cerrar(): void {
    this.editando.set(null);
  }

  protected alternarDia(n: number): void {
    this.dias.update((d) => (d.includes(n) ? d.filter((x) => x !== n) : [...d, n].sort()));
  }

  protected todosLosDias(): void {
    this.dias.set(TODOS);
  }

  protected agregarHora(): void {
    const h = this.nuevaHora();
    if (!h || this.horas().includes(h) || this.horas().length >= 6) return;
    this.horas.update((l) => [...l, h].sort());
  }

  protected quitarHora(h: string): void {
    this.horas.update((l) => l.filter((x) => x !== h));
  }

  protected puedeGuardar = computed(() => this.dias().length > 0 && this.horas().length > 0);

  protected guardar(): void {
    if (this.form.invalid || !this.puedeGuardar()) return;
    const v = this.form.getRawValue();
    const id = this.editando();
    const plan: PlanSuplemento = {
      id: id && id !== 'nuevo' ? id : '',
      nombre: v.nombre,
      cantidad: v.cantidad,
      dias: this.dias(),
      horas: this.horas(),
      inicio: v.inicio,
      duracion_dias: v.con_fin ? v.duracion_dias : null,
      nota: v.nota,
      avisar: v.avisar,
    };
    const lista = this.planes().map((p) => this.soloPlan(p));
    const i = lista.findIndex((p) => p.id === plan.id);
    if (i >= 0) lista[i] = plan;
    else lista.push(plan);
    this.guardarPlanes(lista, () => this.editando.set(null));
  }

  /** Un suplemento que quedó sin aviso se enciende desde la lista, sin abrirlo. */
  protected activarAviso(p: PlanSuplementoEstado): void {
    this.guardarPlanes(
      this.planes().map((x) => ({ ...this.soloPlan(x), avisar: x.id === p.id || x.avisar })),
      () => undefined,
    );
  }

  protected borrar(p: PlanSuplementoEstado): void {
    if (this.confirmarBorrar() !== p.id) {
      this.confirmarBorrar.set(p.id);
      return;
    }
    this.guardarPlanes(
      this.planes()
        .filter((x) => x.id !== p.id)
        .map((x) => this.soloPlan(x)),
      () => this.confirmarBorrar.set(null),
    );
  }

  protected atrasadas = computed(() => this.estado().atrasadas ?? []);
  protected dia = (iso: string) => formatearFecha(iso, 'dia');

  /** Desde «Hoy te toca», o una de los últimos días que quedó sin anotar (`fecha`). */
  protected tomar(clave: string, fecha?: string): void {
    this.guardando.set(true);
    this.salud.anotar(this.proyecto().id, { plan: clave, ...(fecha ? { fecha } : {}) }).subscribe({
      next: (e) => {
        this.guardando.set(false);
        this.cambio.emit(e);
      },
      error: (e) => this.fallo(e, 'No pudimos anotarlo.'),
    });
  }

  /** Lo que se guarda de un plan (sin lo que calcula el servidor). */
  private soloPlan(p: PlanSuplementoEstado): PlanSuplemento {
    return {
      id: p.id,
      nombre: p.nombre,
      cantidad: p.cantidad,
      dias: p.dias,
      horas: p.horas,
      inicio: p.inicio,
      duracion_dias: p.duracion_dias,
      nota: p.nota,
      avisar: p.avisar,
    };
  }

  private guardarPlanes(planes: PlanSuplemento[], despues: () => void): void {
    this.guardando.set(true);
    this.error.set('');
    this.crecimiento.actualizarProyecto(this.proyecto().id, { datos: { planes } }).subscribe({
      next: () =>
        this.salud.cargar(this.proyecto().id).subscribe({
          next: (e) => {
            this.guardando.set(false);
            despues();
            this.cambio.emit(e);
          },
          error: (e) => this.fallo(e, 'No pudimos cargar tus suplementos.'),
        }),
      error: (e) => this.fallo(e, 'No pudimos guardar el suplemento.'),
    });
  }

  private fallo(e: unknown, respaldo: string): void {
    this.guardando.set(false);
    this.error.set(mensajeError(e, respaldo));
  }

  protected leer(e: Event): string {
    return (e.target as HTMLInputElement).value;
  }
}
