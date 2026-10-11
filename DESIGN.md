# Design

Este archivo registra el mundo visual de la página pública (home) y cómo se lleva al resto de la app.

## Mundo: poco y nítido

Hero cinematográfico (referencia elegida por el usuario: hero "Portal" de dinamosites): los guantes colgados en el haz de luz a pantalla completa, titular compacto, un botón de vidrio y barra transparente. Después, un recorrido de cuatro estaciones fijas (comida, entreno, progreso, agenda) donde cada foto sube como el sol, una línea dorada marca el avance y cada estación muestra un pedazo real de la app. Cierre en la cumbre al amanecer.

## Color (comprometido, oscuro primero)

La escena: alguien en el celular de noche o de madrugada pensando en empezar. Por eso el fondo es noche cálida y la luz es la del amanecer de las fotos.

| Token | Valor | Uso |
|---|---|---|
| `--noche` | `#100d0b` | Fondo |
| `--tierra` | `#1b1511` | Superficies |
| `--hueso` | `#f6f1ea` | Texto principal |
| `--bruma` | `rgb(246 241 234 / 0.74)` | Texto secundario |
| `--oro` | `#d4af37` | Contador, etiquetas, detalles |
| `--rojo` | `#c0392b` | Tachado en la muestra de cambio |

## Tipografía

- Display: Barlow Condensed 700. Titular del hero clamp(62px, 6.9vw, 118px), interlineado 0.89, tracking -0.015em.
- Texto: Barlow 400/500, 17–19px, medida máxima 60ch.
- Números tabulares en contadores y cantidades.

## Composición

- Fotos a sangre completa con versión vertical para celular (`-movil.webp`).
- Texto a la izquierda sobre degradado de noche; el sujeto de la foto a la derecha.
- Botón principal de vidrio cálido: píldora de 62px de alto, borde blanco fino, blur 18px y reflejo interior; texto blanco centrado, sin icono.
- Barra transparente sobre el hero (logo y enlaces de texto), sin fondo sólido.
- Fotos en WebP de calidad alta (90) desde los originales.

## Movimiento

- Hero: al bajar, el texto se desvanece y sube un poco, la sombra se aclara y la escena se funde a noche.
- Estaciones: la foto sube con una cortina (clip-path) y se acerca suave; el titular entra con máscara; la línea dorada se llena; en el entreno se turnan boxeo, yoga y en casa.
- Secciones de texto: un fundido corto al llegar.
- Nada de partículas, destellos, rayos ni fotos animadas por código: si hay movimiento en la foto, viene de un video real.
- Todo se apaga con "reducir movimiento".

## Prohibido en este mundo

- Iconos o brillos de IA, destellos y partículas, degradados en el texto, tarjetas iguales de icono + título + texto.
- Testimonios, cifras o logos de clientes inventados.

## En el resto de la app

Lo que no se pierde: el rojo de la marca en lo activo y la acción, el modo claro y oscuro, la barra de abajo y lo práctico de cada pantalla. Lo que se trae del home:

- Modo oscuro en noche cálida (`dark-900 #100d0b`, `dark-800 #1b1511`, `dark-700 #2b221c`) y grises cálidos en toda la app (`styles.css`); PrimeNG con las mismas superficies (`guerrero-preset.ts`).
- Barlow en el texto y Barlow Condensed en `h1`/`h2`/`h3`.
- Portada con foto (`shared/portada`) arriba de cada sección: Nutrición (desayuno), Rutinas (boxeo), Progreso (cinta métrica), Consejos (en casa), Perfil (amarrarse los tenis). Baja (9.5rem) para no quitar espacio.
- Barras de arriba y abajo translúcidas con desenfoque; la sección activa en rojo con una rayita arriba.
- Entrar y registrarse sobre la foto de los guantes.
