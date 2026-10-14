import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  OnInit,
  computed,
  inject,
  input,
  signal,
} from '@angular/core';
import { ButtonModule } from 'primeng/button';
import { InputTextModule } from 'primeng/inputtext';
import { MessageModule } from 'primeng/message';
import { TextareaModule } from 'primeng/textarea';

import { ProyectoCrecimiento } from '../../core/models/crecimiento.model';
import { CrecimientoService } from '../../core/services/crecimiento';
import { clasesChip } from '../../shared/chip';
import { mensajeError } from '../../shared/errores';
import { hoyISO, sumarDias } from '../../shared/fechas';
import { Pestana, Pestanas } from '../../shared/pestanas/pestanas';

type Paso = '1' | '2' | '3' | '4';

/** Las creencias del cuestionario, por grupo, cada una con una sugerencia general para transformarla. */
const GRUPOS: { id: string; nombre: string; preguntas: [string, string][] }[] = [
  {
    id: 'a',
    nombre: 'Merecimiento y autoestima',
    preguntas: [
      [
        'Siento que no merezco tener mucho dinero',
        'Merezco una vida próspera y tranquila con el dinero.',
      ],
      [
        'Creo que no soy bueno/a manejando mis finanzas',
        'Cada mes aprendo a manejar mejor mi plata.',
      ],
      [
        'Pienso que tener dinero me volvería peor persona',
        'El dinero amplifica lo bueno que ya soy.',
      ],
      [
        'Relaciono el éxito económico con gente fría o egoísta',
        'Puedo tener éxito económico y seguir siendo generoso/a.',
      ],
      ['Me da culpa gastar plata en mí', 'Invertir en mí también es cuidarme.'],
    ],
  },
  {
    id: 'b',
    nombre: 'Esfuerzo y trabajo',
    preguntas: [
      [
        'Creo que solo con mucho esfuerzo y sacrificio se gana dinero',
        'Puedo ganar dinero con inteligencia y disfrutando lo que hago.',
      ],
      [
        'Pienso que trabajar en lo que me gusta no da buena plata',
        'Lo que me apasiona puede generar buenos ingresos.',
      ],
      [
        'Creo que para ganar más tendría que dejar de disfrutar la vida',
        'Puedo crecer en ingresos sin sacrificar mi bienestar.',
      ],
    ],
  },
  {
    id: 'c',
    nombre: 'Ahorro y escasez',
    preguntas: [
      [
        'Tengo miedo constante de quedarme sin dinero',
        'Construyo mi tranquilidad con un fondo que me respalda.',
      ],
      ['Me cuesta ahorrar aunque me alcance', 'Ahorrar es pagarme primero a mí.'],
      [
        'Me preocupa gastar, incluso en lo necesario',
        'Gasto con conciencia y sin miedo en lo que importa.',
      ],
      [
        'Pienso que si me doy un gusto hoy, mañana me hará falta',
        'Planeo mis gustos y los disfruto sin culpa.',
      ],
    ],
  },
  {
    id: 'd',
    nombre: 'Inversión y crecimiento',
    preguntas: [
      [
        'Creo que invertir es solo para gente rica',
        'Cualquiera puede aprender a invertir, empezando por mí.',
      ],
      [
        'Siento que no tengo capacidad para aprender de finanzas',
        'Soy capaz de aprender finanzas paso a paso.',
      ],
      [
        'Me paraliza la idea de perder dinero si intento algo nuevo',
        'Tomo riesgos medidos y aprendo de cada intento.',
      ],
      [
        'Creo que nunca voy a salir de deudas o mejorar mi situación',
        'Estoy dando pasos concretos hacia mi estabilidad financiera.',
      ],
    ],
  },
];

interface Pregunta {
  k: string;
  grupo: string;
  texto: string;
  sugerencia: string;
}

const TODAS: Pregunta[] = GRUPOS.flatMap((g) =>
  g.preguntas.map(([texto, sugerencia], i) => ({
    k: g.id + i,
    grupo: g.nombre,
    texto,
    sugerencia,
  })),
);

const PASOS: Pestana<Paso>[] = [
  { id: '1', label: 'Cuestionario', icon: 'pi pi-check-square' },
  { id: '2', label: 'Reflexiona', icon: 'pi pi-comment' },
  { id: '3', label: 'Transforma', icon: 'pi pi-sparkles' },
  { id: '4', label: 'Resultado', icon: 'pi pi-star' },
];

const META = 21;

interface Datos {
  ans: Partial<Record<string, 'si' | 'no'>>;
  ref: Partial<Record<string, { a: string; b: string }>>;
  pos: Partial<Record<string, string>>;
  dias: string[];
  avisar: boolean;
  hora_aviso: string;
}

/**
 * Taller de creencias («Sana tus finanzas», capítulo 1): responder sí o no a cada creencia, reflexionar sobre
 * los «sí», transformarlas en creencias nuevas y leerlas 21 días seguidos.
 */
@Component({
  selector: 'app-taller-creencias',
  templateUrl: './taller-creencias.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [ButtonModule, InputTextModule, MessageModule, TextareaModule, Pestanas],
})
export class TallerCreencias implements OnInit {
  readonly proyecto = input.required<ProyectoCrecimiento>();

  private servicio = inject(CrecimientoService);
  private temporizador: ReturnType<typeof setTimeout> | null = null;

  protected grupos = GRUPOS;
  protected pasos = PASOS;
  protected meta = META;
  protected clasesChip = clasesChip;
  protected letras = 'abcd';

  protected paso = signal<Paso>('1');
  protected datos = signal<Datos>({
    ans: {},
    ref: {},
    pos: {},
    dias: [],
    avisar: true,
    hora_aviso: '08:00',
  });
  protected guardando = signal(false);
  protected error = signal('');
  protected aviso = signal('');

  protected respondidas = computed(() => Object.keys(this.datos().ans).length);
  protected total = TODAS.length;
  protected si = computed(() => TODAS.filter((q) => this.datos().ans[q.k] === 'si'));
  protected nuevas = computed(() =>
    this.si()
      .map((q) => ({ q, texto: (this.datos().pos[q.k] ?? '').trim() }))
      .filter((x) => x.texto),
  );
  protected leidaHoy = computed(() => this.datos().dias.includes(hoyISO()));
  /** Días seguidos leyéndolas, hasta hoy o ayer (igual que el servidor). */
  protected racha = computed(() => {
    const dias = new Set(this.datos().dias);
    let d = dias.has(hoyISO()) ? hoyISO() : sumarDias(hoyISO(), -1);
    let n = 0;
    while (dias.has(d)) {
      n++;
      d = sumarDias(d, -1);
    }
    return n;
  });
  protected cuadros = computed(() =>
    Array.from({ length: META }, (_, i) => i < Math.min(this.racha(), META)),
  );

  constructor() {
    // Si quedó algo escrito sin guardar, se guarda al salir.
    inject(DestroyRef).onDestroy(() => {
      if (this.temporizador) this.guardarYa();
    });
  }

  ngOnInit(): void {
    const d = this.proyecto().datos as Partial<Datos>;
    this.datos.set({
      ans: d.ans ?? {},
      ref: d.ref ?? {},
      pos: d.pos ?? {},
      dias: d.dias ?? [],
      avisar: d.avisar ?? true,
      hora_aviso: d.hora_aviso ?? '08:00',
    });
  }

  protected rotacion(i: number): string {
    return `${[-2, 1.5, -1, 2, -1.5][i % 5]}deg`;
  }

  protected responder(k: string, v: 'si' | 'no'): void {
    this.datos.update((d) => {
      const ans = { ...d.ans };
      if (ans[k] === v) delete ans[k];
      else ans[k] = v;
      return { ...d, ans };
    });
    this.guardarYa();
  }

  protected reflexionar(k: string, campo: 'a' | 'b', texto: string): void {
    this.datos.update((d) => ({
      ...d,
      ref: { ...d.ref, [k]: { ...(d.ref[k] ?? { a: '', b: '' }), [campo]: texto } },
    }));
    this.guardarLuego();
  }

  protected transformar(k: string, texto: string): void {
    this.datos.update((d) => ({ ...d, pos: { ...d.pos, [k]: texto } }));
    this.guardarLuego();
  }

  protected usarSugerencia(q: Pregunta): void {
    this.transformar(q.k, q.sugerencia);
    this.guardarYa();
  }

  protected ajustarAviso(avisar: boolean, hora: string): void {
    this.datos.update((d) => ({ ...d, avisar, hora_aviso: hora }));
    this.guardarYa();
  }

  /** Mientras escribe se espera un poco antes de guardar. */
  private guardarLuego(): void {
    if (this.temporizador) clearTimeout(this.temporizador);
    this.temporizador = setTimeout(() => this.guardarYa(), 800);
  }

  private guardarYa(): void {
    if (this.temporizador) clearTimeout(this.temporizador);
    this.temporizador = null;
    const { ans, ref, pos, avisar, hora_aviso } = this.datos();
    this.guardando.set(true);
    this.servicio
      .actualizarProyecto(this.proyecto().id, { datos: { ans, ref, pos, avisar, hora_aviso } })
      .subscribe({
        next: () => {
          this.guardando.set(false);
          this.error.set('');
        },
        error: (e) => {
          this.guardando.set(false);
          this.error.set(mensajeError(e, 'No pudimos guardar tus respuestas.'));
        },
      });
  }

  protected yaLasLei(): void {
    this.guardarYa();
    this.servicio.accion(this.proyecto().id, 'leer').subscribe({
      next: (p) => {
        this.datos.update((d) => ({ ...d, dias: (p.datos['dias'] as string[]) ?? d.dias }));
        this.aviso.set('¡Bien! Hoy ya las leíste.');
      },
      error: (e) => this.error.set(mensajeError(e, 'No pudimos marcarlo.')),
    });
  }

  protected async copiar(completo: boolean): Promise<void> {
    const texto = completo
      ? this.si()
          .map((q) => {
            const r = this.datos().ref[q.k] ?? { a: '', b: '' };
            return `Creencia: ${q.texto}\n¿A dónde me ha llevado? ${r.a || '-'}\n¿Qué me impide lograr? ${r.b || '-'}\nNueva creencia: ${this.datos().pos[q.k] || '-'}`;
          })
          .join('\n\n')
      : this.nuevas()
          .map((x) => `• ${x.texto}`)
          .join('\n');
    try {
      await navigator.clipboard.writeText(texto);
      this.aviso.set('Copiado.');
    } catch {
      this.error.set('No se pudo copiar.');
    }
  }

  protected leer(e: Event): string {
    return (e.target as HTMLInputElement).value;
  }
}
