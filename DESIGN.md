# Design

Este archivo registra el mundo visual de la página pública (home) y cómo se lleva al resto de la app.

## Mundo: poco y nítido

Hero cinematográfico (referencia elegida por el usuario: hero "Portal" de dinamosites): los guantes rojos sobre negro a pantalla completa, con una animación que arranca con el primer scroll y sigue en bucle mientras el hero se vea (se pausa fuera de pantalla): vendas y cuerdas estallan alrededor de los guantes en una nube de magnesio. Es un video H.264 sin audio por orientación (`frontend/public/home/hero.mp4` 1920×1080 y `hero-movil.mp4` 1080×1920, 24 cuadros por segundo, hechos desde los originales con CRF 23 y 25) que decodifica el chip del celular, mucho más fluido que dibujar cuadros con JavaScript; el primer cuadro (`hero-poster*.webp`) es el que se ve al cargar, y con "reducir movimiento", ahorro de datos o una conexión lenta se queda ese cuadro quieto (dentro de la app instalada el video va empaquetado, solo la versión vertical). Titular al costado en escritorio, arriba en celular, y se desvanece al empezar a bajar. Barra transparente. Después, un recorrido de cuatro estaciones fijas (comida, entreno, progreso, agenda) donde cada foto sube como el sol, una línea dorada marca el avance y cada estación muestra un pedazo real de la app. Cierre en la cumbre al amanecer.

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

- Hero: al bajar, el texto se desvanece y sube un poco, y la foto se oscurece sin apagarse (nunca queda una pantalla vacía): el bloque "¿No sabes por dónde empezar?" sube por encima de ella.
- Las tres preguntas son un camino: una línea dorada se llena al bajar y cada pregunta llega con su punto.
- Cada estación trae una demo viva que muestra qué hace (cambio de alimento, temporizador de una serie, día uno contra hoy, avisos que llegan y se marcan); solo se mueve con la estación activa.
- Estaciones: la foto sube como una ventana que se abre (la ventana sube con `translate` y la foto baja lo mismo para quedar quieta: así no se repinta en cada cuadro, que era lo que trababa los Android) y se acerca suave; el titular entra con máscara; la línea dorada se llena; en el entreno se turnan boxeo, yoga y en casa.
- Secciones de texto: un fundido corto al llegar.
- Nada de partículas, destellos, rayos ni fotos animadas por código: si hay movimiento en la foto, viene de un video real.
- Todo se apaga con "reducir movimiento".

## En la app: ayuda que se ve

`shared/ayuda`: en cada pantalla, una tarjeta "para qué sirve y cómo se usa" con tres pasos y una animación corta que muestra qué hace (menú, mercado, plan, avisos, cumplimiento, proyección, proteína, medidas, agenda). Se abre sola la primera vez y queda recogida. Las animaciones se pausan al cerrarla y se apagan con "reducir movimiento". Movimiento general: la pantalla entra con un fundido breve y los botones se hunden al tocarlos.

## 404

Pantalla completa con la animación del guerrero y el poste que dice 404; por encima, solo la barra de arriba y el pie, transparentes. Hay dos videos sin audio, cada uno con su cuadro fijo: horizontal (`404.mp4`, `404-poster.webp`) y vertical (`404-movil.mp4`, `404-movil-poster.webp`); se usa el que corresponde a la orientación de la pantalla y se cambia solo si gira. Con "reducir movimiento" queda el cuadro fijo.

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

## Descargar la app

Pantalla dentro de la app (`/descargar-app`, también un aviso arriba y un acceso en Perfil) para bajar la última versión del APK. La cabecera es oscura en cualquier tema, con el mismo botón de vidrio del home: titular "Tu camino, en el bolsillo.", versión, peso y fecha del último release en números tabulares (el valor en oro), y un celular con el primer cuadro de los guantes y un aviso de ejemplo ("En media hora, a dormir") que sube y baja, todo quieto con "reducir movimiento". Debajo, tres pasos sobre una línea dorada, como el camino del home. Estados: buscando, lista, sin versión todavía (con reintento), iPhone (solo Android, con la alternativa de agregar a pantalla de inicio) y dentro de la app instalada (no se ofrece). La lectura del release usa `fetch` y no `HttpClient`, para que el interceptor del JWT no le mande el token de la sesión a GitHub.

### Dónde se ve la descarga

La tarjeta de descarga es un componente compartido (`app-descarga-apk`) que se usa en tres lugares: la pantalla `/descargar-app` (con los tres pasos), una sección del home **solo con la sesión iniciada, cualquiera sea el rol** (antes del cierre; el visitante no la ve), y el acceso de arriba (icono de celular en la barra, para todos los roles; en iPhone no se ofrece). El aviso de arriba y la tarjeta de Perfil también aparecen para el admin. Dentro de la app instalada sirve para actualizar ("Mantén tu app al día", botón "Descargar la última versión"): la app no se actualiza sola.

La versión, el peso y la fecha del último APK los lee nuestro servidor (`/api/app/version/`, con caché de 10 minutos) y no el navegador: Cloudflare le pone al sitio un `Content-Security-Policy: connect-src 'self'` que le prohíbe hablar con GitHub. Si no hay datos pero sí enlace, el botón de descarga se muestra igual, sin versión. En celular la tarjeta es compacta: botón de ancho completo en una sola línea y el celular de muestra asomando por abajo, con los guantes visibles.

El botón descarga desde nuestro propio dominio (`/api/app/descargar/`): un enlace a GitHub salta de página en el celular. En la app instalada, el enlace abre el navegador del sistema (el WebView no maneja descargas), que baja el archivo y la app se actualiza al instalarlo.

### La app instalada sabe si está actualizada

Dentro de la app (Android) la pantalla de descarga lee la versión instalada (plugin oficial `@capacitor/app`, `App.getInfo()`; el `versionName` es `1.0.<número de corrida>`) y la compara con la última publicada, número a número (1.0.5 < 1.0.12):
- **Al día:** barra verde con un check: "Estás actualizado · Tienes la versión 1.0.5, que es la última", y un enlace discreto para descargar de nuevo.
- **Una versión atrás:** alerta ámbar "Hay una versión nueva · Tienes la 1.0.5 y la última es la 1.0.7" y el botón "Actualizar a la 1.0.7"; además un punto rojo en el icono del celular de la barra de arriba y, cuando no haya otro aviso más importante, la tarjeta flotante "Hay una versión nueva de la app" (se cierra y no vuelve hasta que salga otra versión).
- **Sin saber la versión** (sin red, o en la web): el botón de siempre. En la web de un celular Android se ofrece "Descargar para Android"; en el computador, copiar el enlace.

## Navegación y ventanas

- **Atrás:** en toda pantalla que no sea el inicio de una pestaña de abajo (Nutrición, Rutinas, Progreso, Consejos, Perfil; en admin, sus cuatro pestañas) aparece una flecha a la izquierda del logo. Vuelve a la pantalla de donde se venía, con su pestaña (`/progreso?seccion=agenda`); si se entró directo a esa pantalla, lleva al inicio de la primera sección.
- **Ventanas (`p-dialog`):** nunca hay que dejar un `transform` (ni el de cero) puesto en un contenedor de pantalla: vuelve a ese contenedor la referencia de los elementos de posición fija y la ventana se mide contra la pantalla y no contra el celular (salía cortada). Por eso las animaciones de entrada usan solo `backwards` (no `both`/`forwards`).
- **Fechas de un plan:** siempre se dice de qué es: "hasta cuándo dura tu proceso", "fecha en que termina tu plan", "tu próximo control", "sin fecha por ahora" (no "va hasta" ni "sin definir" a secas).
