/*
 * THESIS: una foto fuerte para abrir y un recorrido que se baja como un sendero: cada
 * estación de la app sube como el sol, con lo justo de texto.
 * OWN-WORLD: noche cálida (#100d0b), fotos a sangre completa en calidad alta, Barlow
 * Condensed compacto para titulares, el sendero como línea dorada, un botón de vidrio.
 * STORY: cualquiera, sepa o no qué hacer, entiende que la app arma su comida (con o sin
 * nutricionista), su entreno y su seguimiento, y empieza.
 * FIRST VIEWPORT: los guantes flotando en el negro, el titular a un lado y el botón
 * "Empieza tu camino"; al bajar, vendas y cuerdas estallan alrededor de los guantes.
 * FORM: hero cinematográfico con la animación atada al scroll (96 cuadros WebP dibujados
 * en un video) + recorrido de estaciones fijas; nada de partículas ni destellos.
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
import { Capacitor } from '@capacitor/core';

import { AuthService } from '../core/services/auth';
import { ApkService } from '../core/services/apk';
import { DescargaApk } from '../shared/descarga-apk/descarga-apk';

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
  imports: [RouterLink, DescargaApk],
})
export class Home {
  protected auth = inject(AuthService);
  protected apk = inject(ApkService);
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

    const elVideo = raiz.querySelector<HTMLVideoElement>('[data-video]');
    const secuencia = elVideo && this.puedeAnimar() ? this.video(elVideo) : null;

    let pendiente = false;
    const medir = () => {
      pendiente = false;
      const alto = window.innerHeight;
      raiz.style.setProperty('--hero', avance(hero, alto).toFixed(4));
      // La animación arranca con el primer scroll y sigue en bucle mientras el hero se vea.
      if (secuencia && window.scrollY > 4) secuencia.reproducir();
      const camino = raiz.querySelector<HTMLElement>('.preguntas');
      if (camino) {
        // La línea dorada llega hasta donde ya se bajó por la lista de preguntas.
        const c = camino.getBoundingClientRect();
        const p = (alto * 0.78 - c.top) / Math.max(1, c.height);
        raiz.style.setProperty('--preguntas', Math.min(1, Math.max(0, p)).toFixed(3));
      }
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
      { threshold: 0.12 },
    );
    raiz.querySelectorAll('[data-aparece]').forEach((el) => observador.observe(el));

    // Cada pregunta y cada línea del "para quién" llega cuando se la alcanza.
    const porItem = new IntersectionObserver(
      (entradas) =>
        entradas.forEach((e) => {
          if (!e.isIntersecting) return;
          e.target.classList.add('visible');
          porItem.unobserve(e.target);
        }),
      { threshold: 0.5, rootMargin: '0px 0px -8% 0px' },
    );
    raiz.querySelectorAll('[data-item]').forEach((el) => porItem.observe(el));

    // El cierre: la foto se acerca a su sitio al llegar.
    const cierre = raiz.querySelector('[data-cierre]');
    const alCierre = new IntersectionObserver(
      (entradas) =>
        entradas.forEach((e) => {
          if (e.isIntersecting) e.target.classList.add('entra');
        }),
      { threshold: 0.25 },
    );
    if (cierre) alCierre.observe(cierre);

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
      porItem.disconnect();
      alCierre.disconnect();
      window.clearInterval(rotar);
      secuencia?.detener();
    });
  }

  /**
   * El video del hero se reproduce si la persona no pidió reducir el movimiento y hay con qué
   * bajarlo: dentro de la app instalada va empaquetado, en la web no se baja con ahorro de
   * datos ni con una conexión lenta (queda el primer cuadro).
   */
  private puedeAnimar(): boolean {
    if (matchMedia('(prefers-reduced-motion: reduce)').matches) return false;
    if (Capacitor.isNativePlatform()) return true;
    const conexion = (
      navigator as Navigator & { connection?: { saveData?: boolean; effectiveType?: string } }
    ).connection;
    return !conexion?.saveData && !['slow-2g', '2g', '3g'].includes(conexion?.effectiveType ?? '');
  }

  /**
   * Video del hero (H.264, sin audio) decodificado por el chip del celular: mucho más fluido que
   * dibujar cuadros con JavaScript. Arranca con el primer scroll, sigue en bucle y se pausa cuando
   * el hero no se ve o la pestaña está oculta. Hay una versión horizontal y una vertical.
   */
  private video(el: HTMLVideoElement): { reproducir(): void; detener(): void } {
    el.muted = true;
    const movil = matchMedia('(max-width: 767px)');
    let iniciada = false;
    let visible = true;

    const intentar = () => {
      if (!iniciada || !visible || document.hidden) return;
      void el.play().catch(() => undefined);
    };
    const poner = () => {
      // En la app instalada solo va empaquetada la versión vertical (la otra pesa 10 MB de más).
      const vertical = movil.matches || Capacitor.isNativePlatform();
      const fuente = vertical ? '/home/hero-movil.mp4' : '/home/hero.mp4';
      if (el.getAttribute('src') === fuente) return;
      el.setAttribute('src', fuente);
      el.load();
      intentar();
    };
    const alReproducir = () => el.classList.add('reproduciendo');
    el.addEventListener('playing', alReproducir);

    const vigia = new IntersectionObserver(([e]) => {
      visible = e.isIntersecting;
      if (visible) intentar();
      else el.pause();
    });
    vigia.observe(el);
    const alCambiarPestana = () => (document.hidden ? el.pause() : intentar());
    document.addEventListener('visibilitychange', alCambiarPestana);
    movil.addEventListener('change', poner);

    // Se empieza a bajar cuando el navegador está libre, para no competir con la foto del hero.
    const cuandoLibre = (fn: () => void) =>
      'requestIdleCallback' in window
        ? window.requestIdleCallback(fn, { timeout: 1500 })
        : setTimeout(fn, 800);
    cuandoLibre(poner);

    return {
      reproducir: () => {
        iniciada = true;
        poner();
        intentar();
      },
      detener: () => {
        el.pause();
        vigia.disconnect();
        el.removeEventListener('playing', alReproducir);
        document.removeEventListener('visibilitychange', alCambiarPestana);
        movil.removeEventListener('change', poner);
      },
    };
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
