import {
  afterNextRender,
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  OnDestroy,
  computed,
  effect,
  inject,
  input,
  output,
  untracked,
} from '@angular/core';

export type EstadoGuerrero = 'descansa' | 'firme' | 'celebra';
export type AccionGuerrero = 'agua' | 'proteina' | 'comer' | 'dormir' | 'levantar' | 'entrenar';

/** Desde cuánto del día cuenta para la racha (la misma meta que el servidor). */
export const META_DEL_DIA = 50;

/** La pausa vista desde hoy: en curso, o terminó hoy (la persona ya volvió). */
export type PausaDeHoy = 'activa' | 'volvio' | null;

export function pausaDeHoy(
  hoy: { en_pausa?: boolean; volvio?: boolean } | null | undefined,
  activa: boolean,
): PausaDeHoy {
  if (activa) return 'activa';
  return hoy?.en_pausa || hoy?.volvio ? 'volvio' : null;
}

/**
 * El estado del guerrero según cuánto va del día: poco, algo, o lo que hace falta para sostener la racha. En
 * pausa descansa con la persona; el día que vuelve está despierto aunque el día aún no sume (o no cuente).
 */
export function estadoDe(
  porcentaje: number | null | undefined,
  meta = META_DEL_DIA,
  pausa: PausaDeHoy = null,
): EstadoGuerrero {
  if (pausa === 'activa') return 'descansa';
  if (pausa === 'volvio' && (porcentaje ?? 0) < meta) return 'firme';
  if (porcentaje == null || porcentaje < meta / 2) return 'descansa';
  return porcentaje >= meta ? 'celebra' : 'firme';
}

/** Cuánto dura cada acción (ms): el tiempo de verlo hacerla, no de esperar. */
export const DURACION_ACCION: Record<AccionGuerrero, number> = {
  agua: 2600,
  proteina: 3200,
  comer: 3400,
  dormir: 3600,
  levantar: 3200,
  entrenar: 3800,
};

type Punto = [number, number];

interface Pose {
  /** Dónde está la mano izquierda y la derecha (en el dibujo). */
  hi: Punto;
  hd: Punto;
  cabeza: { rot: number; dy: number };
  ojos: 'abiertos' | 'cerrados' | 'esfuerzo';
  /** Lo que sostiene: en la mano derecha (vaso, shaker, arepa) o entre las dos (barra). */
  prop: 'vaso' | 'shaker' | 'arepa' | 'barra' | null;
  angulo: number;
  nivel: number;
  mordidas: number;
  zzz: number;
  luna: number;
  sol: number;
  cuerpoDy: number;
}

// ── Geometría del dibujo (160 × 188, el centro del casco en x = 80) ──────────────────────────────
const HOMBRO_I: Punto = [42, 118];
const HOMBRO_D: Punto = [118, 118];
const LARGO_BRAZO = 33;
const MANO_I: Punto = [64, 142];
const MANO_D: Punto = [96, 142];
const BOCA: Punto = [80, 88];

const lim = (t: number) => Math.min(1, Math.max(0, t));
const suave = (t: number) => (t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2);
/** 0 → 1 entre a y b, con arranque y llegada suaves. */
const tramo = (t: number, a: number, b: number) => suave(lim((t - a) / (b - a)));
const mezcla = (a: number, b: number, k: number) => a + (b - a) * k;
const mover = (a: Punto, b: Punto, k: number): Punto => [
  mezcla(a[0], b[0], k),
  mezcla(a[1], b[1], k),
];
/** Un golpe breve alrededor de `c` (un trago, un mordisco). */
const golpe = (t: number, c: number, ancho = 0.025) => Math.exp(-Math.pow((t - c) / ancho, 2));

const REPOSO: Pose = {
  hi: MANO_I,
  hd: MANO_D,
  cabeza: { rot: 0, dy: 0 },
  ojos: 'abiertos',
  prop: null,
  angulo: 0,
  nivel: 1,
  mordidas: 0,
  zzz: 0,
  luna: 0,
  sol: 0,
  cuerpoDy: 0,
};

/** Cada acción es una función del tiempo (0 → 1) que dice dónde está cada parte del guerrero. */
const ACCIONES: Record<AccionGuerrero, (t: number) => Pose> = {
  // Se lleva el vaso a la boca, lo inclina y toma tres tragos.
  agua: (t) => {
    const sube = tramo(t, 0.0, 0.24) - tramo(t, 0.8, 1);
    const trago = golpe(t, 0.5) + golpe(t, 0.6) + golpe(t, 0.7);
    return {
      ...REPOSO,
      hd: mover(MANO_D, [101, 99], sube),
      prop: 'vaso',
      angulo: -36 * (tramo(t, 0.2, 0.44) - tramo(t, 0.74, 0.86)),
      nivel: 1 - 0.88 * tramo(t, 0.4, 0.72),
      cabeza: { rot: -3 * tramo(t, 0.3, 0.5) * (1 - tramo(t, 0.74, 0.9)), dy: 1.6 * trago },
    };
  },
  // Agita el shaker con las dos manos y luego se lo toma.
  proteina: (t) => {
    const junta = tramo(t, 0.0, 0.16) - tramo(t, 0.86, 1);
    const agita = lim((t - 0.14) / 0.3) * (1 - lim((t - 0.44) / 0.04)) * Math.sin(t * 150);
    const toma = tramo(t, 0.46, 0.64) - tramo(t, 0.86, 0.98);
    const trago = golpe(t, 0.66) + golpe(t, 0.76);
    const base = mover(MANO_D, [90, 118], junta);
    return {
      ...REPOSO,
      hd: mover([base[0], base[1] + 3 * agita], [102, 98], toma),
      hi: mover(MANO_I, [84, 122], junta * (1 - toma)),
      prop: 'shaker',
      angulo: 10 * agita - 40 * toma,
      nivel: 1 - 0.7 * tramo(t, 0.58, 0.82),
      cabeza: { rot: 0, dy: 1.6 * trago },
    };
  },
  // Muerde una arepa tres veces y mastica.
  comer: (t) => {
    const sube = tramo(t, 0.0, 0.2) - tramo(t, 0.86, 1);
    const mordida = golpe(t, 0.32) + golpe(t, 0.54) + golpe(t, 0.76);
    const mastica = [0.4, 0.62, 0.84].reduce(
      (s, c) => s + Math.max(0, Math.sin((t - c) * 42)) * (t > c && t < c + 0.14 ? 1 : 0),
      0,
    );
    return {
      ...REPOSO,
      hd: mover(MANO_D, [97, 97], sube - 0.06 * mordida),
      prop: 'arepa',
      angulo: -18 * sube,
      mordidas: (t > 0.32 ? 1 : 0) + (t > 0.54 ? 1 : 0) + (t > 0.76 ? 1 : 0),
      cabeza: { rot: 0, dy: 1.4 * mastica + 1.2 * mordida },
    };
  },
  // Se acomoda, cierra los ojos y salen las zetas.
  dormir: (t) => ({
    ...REPOSO,
    cabeza: { rot: 11 * tramo(t, 0.05, 0.4), dy: 3 * tramo(t, 0.05, 0.4) },
    ojos: t > 0.2 ? 'cerrados' : 'abiertos',
    cuerpoDy: 3 * tramo(t, 0.05, 0.4),
    luna: tramo(t, 0.1, 0.4) - tramo(t, 0.92, 1),
    zzz: lim((t - 0.3) / 0.7),
    hi: mover(MANO_I, [70, 134], tramo(t, 0.05, 0.4)),
    hd: mover(MANO_D, [90, 134], tramo(t, 0.05, 0.4)),
  }),
  // Despierta, abre los ojos, se estira con el sol saliendo y vuelve a su sitio.
  levantar: (t) => {
    const despierta = tramo(t, 0.1, 0.3);
    const estira = tramo(t, 0.3, 0.55) - tramo(t, 0.74, 0.96);
    return {
      ...REPOSO,
      cabeza: { rot: 11 * (1 - despierta) - 2 * estira, dy: 3 * (1 - despierta) - 3 * estira },
      ojos: t < 0.16 ? 'cerrados' : 'abiertos',
      cuerpoDy: 3 * (1 - despierta),
      sol: tramo(t, 0.15, 0.55) - tramo(t, 0.86, 1),
      hi: mover(MANO_I, [34, 26], estira),
      hd: mover(MANO_D, [126, 26], estira),
    };
  },
  // Levanta la barra del pecho tres veces, con cara de esfuerzo.
  entrenar: (t) => {
    const agarra = tramo(t, 0, 0.1) - tramo(t, 0.92, 1);
    const rep = (a: number, b: number) => tramo(t, a, (a + b) / 2) - tramo(t, (a + b) / 2, b);
    const sube = Math.max(rep(0.1, 0.38), rep(0.34, 0.62), rep(0.58, 0.86));
    const y = mezcla(142, 108, sube);
    return {
      ...REPOSO,
      hi: [mezcla(MANO_I[0], 40, agarra), mezcla(MANO_I[1], y, agarra)],
      hd: [mezcla(MANO_D[0], 120, agarra), mezcla(MANO_D[1], y, agarra)],
      prop: 'barra',
      ojos: sube > 0.55 ? 'esfuerzo' : 'abiertos',
      cabeza: { rot: 0, dy: -2.2 * sube },
      cuerpoDy: 1.6 * sube,
    };
  },
};

/** Dos huesos con codo: dónde queda el codo para que la mano llegue a `mano` (el codo se dobla hacia afuera y abajo). */
function codo(hombro: Punto, mano: Punto, haciaAfuera: 1 | -1): Punto {
  const dx = mano[0] - hombro[0];
  const dy = mano[1] - hombro[1];
  const d = Math.min(Math.hypot(dx, dy), LARGO_BRAZO * 2 - 0.01) || 0.01;
  const a = Math.atan2(dy, dx);
  const cos = d / (2 * LARGO_BRAZO);
  const apertura = Math.acos(Math.min(1, cos));
  const candidatos = [a + apertura, a - apertura].map<Punto>((r) => [
    hombro[0] + LARGO_BRAZO * Math.cos(r),
    hombro[1] + LARGO_BRAZO * Math.sin(r),
  ]);
  return candidatos.sort((p, q) => (q[0] - p[0]) * haciaAfuera - 0.2 * (q[1] - p[1]))[0] as Punto;
}

let contador = 0;

/**
 * El guerrero del logo, de busto y dibujado a mano en SVG. Tiene tres estados (descansa, firme,
 * celebra) y seis acciones que hace con sus manos y objetos: toma agua, se toma la proteína, come,
 * duerme, se levanta y entrena. Sin imágenes ni librerías: las poses se calculan por cuadro (los
 * brazos con dos huesos) y solo mientras dura la acción. Con «reducir movimiento» se queda en el
 * momento clave sin moverse.
 */
@Component({
  selector: 'app-guerrero',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: {
    class: 'inline-block',
    '[style.width.px]': 'tamano()',
    '[style.height.px]': 'tamano() * 1.175',
  },
  template: `
    <svg
      viewBox="0 -18 160 188"
      [class]="'g ' + estado()"
      role="img"
      [attr.aria-label]="etiqueta()"
      overflow="visible"
    >
      <defs>
        <linearGradient [attr.id]="id + 'casco'" x1="0" x2="1" y1="0" y2="0">
          <stop offset="0" stop-color="#d9503f" />
          <stop offset="0.55" stop-color="#c0392b" />
          <stop offset="1" stop-color="#8f2a1f" />
        </linearGradient>
        <linearGradient [attr.id]="id + 'cuerpo'" x1="0" x2="1" y1="0" y2="0">
          <stop offset="0" stop-color="#a8322a" />
          <stop offset="1" stop-color="#6e1f18" />
        </linearGradient>
        <radialGradient [attr.id]="id + 'aura'" cx="0.5" cy="0.45" r="0.5">
          <stop offset="0.55" stop-color="#d4af37" stop-opacity="0.35" />
          <stop offset="1" stop-color="#d4af37" stop-opacity="0" />
        </radialGradient>
        <clipPath [attr.id]="id + 'vaso'"><path d="M-8 -26 L8 -26 L6 -2 L-6 -2 Z" /></clipPath>
        <mask [attr.id]="id + 'mordida'">
          <rect x="-14" y="-24" width="28" height="28" fill="#fff" />
          <circle data-m="1" cx="-10" cy="-14" r="7" fill="#000" opacity="0" />
          <circle data-m="2" cx="-9" cy="-4" r="6.5" fill="#000" opacity="0" />
          <circle data-m="3" cx="-2" cy="-19" r="6.5" fill="#000" opacity="0" />
        </mask>
      </defs>

      <circle class="aura" cx="80" cy="52" r="68" [attr.fill]="'url(#' + id + 'aura)'" />

      <!-- El sol que sale al levantarse -->
      <g data-p="sol" opacity="0" transform="translate(0 70)">
        <circle cx="80" cy="64" r="22" fill="#d4af37" />
        <circle
          cx="80"
          cy="64"
          r="30"
          fill="none"
          stroke="#d4af37"
          stroke-opacity="0.35"
          stroke-width="3"
        />
      </g>

      <g data-p="cuerpo">
        <g class="todo">
          <!-- hombros y peto -->
          <path
            d="M22 172 C22 126 40 102 64 99 L96 99 C120 102 138 126 138 172 Z"
            [attr.fill]="'url(#' + id + 'cuerpo)'"
          />
          <path
            d="M30 150 C32 126 46 108 64 103 M130 150 C128 126 114 108 96 103"
            fill="none"
            stroke="#d4af37"
            stroke-width="2.4"
            stroke-linecap="round"
          />
          <path
            d="M64 99 L80 120 L96 99"
            fill="none"
            stroke="#d4af37"
            stroke-width="3"
            stroke-linejoin="round"
          />
          <rect x="70" y="86" width="20" height="15" fill="#4a130e" />

          <g class="cabeza" data-p="cabeza">
            <g class="cresta">
              <path
                d="M74 20 C72 6 75 -6 80 -14 C85 -6 88 6 86 20 Z"
                fill="#8f2a1f"
                stroke="#d4af37"
                stroke-width="1.6"
                stroke-linejoin="round"
              />
              <path d="M80 -8 C78 0 78 10 80 18" fill="none" stroke="#c0392b" stroke-width="2" />
            </g>
            <path
              d="M80 14 C102 14 118 30 118 56 L118 74 C118 86 112 96 104 102 L96 108 L90 92 L70 92 L64 108 L56 102 C48 96 42 86 42 74 L42 56 C42 30 58 14 80 14 Z"
              [attr.fill]="'url(#' + id + 'casco)'"
              stroke="#d4af37"
              stroke-width="2.6"
              stroke-linejoin="round"
            />
            <path
              d="M58 40 C64 28 74 24 80 24"
              fill="none"
              stroke="#f1ece5"
              stroke-opacity="0.28"
              stroke-width="2.4"
              stroke-linecap="round"
            />
            <path
              d="M76.5 22 L83.5 22 L85 58 L82 94 L78 94 L75 58 Z"
              fill="#a8322a"
              stroke="#d4af37"
              stroke-width="1"
              stroke-linejoin="round"
            />
            <path
              d="M56 48 L76 53 M104 48 L84 53"
              fill="none"
              stroke="#d4af37"
              stroke-width="1.8"
              stroke-linecap="round"
            />
            <path
              d="M57 51 L76 56 L76 66 L60 64 Z M103 51 L84 56 L84 66 L100 64 Z"
              fill="#120a08"
            />
            <path d="M70 78 L90 78 L88 91 L72 91 Z" fill="#120a08" />
            <g class="ojos" data-p="ojos" data-ojos="abiertos">
              <path class="ojo" d="M62 58 L74 61 L74 64 L63 63 Z" />
              <path class="ojo" d="M98 58 L86 61 L86 64 L97 63 Z" />
            </g>
            <!-- las zetas del sueño -->
            <g
              data-p="zzz"
              opacity="0"
              fill="#d4af37"
              font-family="Barlow Condensed, Barlow, sans-serif"
              font-weight="700"
            >
              <text data-z="1" x="112" y="30" font-size="14">Z</text>
              <text data-z="2" x="124" y="14" font-size="19">Z</text>
              <text data-z="3" x="138" y="-4" font-size="25">Z</text>
            </g>
          </g>

          <!-- brazos: se redibujan cuadro a cuadro -->
          <g data-p="brazo-i">
            <path
              data-b="sombra"
              fill="none"
              stroke="#4a130e"
              stroke-width="19"
              stroke-linecap="round"
              stroke-linejoin="round"
            />
            <path
              data-b="carne"
              fill="none"
              stroke="#b83a2c"
              stroke-width="14.5"
              stroke-linecap="round"
              stroke-linejoin="round"
            />
            <path
              data-b="oro"
              fill="none"
              stroke="#d4af37"
              stroke-width="15.5"
              stroke-linecap="butt"
            />
            <circle data-b="puno" r="9" fill="#c0392b" stroke="#4a130e" stroke-width="2.4" />
          </g>
          <g data-p="brazo-d">
            <path
              data-b="sombra"
              fill="none"
              stroke="#4a130e"
              stroke-width="19"
              stroke-linecap="round"
              stroke-linejoin="round"
            />
            <path
              data-b="carne"
              fill="none"
              stroke="#b83a2c"
              stroke-width="14.5"
              stroke-linecap="round"
              stroke-linejoin="round"
            />
            <path
              data-b="oro"
              fill="none"
              stroke="#d4af37"
              stroke-width="15.5"
              stroke-linecap="butt"
            />
            <circle data-b="puno" r="9" fill="#c0392b" stroke="#4a130e" stroke-width="2.4" />
          </g>

          <!-- lo que sostiene -->
          <g data-p="barra" opacity="0">
            <line data-q="barra" stroke="#d4af37" stroke-width="4" stroke-linecap="round" />
            <g data-q="placa-i">
              <rect
                x="-9"
                y="-19"
                width="9"
                height="38"
                rx="2"
                fill="#a8322a"
                stroke="#4a130e"
                stroke-width="1.6"
              />
              <rect
                x="-14"
                y="-14"
                width="5"
                height="28"
                rx="2"
                fill="#8f2a1f"
                stroke="#4a130e"
                stroke-width="1.6"
              />
            </g>
            <g data-q="placa-d">
              <rect
                x="0"
                y="-19"
                width="9"
                height="38"
                rx="2"
                fill="#a8322a"
                stroke="#4a130e"
                stroke-width="1.6"
              />
              <rect
                x="9"
                y="-14"
                width="5"
                height="28"
                rx="2"
                fill="#8f2a1f"
                stroke="#4a130e"
                stroke-width="1.6"
              />
            </g>
          </g>
          <g data-p="vaso" opacity="0">
            <g [attr.clip-path]="'url(#' + id + 'vaso)'">
              <rect
                data-q="agua"
                x="-9"
                y="-26"
                width="18"
                height="24"
                fill="#7cc8f0"
                fill-opacity="0.9"
              />
            </g>
            <path
              d="M-8 -26 L8 -26 L6 -2 L-6 -2 Z"
              fill="#fff"
              fill-opacity="0.14"
              stroke="#f1ece5"
              stroke-width="1.6"
              stroke-linejoin="round"
            />
          </g>
          <g data-p="shaker" opacity="0">
            <rect
              x="-6.5"
              y="-31"
              width="13"
              height="29"
              rx="3"
              fill="#2b221c"
              stroke="#f1ece5"
              stroke-width="1.4"
            />
            <rect
              data-q="batido"
              x="-5"
              y="-30"
              width="10"
              height="27"
              rx="2"
              fill="#f1ece5"
              fill-opacity="0.9"
            />
            <rect x="-6" y="-17" width="12" height="4" fill="#d4af37" />
            <rect x="-5" y="-36" width="10" height="5" rx="1.5" fill="#d4af37" />
          </g>
          <g data-p="arepa" opacity="0">
            <g [attr.mask]="'url(#' + id + 'mordida)'">
              <circle cx="0" cy="-10" r="11.5" fill="#e8b84a" stroke="#b9801f" stroke-width="2" />
              <circle cx="-3" cy="-13" r="1.2" fill="#b9801f" />
              <circle cx="4" cy="-8" r="1.2" fill="#b9801f" />
              <circle cx="0" cy="-5" r="1.1" fill="#b9801f" />
              <circle cx="3" cy="-15" r="1" fill="#b9801f" />
            </g>
          </g>
        </g>
      </g>

      <!-- la luna al dormir -->
      <g data-p="luna" opacity="0">
        <path d="M14 -2 A12 12 0 1 0 28 18 A9.5 9.5 0 1 1 14 -2 Z" fill="#d4af37" />
      </g>
    </svg>
  `,
  styles: `
    :host {
      line-height: 0;
    }
    .g {
      width: 100%;
      height: 100%;
      overflow: visible;
    }
    .aura {
      opacity: 0;
      transform-origin: 80px 52px;
    }
    .ojo {
      fill: #f1ece5;
      transform-box: fill-box;
      transform-origin: center;
      transition:
        fill 0.4s,
        transform 0.2s;
    }
    [data-ojos='cerrados'] .ojo {
      transform: scaleY(0.12);
    }
    [data-ojos='esfuerzo'] .ojo {
      transform: scaleY(0.5) rotate(0deg);
      fill: #ffd54a;
    }
    .cresta,
    .cabeza,
    .todo {
      transition: transform 0.5s cubic-bezier(0.3, 1.4, 0.5, 1);
    }
    .cresta {
      transform-origin: 80px 18px;
      transform-box: view-box;
    }
    .cabeza {
      transform-origin: 80px 104px;
      transform-box: view-box;
    }

    /* descansa: cabeza baja, ojos cerrados y colores apagados */
    .descansa {
      filter: saturate(0.55) brightness(0.85);
    }
    .descansa .ojo {
      transform: scaleY(0.12);
    }
    .descansa .cabeza {
      transform: translateY(5px) rotate(4deg);
    }
    .descansa .cresta {
      transform: rotate(-12deg);
    }
    .descansa .todo {
      animation: respira 4.5s ease-in-out infinite;
    }

    /* firme: de pie, atento, parpadea de vez en cuando */
    .firme .todo {
      animation: respira 3.2s ease-in-out infinite;
    }
    .firme [data-ojos='abiertos'] .ojo,
    .celebra [data-ojos='abiertos'] .ojo {
      animation: parpadea 6s ease-in-out infinite;
    }

    /* celebra: ojos dorados y aura */
    .celebra .ojo {
      fill: #ffd54a;
      filter: drop-shadow(0 0 3px #d4af37);
    }
    .celebra .aura {
      opacity: 1;
      animation: aura 1.8s ease-in-out infinite;
    }
    .celebra .cresta {
      transform: translateY(-2px) scaleY(1.08);
    }

    @keyframes respira {
      50% {
        transform: translateY(-1.6px);
      }
    }
    @keyframes parpadea {
      0%,
      93%,
      100% {
        transform: scaleY(1);
      }
      96% {
        transform: scaleY(0.1);
      }
    }
    @keyframes aura {
      50% {
        transform: scale(1.07);
        opacity: 0.7;
      }
    }
    @media (prefers-reduced-motion: reduce) {
      .todo,
      .aura,
      .ojo {
        animation: none !important;
      }
    }
  `,
})
export class Guerrero implements OnDestroy {
  private anfitrion = inject<ElementRef<HTMLElement>>(ElementRef);

  readonly estado = input<EstadoGuerrero>('firme');
  readonly tamano = input(96);
  /** Qué está haciendo ahora: al cambiar se reproduce y, al terminar, avisa. */
  readonly accion = input<AccionGuerrero | null>(null);
  readonly terminada = output<void>();

  /** Para que cada dibujo tenga sus propios degradados y máscaras. */
  protected id = `g${++contador}-`;
  private cuadro = 0;
  private temporizador: ReturnType<typeof setTimeout> | null = null;
  private piezas = new Map<string, Element | null>();

  protected etiqueta = computed(() => {
    const accion = this.accion();
    if (accion) {
      return {
        agua: 'El guerrero toma agua',
        proteina: 'El guerrero se toma la proteína',
        comer: 'El guerrero come',
        dormir: 'El guerrero duerme',
        levantar: 'El guerrero se levanta',
        entrenar: 'El guerrero entrena',
      }[accion];
    }
    return {
      descansa: 'El guerrero descansa',
      firme: 'El guerrero está firme',
      celebra: 'El guerrero celebra',
    }[this.estado()];
  });

  constructor() {
    effect(() => {
      const accion = this.accion();
      untracked(() => (accion ? this.reproducir(accion) : this.reposar()));
    });
    afterNextRender(() => {
      if (!this.accion()) this.reposar();
    });
    // Con la pestaña oculta no se gasta nada.
    document.addEventListener('visibilitychange', this.alCambiarVisibilidad);
  }

  ngOnDestroy(): void {
    this.detener();
    document.removeEventListener('visibilitychange', this.alCambiarVisibilidad);
  }

  private alCambiarVisibilidad = (): void => {
    if (document.hidden && this.cuadro) this.terminar();
  };

  private pieza<T extends Element>(clave: string, selector: string): T | null {
    if (!this.piezas.has(clave))
      this.piezas.set(clave, this.anfitrion.nativeElement.querySelector(selector));
    return this.piezas.get(clave) as T | null;
  }

  private reproducir(accion: AccionGuerrero): void {
    this.detener();
    const duracion = DURACION_ACCION[accion];
    const guion = ACCIONES[accion];
    if (matchMedia('(prefers-reduced-motion: reduce)').matches) {
      // Sin movimiento: el momento clave quieto y listo.
      this.aplicar(guion(accion === 'dormir' ? 0.6 : accion === 'entrenar' ? 0.24 : 0.58));
      this.temporizador = setTimeout(() => this.terminar(), 1400);
      return;
    }
    const inicio = performance.now();
    const paso = (ahora: number) => {
      const t = lim((ahora - inicio) / duracion);
      this.aplicar(guion(t));
      if (t < 1) this.cuadro = requestAnimationFrame(paso);
      else this.terminar();
    };
    this.cuadro = requestAnimationFrame(paso);
  }

  private terminar(): void {
    this.detener();
    this.aplicar(REPOSO);
    this.terminada.emit();
  }

  private detener(): void {
    if (this.cuadro) cancelAnimationFrame(this.cuadro);
    if (this.temporizador) clearTimeout(this.temporizador);
    this.cuadro = 0;
    this.temporizador = null;
  }

  private reposar(): void {
    this.detener();
    this.aplicar(REPOSO);
  }

  /** Pone cada parte del dibujo donde dice la pose. */
  private aplicar(p: Pose): void {
    const raiz = this.anfitrion.nativeElement;
    const poner = (clave: string, selector: string, atributo: string, valor: string) =>
      this.pieza(clave, selector)?.setAttribute(atributo, valor);

    poner('cuerpo', '[data-p=cuerpo]', 'transform', `translate(0 ${p.cuerpoDy.toFixed(2)})`);
    const cabeza = this.pieza<SVGGElement>('cabeza', '[data-p=cabeza]');
    if (cabeza) {
      // Mientras se anima, la transición de CSS estorbaría: se apaga y se vuelve a prender en reposo.
      cabeza.style.transition = p === REPOSO ? '' : 'none';
      cabeza.style.transform =
        p === REPOSO
          ? ''
          : `translateY(${p.cabeza.dy.toFixed(2)}px) rotate(${p.cabeza.rot.toFixed(2)}deg)`;
    }
    this.pieza('ojos', '[data-p=ojos]')?.setAttribute('data-ojos', p.ojos);

    // Brazos: se dibujan solo si hace falta (en reposo se esconden las manos junto al pecho).
    this.brazo('brazo-i', HOMBRO_I, p.hi, -1, p.cuerpoDy);
    this.brazo('brazo-d', HOMBRO_D, p.hd, 1, p.cuerpoDy);

    // Objetos
    for (const nombre of ['vaso', 'shaker', 'arepa', 'barra'] as const) {
      poner(nombre, `[data-p=${nombre}]`, 'opacity', p.prop === nombre ? '1' : '0');
    }
    if (p.prop === 'vaso') {
      poner(
        'vaso-t',
        '[data-p=vaso]',
        'transform',
        `translate(${p.hd[0].toFixed(1)} ${(p.hd[1] + p.cuerpoDy).toFixed(1)}) rotate(${p.angulo.toFixed(1)})`,
      );
      const agua = this.pieza('agua', '[data-q=agua]');
      agua?.setAttribute('y', (-2 - 24 * p.nivel).toFixed(2));
    } else if (p.prop === 'shaker') {
      poner(
        'shaker-t',
        '[data-p=shaker]',
        'transform',
        `translate(${p.hd[0].toFixed(1)} ${(p.hd[1] + p.cuerpoDy).toFixed(1)}) rotate(${p.angulo.toFixed(1)})`,
      );
      const batido = this.pieza('batido', '[data-q=batido]');
      batido?.setAttribute('y', (-3 - 27 * p.nivel).toFixed(2));
      batido?.setAttribute('height', (27 * p.nivel).toFixed(2));
    } else if (p.prop === 'arepa') {
      poner(
        'arepa-t',
        '[data-p=arepa]',
        'transform',
        `translate(${p.hd[0].toFixed(1)} ${(p.hd[1] + p.cuerpoDy).toFixed(1)}) rotate(${p.angulo.toFixed(1)})`,
      );
      raiz
        .querySelectorAll('[data-m]')
        .forEach((m) =>
          m.setAttribute('opacity', Number(m.getAttribute('data-m')) <= p.mordidas ? '1' : '0'),
        );
    } else if (p.prop === 'barra') {
      const y = (p.hi[1] + p.hd[1]) / 2 + p.cuerpoDy;
      const barra = this.pieza('barra-l', '[data-q=barra]');
      barra?.setAttribute('x1', p.hi[0].toFixed(1));
      barra?.setAttribute('x2', p.hd[0].toFixed(1));
      barra?.setAttribute('y1', y.toFixed(1));
      barra?.setAttribute('y2', y.toFixed(1));
      poner(
        'placa-i',
        '[data-q=placa-i]',
        'transform',
        `translate(${(p.hi[0] - 6).toFixed(1)} ${y.toFixed(1)})`,
      );
      poner(
        'placa-d',
        '[data-q=placa-d]',
        'transform',
        `translate(${(p.hd[0] + 6).toFixed(1)} ${y.toFixed(1)})`,
      );
    }

    // Escenas
    poner('luna', '[data-p=luna]', 'opacity', p.luna.toFixed(2));
    poner('sol', '[data-p=sol]', 'opacity', p.sol.toFixed(2));
    poner('sol-t', '[data-p=sol]', 'transform', `translate(0 ${(100 - 100 * p.sol).toFixed(1)})`);
    poner('zzz', '[data-p=zzz]', 'opacity', p.zzz > 0 ? '1' : '0');
    raiz.querySelectorAll<SVGTextElement>('[data-z]').forEach((z) => {
      const i = Number(z.getAttribute('data-z'));
      const k = lim(p.zzz * 3 - (i - 1));
      z.setAttribute('opacity', (k * (1 - lim((p.zzz - 0.85) / 0.15))).toFixed(2));
      z.setAttribute('transform', `translate(${(-6 * k).toFixed(1)} ${(-10 * k).toFixed(1)})`);
    });
  }

  /** Dibuja un brazo con codo desde el hombro hasta la mano. En reposo la mano queda junto al pecho. */
  private brazo(clave: string, hombro: Punto, mano: Punto, haciaAfuera: 1 | -1, dy: number): void {
    const g = this.pieza<SVGGElement>(clave, `[data-p=${clave}]`);
    if (!g) return;
    const S: Punto = [hombro[0], hombro[1] + dy * 0.5];
    const H: Punto = [mano[0], mano[1] + dy];
    const C = codo(S, H, haciaAfuera);
    const d = `M${S[0].toFixed(1)} ${S[1].toFixed(1)} L${C[0].toFixed(1)} ${C[1].toFixed(1)} L${H[0].toFixed(1)} ${H[1].toFixed(1)}`;
    g.querySelector('[data-b=sombra]')?.setAttribute('d', d);
    g.querySelector('[data-b=carne]')?.setAttribute('d', d);
    // La muñequera dorada: el último cuarto del antebrazo.
    const m: Punto = [mezcla(C[0], H[0], 0.45), mezcla(C[1], H[1], 0.45)];
    const m2: Punto = [mezcla(C[0], H[0], 0.72), mezcla(C[1], H[1], 0.72)];
    g.querySelector('[data-b=oro]')?.setAttribute(
      'd',
      `M${m[0].toFixed(1)} ${m[1].toFixed(1)} L${m2[0].toFixed(1)} ${m2[1].toFixed(1)}`,
    );
    const puno = g.querySelector('[data-b=puno]');
    puno?.setAttribute('cx', H[0].toFixed(1));
    puno?.setAttribute('cy', H[1].toFixed(1));
  }
}
