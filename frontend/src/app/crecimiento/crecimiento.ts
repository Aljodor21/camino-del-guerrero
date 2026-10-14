import {
  ChangeDetectionStrategy,
  Component,
  OnInit,
  Type,
  computed,
  inject,
  signal,
} from '@angular/core';
import { NgComponentOutlet } from '@angular/common';
import { ActivatedRoute, Router } from '@angular/router';
import { map, switchMap } from 'rxjs';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ButtonModule } from 'primeng/button';
import { InputTextModule } from 'primeng/inputtext';
import { MessageModule } from 'primeng/message';
import { ProgressSpinnerModule } from 'primeng/progressspinner';
import { TextareaModule } from 'primeng/textarea';

import {
  AreaCrecimiento,
  EstadoProyecto,
  FuenteProceso,
  NotaCrecimiento,
  ProcesoCrecimiento,
  ProgramaCrecimiento,
  ProyectoCrecimiento,
} from '../core/models/crecimiento.model';
import { PANTALLAS } from './pantallas';
import { CrecimientoService } from '../core/services/crecimiento';
import { mensajeError } from '../shared/errores';
import { formatearFecha } from '../shared/fechas';
import { Portada } from '../shared/portada/portada';
import { QueEs } from '../shared/que-es/que-es';

const FUENTES: { id: FuenteProceso; label: string }[] = [
  { id: 'libro', label: 'Libro' },
  { id: 'curso', label: 'Curso' },
  { id: 'mentor', label: 'Mentor' },
  { id: 'propio', label: 'Propio' },
];

/** Cuánto lleva un proyecto libre: lo marca la persona. */
const AVANCES = [0, 25, 50, 75, 100];

type Formulario = 'area' | 'proceso' | null;

/**
 * Crecimiento personal: cada persona arma sus áreas («Educación financiera»), dentro lleva procesos
 * que salen de una fuente (un libro y su autor), y cada proceso tiene sus proyectos y notas.
 */
@Component({
  selector: 'app-crecimiento',
  templateUrl: './crecimiento.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    NgComponentOutlet,
    ReactiveFormsModule,
    ButtonModule,
    InputTextModule,
    MessageModule,
    ProgressSpinnerModule,
    TextareaModule,
    Portada,
    QueEs,
  ],
})
export class Crecimiento implements OnInit {
  private servicio = inject(CrecimientoService);
  private fb = inject(NonNullableFormBuilder);
  private ruta = inject(ActivatedRoute);
  private router = inject(Router);

  protected fuentes = FUENTES;
  protected avances = AVANCES;
  protected formatearFecha = formatearFecha;

  protected areas = signal<AreaCrecimiento[]>([]);
  protected procesos = signal<ProcesoCrecimiento[]>([]);
  protected proyectos = signal<ProyectoCrecimiento[]>([]);
  protected notas = signal<NotaCrecimiento[]>([]);

  /** Dónde está la persona: ninguna (las áreas), un área, un proceso o un proyecto. */
  protected area = signal<AreaCrecimiento | null>(null);
  protected proceso = signal<ProcesoCrecimiento | null>(null);
  protected proyecto = signal<ProyectoCrecimiento | null>(null);

  protected cargando = signal(true);
  protected guardando = signal(false);
  protected error = signal('');
  protected formulario = signal<Formulario>(null);
  protected confirmarBorrar = signal(false);

  /** Los programas del catálogo y si el proceso nuevo sale de uno o es propio. */
  protected programas = signal<ProgramaCrecimiento[]>([]);
  /** La pantalla propia del tipo del proyecto abierto (si tiene). */
  protected pantalla = signal<Type<unknown> | null>(null);
  protected entradasPantalla = computed(() => ({ proyecto: this.proyecto() }));

  protected nivel = computed(() =>
    this.proyecto() ? 'proyecto' : this.proceso() ? 'proceso' : this.area() ? 'area' : 'areas',
  );

  protected formArea = this.fb.group({
    nombre: this.fb.control('', [Validators.required, Validators.maxLength(80)]),
  });
  protected formNota = this.fb.group({
    texto: this.fb.control('', [Validators.required, Validators.maxLength(2000)]),
  });

  ngOnInit(): void {
    // Desde un aviso se llega directo a un proyecto (?proyecto=12).
    const id = Number(this.ruta.snapshot.queryParamMap.get('proyecto'));
    if (!id) {
      this.cargarAreas();
      return;
    }
    this.servicio
      .proyecto(id)
      .pipe(
        switchMap((proyecto) =>
          this.servicio
            .proceso(proyecto.proceso)
            .pipe(
              switchMap((proceso) =>
                this.servicio.area(proceso.area).pipe(map((area) => ({ proyecto, proceso, area }))),
              ),
            ),
        ),
      )
      .subscribe({
        next: ({ proyecto, proceso, area }) => {
          this.area.set(area);
          this.proceso.set(proceso);
          this.abrirProyecto(proyecto);
          void this.router.navigate([], { queryParams: {}, replaceUrl: true });
        },
        error: () => this.cargarAreas(),
      });
  }

  private fallo(texto: string): (e: unknown) => void {
    return (e) => {
      this.cargando.set(false);
      this.guardando.set(false);
      this.error.set(mensajeError(e, texto));
    };
  }

  protected cargarAreas(): void {
    this.cargando.set(true);
    this.servicio.areas().subscribe({
      next: (a) => {
        this.areas.set(a);
        this.cargando.set(false);
      },
      error: this.fallo('No pudimos cargar tus áreas.'),
    });
  }

  protected abrirArea(a: AreaCrecimiento): void {
    this.cerrarFormulario();
    this.area.set(a);
    this.cargando.set(true);
    this.servicio.procesos(a.id).subscribe({
      next: (p) => {
        this.procesos.set(p);
        this.cargando.set(false);
      },
      error: this.fallo('No pudimos cargar el área.'),
    });
  }

  protected abrirProceso(p: ProcesoCrecimiento): void {
    this.cerrarFormulario();
    this.proceso.set(p);
    this.cargando.set(true);
    this.servicio.proyectos(p.id).subscribe({
      next: (l) => {
        this.proyectos.set(l);
        this.cargando.set(false);
      },
      error: this.fallo('No pudimos cargar el proceso.'),
    });
  }

  protected abrirProyecto(p: ProyectoCrecimiento): void {
    this.cerrarFormulario();
    this.proyecto.set(p);
    this.pantalla.set(null);
    PANTALLAS[p.tipo]?.().then((c) => this.pantalla.set(c));
    this.formNota.reset();
    this.cargando.set(true);
    this.servicio.notas(p.id).subscribe({
      next: (n) => {
        this.notas.set(n);
        this.cargando.set(false);
      },
      error: this.fallo('No pudimos cargar las notas.'),
    });
  }

  /** Un paso atrás, y se refresca lo que cambió abajo (el avance, los conteos). */
  protected volver(): void {
    this.cerrarFormulario();
    this.error.set('');
    if (this.proyecto()) {
      this.proyecto.set(null);
      const p = this.proceso();
      if (p) this.abrirProceso(p);
    } else if (this.proceso()) {
      this.proceso.set(null);
      const a = this.area();
      if (a) this.abrirArea(a);
    } else {
      this.area.set(null);
      this.cargarAreas();
    }
  }

  protected abrirFormulario(cual: Exclude<Formulario, null>): void {
    this.error.set('');
    this.formulario.set(cual);
    if (cual === 'proceso' && !this.programas().length) {
      this.servicio.programas().subscribe({
        next: (l) => this.programas.set(l),
        error: this.fallo('No pudimos cargar los programas.'),
      });
    }
  }

  /** Un programa del catálogo trae su fuente y sus proyectos ya puestos. */
  protected empezarPrograma(programa: ProgramaCrecimiento): void {
    const area = this.area();
    if (!area) return;
    this.guardando.set(true);
    this.servicio.crearProceso({ area: area.id, programa: programa.id }).subscribe({
      next: (p) => {
        this.guardando.set(false);
        this.cerrarFormulario();
        this.abrirProceso(p);
      },
      error: this.fallo('No pudimos empezar el programa.'),
    });
  }

  protected cerrarFormulario(): void {
    this.formulario.set(null);
    this.confirmarBorrar.set(false);
    this.formArea.reset();
  }

  protected guardarArea(): void {
    if (this.formArea.invalid) return;
    this.guardando.set(true);
    this.servicio.crearArea(this.formArea.controls.nombre.value.trim()).subscribe({
      next: () => {
        this.guardando.set(false);
        this.cerrarFormulario();
        this.cargarAreas();
      },
      error: this.fallo('No pudimos guardar el área.'),
    });
  }

  protected marcarAvance(avance: number): void {
    const p = this.proyecto();
    if (!p) return;
    const estado: EstadoProyecto =
      avance >= 100 ? 'terminado' : avance > 0 ? 'en_curso' : 'por_empezar';
    this.servicio.actualizarProyecto(p.id, { avance, estado }).subscribe({
      next: (n) => this.proyecto.set(n),
      error: this.fallo('No pudimos guardar el avance.'),
    });
  }

  protected guardarNota(): void {
    const p = this.proyecto();
    if (!p || this.formNota.invalid) return;
    this.guardando.set(true);
    this.servicio.crearNota(p.id, this.formNota.controls.texto.value.trim()).subscribe({
      next: (n) => {
        this.guardando.set(false);
        this.notas.update((l) => [n, ...l]);
        this.formNota.reset();
      },
      error: this.fallo('No pudimos guardar la nota.'),
    });
  }

  protected borrarNota(n: NotaCrecimiento): void {
    this.servicio.borrarNota(n.id).subscribe({
      next: () => this.notas.update((l) => l.filter((x) => x.id !== n.id)),
      error: this.fallo('No pudimos borrar la nota.'),
    });
  }

  /** Borra lo que se está viendo (el área o el programa) con todo lo que tiene dentro. */
  protected borrar(): void {
    const nivel = this.nivel();
    const peticion =
      nivel === 'proceso'
        ? this.servicio.borrarProceso(this.proceso()!.id)
        : this.servicio.borrarArea(this.area()!.id);
    peticion.subscribe({
      next: () => {
        this.confirmarBorrar.set(false);
        // El elemento ya no existe: se vuelve al nivel de arriba sin abrirlo otra vez.
        if (nivel === 'proceso') this.proceso.set(null);
        else this.area.set(null);
        const a = this.area();
        if (nivel === 'proceso' && a) this.abrirArea(a);
        else this.cargarAreas();
      },
      error: this.fallo('No pudimos borrarlo.'),
    });
  }

  protected fuenteTexto(p: Pick<ProcesoCrecimiento, 'fuente' | 'fuente_titulo' | 'autor'>): string {
    const base = FUENTES.find((f) => f.id === p.fuente)?.label ?? '';
    const detalle = [p.fuente_titulo, p.autor].filter(Boolean).join(' · ');
    return detalle ? `${base}: ${detalle}` : base;
  }

  protected estadoTexto(e: EstadoProyecto): string {
    return { por_empezar: 'Por empezar', en_curso: 'En curso', terminado: 'Terminado' }[e];
  }
}
