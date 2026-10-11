/*
 * THESIS: una foto fuerte para abrir y un recorrido que se baja como un sendero: cada
 * estación de la app sube como el sol, con lo justo de texto.
 * OWN-WORLD: noche cálida (#100d0b), fotos a sangre completa en calidad alta, Barlow
 * Condensed compacto para titulares, el sendero como línea dorada, un botón de vidrio.
 * STORY: cualquiera, sepa o no qué hacer, entiende que la app arma su comida (con o sin
 * nutricionista), su entreno y su seguimiento, y empieza.
 * FIRST VIEWPORT: los guantes colgados en el haz de luz; el titular arriba dentro de la
 * luz; abajo el botón "Empieza tu camino".
 * FORM: hero cinematográfico centrado + recorrido de estaciones fijas (elegido por el
 * usuario); nada de partículas ni destellos.
 */
import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  ElementRef,
  afterNextRender,
  computed,
  inject,
  signal,
} from '@angular/core';
import { RouterLink } from '@angular/router';

import { AuthService } from '../core/services/auth';

interface Imagen {
  nombre: string;
  alt: string;
}

interface Estacion {
  id: 'comida' | 'entreno' | 'progreso' | 'agenda';
  nombre: string;
  titulo: string;
  texto: string;
}

const ESTACIONES: Estacion[] = [
  {
    id: 'comida',
    nombre: 'Tu comida',
    titulo: 'Con tu nutricionista o sin ella.',
    texto:
      'Pasa su minuta a la app o súbela en PDF; si no tienes, la app calcula una guía. Cada semana tienes menú nuevo, hecho solo con tu lista de intercambios.',
  },
  {
    id: 'entreno',
    nombre: 'Tu entreno',
    titulo: 'El que te mueve a ti.',
    texto:
      'Boxeo, fuerza, funcional, cardio en casa o yoga. Una rutina con lo que tienes a mano y un temporizador que te lleva serie por serie.',
  },
  {
    id: 'progreso',
    nombre: 'Tu progreso',
    titulo: 'Tu punto de partida no se borra.',
    texto:
      'Medidas, peso y fotos del primer día quedan guardadas tal cual. Las comparas con hoy cuando quieras, y solo tú las ves.',
  },
  {
    id: 'agenda',
    nombre: 'Tu agenda',
    titulo: 'Nada se te pasa.',
    texto:
      'El control con tu nutricionista, cuándo pesarte, cuándo se acaba la proteína. La app te avisa antes, para que no tengas que acordarte de todo.',
  },
];

const IMAGENES: Record<Exclude<Estacion['id'], 'entreno'>, Imagen> = {
  comida: { nombre: 'plan', alt: 'Desayuno casero: huevos pericos, arepa, aguacate y café' },
  progreso: { nombre: 'progreso', alt: 'Una persona se mide la cintura con una cinta métrica' },
  agenda: {
    nombre: 'agenda',
    alt: 'Un hombre se amarra los tenis en la entrada de su casa al amanecer',
  },
};

const ENTRENOS: (Imagen & { enfoque: string })[] = [
  { nombre: 'entreno', enfoque: 'Boxeo', alt: 'Un boxeador golpea un saco en el gimnasio' },
  { nombre: 'entreno-yoga', enfoque: 'Yoga', alt: 'Una mujer hace yoga en la sala de su casa' },
  {
    nombre: 'entreno-casa',
    enfoque: 'Cardio en casa',
    alt: 'Un hombre hace sentadillas en su sala',
  },
];

const ENFOQUES = ['Boxeo', 'Fuerza', 'Funcional', 'Cardio en casa', 'Yoga'];

/** Avance de 0 a 1 de una sección alta con un escenario fijo adentro. */
function avance(seccion: HTMLElement, alto: number): number {
  const caja = seccion.getBoundingClientRect();
  const recorrido = caja.height - alto;
  if (recorrido <= 0) return 0;
  return Math.min(1, Math.max(0, -caja.top / recorrido));
}

@Component({
  selector: 'app-home',
  templateUrl: './home.html',
  styleUrl: './home.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [RouterLink],
})
export class Home {
  protected auth = inject(AuthService);
  private host = inject<ElementRef<HTMLElement>>(ElementRef);
  private destroyRef = inject(DestroyRef);

  protected estaciones = ESTACIONES;
  protected imagenes = IMAGENES;
  protected entrenos = ENTRENOS;
  protected enfoques = ENFOQUES;

  protected estacion = signal(0);
  protected entreno = signal(0);
  protected enfoqueActual = computed(() => ENTRENOS[this.entreno()].enfoque);
  protected numero = computed(() => String(this.estacion() + 1).padStart(2, '0'));

  constructor() {
    afterNextRender(() => this.iniciar());
  }

  private iniciar(): void {
    const raiz = this.host.nativeElement;
    const hero = raiz.querySelector<HTMLElement>('[data-hero]');
    const recorrido = raiz.querySelector<HTMLElement>('[data-recorrido]');
    if (!hero || !recorrido) return;

    const sinMovimiento = matchMedia('(prefers-reduced-motion: reduce)');
    const aplicarPreferencia = () =>
      raiz.classList.toggle('con-movimiento', !sinMovimiento.matches);
    aplicarPreferencia();
    sinMovimiento.addEventListener('change', aplicarPreferencia);

    let pendiente = false;
    const medir = () => {
      pendiente = false;
      const alto = window.innerHeight;
      raiz.style.setProperty('--hero', avance(hero, alto).toFixed(4));
      const q = avance(recorrido, alto);
      raiz.style.setProperty('--recorrido', q.toFixed(4));
      const indice = Math.min(ESTACIONES.length - 1, Math.floor(q * ESTACIONES.length));
      if (indice !== this.estacion()) this.estacion.set(indice);
    };
    const alMover = () => {
      if (pendiente) return;
      pendiente = true;
      requestAnimationFrame(medir);
    };
    medir();
    window.addEventListener('scroll', alMover, { passive: true });
    window.addEventListener('resize', alMover);

    const observador = new IntersectionObserver(
      (entradas) =>
        entradas.forEach((e) => {
          if (!e.isIntersecting) return;
          e.target.classList.add('visible');
          observador.unobserve(e.target);
        }),
      { threshold: 0.3 },
    );
    raiz.querySelectorAll('[data-aparece]').forEach((el) => observador.observe(el));

    // En la estación del entreno se turnan las disciplinas.
    const rotar = window.setInterval(() => {
      if (document.hidden || this.estacion() !== 1 || sinMovimiento.matches) return;
      this.entreno.update((i) => (i + 1) % ENTRENOS.length);
    }, 3200);

    this.destroyRef.onDestroy(() => {
      window.removeEventListener('scroll', alMover);
      window.removeEventListener('resize', alMover);
      sinMovimiento.removeEventListener('change', aplicarPreferencia);
      observador.disconnect();
      window.clearInterval(rotar);
    });
  }

  protected irAEstacion(indice: number): void {
    const recorrido = this.host.nativeElement.querySelector<HTMLElement>('[data-recorrido]');
    if (!recorrido) return;
    const alto = window.innerHeight;
    const inicio = recorrido.getBoundingClientRect().top + window.scrollY;
    const tramo = (recorrido.offsetHeight - alto) / ESTACIONES.length;
    window.scrollTo({ top: inicio + tramo * (indice + 0.5), behavior: 'smooth' });
  }
}
