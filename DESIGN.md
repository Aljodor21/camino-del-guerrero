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

## Los avisos se ven como notificaciones

- **Aviso de arriba:** una tarjeta flotante (redondeada, con sombra, ícono a la izquierda y botón de acción), no una barra a todo lo ancho. Solo uno a la vez, el más importante.
- **Bandeja de Pendientes:** una sola lista (lo más nuevo arriba), cada aviso con el color y el ícono de su tipo (agua celeste, proteína ámbar, dormir índigo, entreno rojo, comida verde, agenda violeta), un punto rojo de "sin atender" y cuándo llegó ("Ahora", "Hace 12 min", "Hace 2 h"). Un contador rojo en el título y en la campana; la campana se sacude un instante cada tanto mientras haya algo pendiente. Vacía dice "Estás al día".
- **En el celular (push):** ícono de estado de una sola silueta (`badge.png`), vibración, la hora a la que tocaba el aviso y el botón de confirmar en la propia notificación.

## Cómo se ordenan las secciones

Cada pestaña de abajo es una sola cosa y lo secundario va en la barra de pestañas de arriba, no en tarjetas sueltas:

- **Nutrición:** Menú · Mercado · Mi plan · Cumplimiento · Alimentos (la lista de intercambios).
- **Progreso:** Medidas · Agenda · Proyección ("¿cuánto puedo cambiar?", solo si el proceso incluye alimentación) · Sesiones (solo con entrenamiento). La proteína vive en la Agenda.
- La barra (`app-pestanas`) se desplaza hacia el lado si no caben todas y deja la activa a la vista; la sección elegida queda en la URL (`?seccion=`).
- Los enlaces viejos (`/cumplimiento`, `/lista-alimentos`, `/proyeccion`) redirigen a su pestaña conservando los parámetros (`?listo=desayuno`).

## Navegación y ventanas

- **Atrás:** en toda pantalla que no sea el inicio de una pestaña de abajo (Nutrición, Rutinas, Progreso, Consejos, Perfil; en admin, sus cuatro pestañas) aparece una flecha a la izquierda del logo. Vuelve a la pantalla de donde se venía, con su pestaña (`/progreso?seccion=agenda`); si se entró directo a esa pantalla, lleva al inicio de la primera sección.
- **Ventanas (`p-dialog`):** nunca hay que dejar un `transform` (ni el de cero) puesto en un contenedor de pantalla: vuelve a ese contenedor la referencia de los elementos de posición fija y la ventana se mide contra la pantalla y no contra el celular (salía cortada). Por eso las animaciones de entrada usan solo `backwards` (no `both`/`forwards`).
- **Fechas de un plan:** siempre se dice de qué es: "hasta cuándo dura tu proceso", "fecha en que termina tu plan", "tu próximo control", "sin fecha por ahora" (no "va hasta" ni "sin definir" a secas).

### Actualizar sin salir de la app

Dentro de la app instalada el botón "Actualizar a la X" no abre el navegador: un plugin propio de Android (`ActualizadorPlugin.java`) baja el APK desde nuestro dominio con una barra de progreso ("Descargando la actualización… 60 %"), comprueba que sea de esta misma app (mismo paquete) y abre el instalador de Android, donde la persona toca "Instalar" y la app se actualiza encima, con su sesión y sus datos. Estados: descargando (barra), "Descarga lista · Toca «Instalar» en la pantalla de Android", "Falta un permiso" (la primera vez Android pide activar "Permitir de esta fuente"; se abre la pantalla de ajustes y se vuelve a tocar Actualizar) y error ("No pudimos descargarla" + reintentar + "Descargarla con el navegador"). Android no instala en silencio una app de fuera de la Play Store: la confirmación es siempre de la persona.

## Cuando el servidor no responde

- **Una sola tarjeta para toda la app** (`app-servidor-caido`), sobre la barra de abajo y sin tapar lo que se lee: "No podemos conectar con el servidor" o "Sin internet", la tranquilidad de que los datos están a salvo, un botón "Reintentar" y "Reintentando solos". Cuando vuelve la conexión se retira sola y deja 3 segundos una tarjeta verde "Conexión recuperada".
- **Cómo lo sabe:** el interceptor `servidorInterceptor` cuenta las respuestas de nuestra API. Dos fallos seguidos (sin respuesta, 502, 503 o 504) la marcan como caída; cualquier respuesta (incluso un 400 o 401: el servidor contestó) la recupera. Mientras está caída se sondea cada 8 segundos `/api/app/version/` con `fetch`.
- **nginx:** si el backend está apagado, `/api/` contesta un JSON claro (`503 {"detail": ...}`) en vez de una página HTML de error.
- **404:** una ruta que no existe muestra la página 404 (video del guerrero). Si no carga ni el sitio (el túnel o uburoom apagados), lo que se ve es la página de error de Cloudflare: eso no lo controla la app; la app instalada, en cambio, sí carga (va empaquetada) y muestra esta tarjeta.

## Avisos, una sección propia

- **Cabecera propia, no la foto de las demás pantallas:** el icono de la campana en rojo, "Avisos" y una línea que dice cuántos faltan ("2 sin atender") o "Estás al día". Fondo con un tinte cálido arriba y llega desde la derecha (sin dejar un `transform` puesto).
- **Tres pestañas:** Pendientes (con su contador rojo; la ayuda y la bandeja), Tu día (el agua, la proteína, el entreno y la hora de dormir) y Ajustes (agua, horas, qué avisos llegan y las notificaciones del celular). La pestaña queda en la URL.
- **El aviso del agua dice cuánto llevas hoy** ("Llevas 1 de 4 vasos de hoy (600 ml cada uno)"), no el número del recordatorio: el texto se arma al mostrarlo, tanto en la app como en el push.
- **El aviso de arriba (el que sale en todas las pantallas):** va dentro de la página, nunca flota ni tapa el título. Si pide algo es una tarjeta tranquila con un botón de texto (Registrar, Actualizar…); si solo informa ("Tu proceso inicia el martes") es una línea discreta, sin caja ni botón.
- **Barra de pestañas:** flecha "›" mientras queden pestañas a la derecha y "‹" cuando se pueda volver a la izquierda; tocarlas desplaza la barra.

## Notificaciones en el celular

- **Ajustes de Avisos › Notificaciones en este dispositivo** cambia según dónde se abra: en la app instalada, "Activar notificaciones" (pide el permiso de Android), "Activas" con cuántas hay programadas y una nota sobre el ahorro de batería, o cómo desbloquearlas si se negaron; en el navegador, el web push de siempre.
- **El aviso de arriba invita a activarlas** ("Activa las notificaciones para que los avisos te lleguen aunque la app esté cerrada") mientras estén sin activar en la app instalada.
- **En la barra de estado:** una campana blanca de una sola silueta, que es lo que Android permite, tintada del rojo de la marca. Al tocar una notificación se abre la bandeja de Avisos.

## Auditoría (administrador)

- **Pantalla `/admin/auditoria`**, con Resumen y Huellas, y con filtros de periodo (Hoy, 7, 30 y 90 días), desde dónde (todos, app instalada, navegador), solo errores, buscar una ruta y mostrar las revisiones automáticas que la app hace sola cada minuto (ocultas por defecto).
- **Resumen:** consultas, personas, errores, actividad por día, dispositivos (modelo, sistema, cuántas personas, última vez), versiones de la app en uso, personas con su última vez, lo que más se consulta (con errores y tiempo medio) y las pantallas más abiertas.
- **Huellas:** una fila por cada una, con método y ruta, el resultado en una etiqueta (verde bien, ámbar error de quien pidió, rojo falla del servidor), la hora, quién, desde dónde y la IP; "Ver más" sigue desde donde quedó.

## Cumplimiento, en Avisos

- **Vive en Avisos** como cuarta pestaña ("Cumplimiento"), con Día · Semana · Mes · Trimestre y flechas para ir a periodos anteriores ("Volver a hoy" cuando se aleja).
- **Un anillo con el porcentaje** (verde desde la meta del 80 %, ámbar entre 50 y 79 %, rojo por debajo) y una frase que dice qué significa. En el día, una barra por cada parte (agua, dormir, y con el proceso en marcha comidas, proteína y entreno) con el dato real ("1500 de 2000 ml").
- **Semana, mes y trimestre:** racha, mejor racha y días que llegaron a la meta; un calendario de casillas de color por día (tocar una muestra su detalle); y "Dónde se te fue", la lista de lo que faltó en los días ya cerrados.
- **Antes de empezar el proceso** solo cuentan el agua y dormir; así se puede abrir la app desde el primer día y llegar al 100 %. Con el proceso en marcha entran las comidas (40 %), el entreno (20 %), la proteína (15 %), el agua (15 %) y dormir (10 %); lo que no aplica ese día no pesa.

## Notificaciones por Firebase

- **Ajustes de Avisos** dice por dónde llegan: «cada aviso te llega a su hora desde el servidor, aunque pasen los días sin abrir la app» (Firebase) o «tu celular las programa y suenan a su hora…, ahora hay N programadas» (respaldo). Con Firebase activo aparece «Enviar una de prueba» y un mensaje de si se entregó.
- **Una sola vía a la vez:** con Firebase no se programa nada local, para que un aviso no suene dos veces. Con la app abierta Android no muestra la notificación: la bandeja se actualiza sola.
- **El botón dentro de la notificación** («Ya lo tomé», «Ya me la tomé», «Ya me acosté», «Ya entrené», «Listo»): anota el dato sin abrir la app y la notificación pasa a «Anotado» unos segundos. Si falla (sin conexión), dice «No pudimos anotarlo. Ábrela para confirmar.» y al tocarla se abre Avisos. Las de comida y control no llevan botón: se resuelven dentro de la app.
- **En el navegador, con la app ya instalada:** Ajustes dice «Ya tienes la app instalada: los avisos te llegan ahí y no se repiten en el navegador», en vez de ofrecer activar las notificaciones del navegador.
- **Con la app abierta o cerrada** la notificación se ve igual: la arma el propio servicio de la app (Android no muestra solo las de Firebase con la app abierta), con el color y la campana de la marca.

## Logros y celebraciones

- **El guerrero** es el del logo, de busto y dibujado a mano en SVG (sin imágenes): casco rojo con cresta, ojos que brillan y filo dorado. Tiene tres estados según el avance del día: descansa (menos del 30 %: cabeza baja, ojos cerrados, colores apagados), firme (de pie, atento) y celebra (desde la meta del 80 %: ojos dorados, un aura y tres saltos).
- **Avisos › Logros** (quinta pestaña): arriba el guerrero con su frase, los días seguidos de racha, la mejor racha y el anillo del día; un aviso del **comodín de la semana** (disponible o usado; se renueva el lunes); el **capítulo de la semana** como un camino de siete estaciones, una por día, con su color (verde, ámbar o rojo), el título de la semana, lo que subiste o bajaste frente a la anterior, el mejor día y qué mirar la próxima; y la cuadrícula de **hitos** con filtro (todos, logrados, por lograr).
- **Medallas** en forma de escudo, como el del logo, con un dibujo por grupo (racha, días completos, agua, entreno, comida, proteína, medición) y borde de bronce, plata u oro según el nivel. Las que faltan se ven apagadas y con su borde punteado; debajo dicen cuánto falta o cuándo se lograron.
- **Anillo del día** en la cabecera de Avisos (toca para ir a Logros): da un salto cada vez que se anota algo y cambia de color con el avance.
- **Al anotar algo:** salto del anillo, vibración corta y, si se activa, un sonido suave. Ajustes › «Al anotar algo» enciende o apaga vibración (encendida) y sonido (apagado).
- **Celebraciones** (una tarjeta con el guerrero o la medalla y un confeti rojo, dorado y crema): al cerrar el día al 100 % (una vez por día) y al lograr un hito nuevo. Se cierran con «Seguir», Escape o tocando fuera. Con «reducir movimiento» no hay confeti ni saltos.
- **Sin culpa:** el comodín evita que un mal día borre todo; una semana sin terminar no se califica («Así va tu semana»); y ningún hito premia comer menos, pasarse de agua ni saltarse comidas.

## Sueño

- **Avisos › Tu día** trae una sección «Sueño» con la hora a la que te levantaste (o la que tienes como meta), cuánto dormiste anoche, el promedio de los últimos 7 días y dos botones: **Me levanté** y **Ya me acosté**. Cada botón desaparece cuando ya anotaste esa hora.
- **Aviso de la mañana:** «Buenos días: ¿ya te levantaste?» a tu hora de levantarte, con el botón «Ya me levanté» (también dentro de la notificación del celular). Se apaga en Ajustes › Avisos que quiero recibir › Levantarme.
- **Avisos › Cumplimiento** muestra una tarjeta «Sueño» con el promedio del periodo y una barra por noche (10 horas llenan la barra), con la aclaración de que es aproximado.
- **Sin inventar metas:** no se califica si dormiste «bien» o «mal»; solo se muestra lo que anotaste.

## El porcentaje de un periodo

- **En una semana, un mes o un trimestre el anillo muestra lo que llevas del periodo entero**, no el promedio de los días que van: dos días al 100 % en una semana son el 29 % de la semana (2 de 7), y debajo dice «En los días que van, tu promedio es 100 %». Así el porcentaje sube a medida que pasan los días y nunca engaña. En un día, o en un periodo ya cerrado, las dos cuentas dan lo mismo.
- **El capítulo de la semana** hace igual: una semana a medias dice «N % de la semana» y «Van X de 7 días», y no se compara con la anterior hasta que termina.

## La app siempre al día

- **Sin cerrar y abrir:** la app se vuelve a cargar sola cuando cambia el día (a medianoche con la app abierta, o al volver a ella) y cuando se regresa después de más de 10 minutos en segundo plano. Si en ese momento hay un campo con texto o una ventana abierta, espera a que termine para no borrar lo que se escribe.
- **Fotos de la comida:** «Tomar foto» abre la cámara y «Galería» deja elegir una que ya exista. La app declara el permiso de cámara (sin él, Android solo ofrecía la galería).
- **Un solo «Cumplimiento»:** el de Avisos es el del día completo (agua, dormir, comidas, proteína y entreno); el de Nutrición se llama «Lo que comí» y muestra qué grupos de la minuta faltaron. Desde el día, la tarjeta de comidas enlaza a ese detalle.

## Mis horas

- **Ajustes › A qué hora comes:** una hora por cada comida del plan (con «Volver a las 7:00» si la cambiaste). El aviso «¿Cómo te fue con…?» llega **45 minutos después** de esa hora, no a la hora de comer.
- **Ajustes › Horas distintas según el día:** una fila por día de la semana, con una hora de levantarte y otra de acostarte; lo vacío usa la de siempre. Está plegado para no estorbar.
- **Tu día › Sueño:** debajo de los botones, «Hoy: te levantas a las 6:30 · mañana: a las 5:00 (cambiada)» y dos enlaces, «Cambiar las de hoy» y «Cambiar las de mañana», que abren las dos horas de ese día con «Guardar» y «Volver a la de siempre».
- **Frente a lo previsto:** «Anoche te acostaste 30 min antes de lo previsto. Hoy te levantaste 15 min después de lo previsto» (a menos de 5 minutos dice «a la hora prevista»). En Cumplimiento, la tarjeta de sueño agrega el promedio de esas diferencias.

## El porcentaje de un periodo

- **En una semana, un mes o un trimestre el anillo muestra lo que llevas del periodo entero**, no el promedio de los días que van: dos días al 100 % en una semana son el 29 % de la semana (2 de 7), y debajo dice «En los días que van, tu promedio es 100 %». Así el porcentaje sube a medida que pasan los días y nunca engaña. En un día, o en un periodo ya cerrado, las dos cuentas dan lo mismo.
- **El capítulo de la semana** hace igual: una semana a medias dice «N % de la semana» y «Van X de 7 días», y no se compara con la anterior hasta que termina.

## Avisos que siguen tu día

- **Las comidas no tienen hora fija:** el desayuno es una hora después de levantarte, la última comida dos horas antes de acostarte y las demás se reparten entre las dos, solo con las comidas de tu plan. Si hoy te levantaste tarde y lo anotaste, todo se corre. Mientras no digas que te levantaste (y no pase tu hora más 3 horas), la app no te pregunta por el desayuno.
- **Todo lo anterior es opcional:** en Ajustes puedes poner tu hora para cada comida («A qué hora comes (opcional)»), el rango del agua («Tomar agua entre», vacío = de una hora después de levantarte a una antes de acostarte) y tus horas por día.
- **Pendientes de la agenda y obligatorios:** con hora, avisan una hora, media hora y un cuarto de hora antes y en el momento («En 1 hora: Control…», «En 30 minutos…», «En 15 minutos…», «Ahora…»). Cada aviso reemplaza al anterior: en la bandeja queda solo el último y en la barra del celular se cambia la misma notificación. Sin hora, avisan a las 8:00 de ese día (y el día antes, si lo pediste).
- **«Según cómo usas la app»:** en Ajustes, una tarjeta ámbar con cambios que la app propone (p. ej. «Sueles contar el desayuno cerca de las 9:30, así que comes hacia las 8:45; hoy lo tienes a las 7:00») con «Cambiar» y «Así está bien». Solo aparece con datos suficientes y si la diferencia es de 30 minutos o más.

## El guerrero que acompaña

- **Siempre ahí:** una esquina de la pantalla (arriba de la barra de abajo) tiene al guerrero en miniatura con los días de racha en una insignia dorada. Al tocarlo dice cuántos días lleva, cuánto va hoy y cuántos puntos faltan para sostener la racha, con un enlace a Logros. No se repite en la pestaña de Logros, donde ya está en grande.
- **Hace lo que tú haces:** al anotar algo, crece y lo actúa un par de segundos, con una frase. Toma agua (levanta el vaso, lo inclina y toma tres tragos mientras baja el nivel), se toma la proteína (agita el shaker con las dos manos y toma), come (muerde una arepa tres veces y mastica), duerme (inclina la cabeza, cierra los ojos y salen las zetas con la luna), se levanta (abre los ojos, se estira con el sol saliendo) y entrena (levanta la barra tres veces con cara de esfuerzo).
- **Cómo está hecho:** un solo SVG dibujado a mano, sin imágenes ni librerías. Los brazos son de dos huesos con codo, que se recalculan cuadro a cuadro mientras dura la acción, así la mano llega a la boca o a la barra sin trucos; el resto del tiempo no se mueve más que respirar y parpadear. Con «reducir movimiento» se queda en el momento clave sin moverse.
- **Tres estados** según cuánto va el día: descansa (menos de la mitad de la meta), firme y, desde el 50 %, celebra.
- **La racha, en grande** (Avisos › Logros): el número a todo lo alto en dorado, «días de racha», qué falta hoy, la barra hacia la próxima meta (3, 7, 14, 30, 60, 90 días) y los dos pilares del día.
- **La regla:** un día cuenta para la racha desde el 50 %; por debajo, se pierde (el comodín de la semana perdona un día). El día vale por dos pilares iguales, **alimentación** (comidas, proteína, agua y dormir) y **deporte** (entreno, solo si ese día toca); si no toca entrenar, vale solo la alimentación.

