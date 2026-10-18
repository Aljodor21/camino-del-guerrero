# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project layout

Monorepo with two independent apps:
- `backend/` — Django 6 + DRF REST API. Run every `manage.py` command from inside `backend/`.
- `frontend/` — Angular 21 + PrimeNG + Tailwind v4 SPA. Angular/TypeScript conventions live in `frontend/.claude/CLAUDE.md` (auto-loaded when working there) — follow them; don't restate them here.

Real versions come from `backend/requirements.txt` and `frontend/package.json`, not the README (README says "Django 5" but it is actually **Django 6.0.3**).

## Backend

- Config via `python-decouple`, read from `backend/.env` (not committed). Keys: `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, `DB_*`, `AI_PROVIDER`/`AI_BASE_URL`/`AI_MODEL`/`AI_API_KEY`, optional `YOUTUBE_API_KEY`, `GIPHY_API_KEY`.
- Custom user model: `AUTH_USER_MODEL = 'users.Usuario'`.
- Custom management commands: `python manage.py crear_admin`, `python manage.py limpiar_db`.
- Fixtures at `backend/fixtures/initial_data.json` are loaded automatically on Docker startup.
- `TIME_ZONE = 'America/Bogota'`. Date fields use `default=timezone.localdate` (never `auto_now_add`) to respect the timezone — do the same in new models.
- All AI calls go through `core/ai_service.py` (`AIService`), which abstracts the provider: `AI_PROVIDER=anthropic` calls Claude through the official `anthropic` SDK; `AI_PROVIDER=ollama` hits `/api/generate`; anything else hits an OpenAI-compatible `/v1/chat/completions`. Prompts return JSON parsed leniently by `_chat_json` (tolerates markdown fences and `<think>` blocks, retries on 429). Switch models via env only — don't hardcode a provider or model.

## Avisos y notificaciones

Los avisos (agua, tomas de proteína, dormir, entreno, recordatorios) los arma `agenda/notificaciones.py`: se crean a su hora, quedan pendientes en la app **hasta que el usuario confirma** y al confirmar se guarda el dato en `RegistroHabito` (inmutable). El envío al celular (web push) lo hace `python manage.py enviar_avisos --cada 60` (servicio `avisos` en `docker-compose.yml`) y necesita `VAPID_*` en `.env.docker` (se generan con `python manage.py llaves_push`). El service worker es `frontend/public/sw.js`. Eso es solo para el navegador: en la app instalada (Capacitor) el web push no existe: ahí los avisos salen por Firebase (FCM, `agenda/fcm.py`: API HTTP v1 con la cuenta de servicio en `FIREBASE_CREDENCIALES_B64`; cada celular se registra en `TokenCelular` con `POST /api/agenda/push/celular/`) y, si Firebase no está disponible, el celular programa sus propios avisos con `@capacitor/local-notifications` a partir de `GET /api/agenda/avisos/proximos/` (`notificaciones.proximos`). Los mensajes de Firebase van solo con datos y el servicio nativo `AvisosMessagingService` arma la notificación con el botón de confirmar (`ConfirmarReceiver`, firma de `notificaciones.firmar`). `NotificacionesCelularService` (frontend) decide cuál usar; con Firebase activo no se programa nada local para no repetir. Los avisos de comida (`tipo='comida'`) no se confirman a ciegas: se resuelven al contar lo que se comió (`nutricion/comidas.py`, `RegistroComida`), que se compara con la minuta para el porcentaje de cumplimiento; la foto es opcional, privada y de apoyo (el porcentaje sale de lo que el usuario marca).

## Auditoría

La app `auditoria` deja una huella (`Evento`, inmutable) por cada consulta a `/api/` (middleware `AuditoriaMiddleware`) y por cada pantalla que abre la persona (`POST /api/auditoria/pantalla/`): quién, ruta (con su forma, para agrupar), resultado, duración, IP y dispositivo (se interpreta del User-Agent y de las cabeceras `X-Cliente` y `X-App-Version` que manda la app). Nunca guarda cuerpos de peticiones, fotos ni claves; la consulta tapa valores sensibles. Solo el administrador la ve (`/api/auditoria/eventos|resumen/`, pantalla `/admin/auditoria`). `limpiar_auditoria` borra lo de más de 90 días y lo corre el servicio `avisos` una vez al día.

## Sueño

`RegistroHabito` tiene los tipos `dormir` («me acosté») y `levantar` («me levanté», una vez al día; viene del aviso `levantar` a la hora de levantarse de `Habitos` o del botón). Los avisos de levantarse y de acostarse solo valen cerca de su hora (`VIGENCIA_DEL_MOMENTO`, 90 minutos): pasado ese rato no se crean —aunque la app los calcule por primera vez, por ejemplo tras un cambio— y los pendientes se quitan solos sin inventar ningún registro. `agenda/sueno.py` calcula las noches (de la última hora de acostarse a la de levantarse, entre 1 y 16 horas) y el promedio; no se guarda nada. `POST /api/agenda/registros/levantar|dormir/` anotan **la hora de ahora**: es un valor y no se cambia a mano (para no engañarse). Si hubiera más de un registro del mismo día (datos viejos), vale el último (por `id`). `GET /api/agenda/sueno/?desde=&hasta=`.

## Mis horas

`agenda/horarios.py` resuelve las horas de cada día. Levantarse y acostarse: manda lo de ese día (`HorarioDia`), luego el día de la semana (`Habitos.horas_semana`) y luego la hora general. **Comidas** (`horas_de_comidas`): solo las del plan; el desayuno es una hora después de levantarse (la hora real anotada hoy, si la hay) y la última dos horas antes de acostarse, con el mismo espacio entre una y otra (como el agua); lo que la persona puso en `Habitos.horas_comida` manda. Mientras no anote que se levantó (y no pasen 3 horas de su hora prevista), las comidas y tomas de hoy ligadas a una comida se retienen. El aviso de contar una comida sale 45 minutos después. El agua usa `Habitos.horas_agua` o levantarse + 1 h / acostarse − 1 h.

**Pendientes con hora** (`_avisos_de_recordatorio`): avisan 60, 30 y 15 minutos antes y en el momento (`ETAPAS_RECORDATORIO`); todos llevan `datos.grupo`, y cada uno reemplaza al anterior (se resuelven solos los hermanos pendientes en la bandeja; en el celular comparten `tag`/`clave`). **Sugerencias de horas** (`agenda/sugerencias_de_horas.py`, no confundir con `sugerencias.py`, que arma los recordatorios de suplementos): con 5 o más días de datos en las últimas 3 semanas propone cambiar la hora de una comida, del rango del agua, de levantarse o de acostarse si se aparta 30 minutos o más; solo propone, la persona decide.

## El día y la racha

`agenda/cumplimiento.py` mide el día en dos pilares iguales: alimentación (comidas 40, proteína 15, agua 15, dormir 10, repartidos entre sí) y deporte (el entreno, solo si ese día toca); un día sin entreno vale solo por la alimentación. Un día cuenta para la racha desde `UMBRAL_RACHA = 50`; por debajo se pierde (el comodín de la semana lo perdona una vez). En el frontend, `app-guerrero` (SVG propio, acciones con brazos de dos huesos calculados por cuadro) y `app-companero` (en el layout) lo muestran; `CelebracionesService.registro(accion)` hace que el guerrero actúe lo que se anotó.

## Logros

`agenda/logros.py` calcula siempre (no guarda contadores) la racha con comodín (un día corto por semana lunes a domingo no la rompe), los hitos y el capítulo semanal a partir de lo registrado, que no se edita; solo `HitoVisto` recuerda qué hitos ya se celebraron (los de hace más de 2 días se dan por vistos sin fiesta). Ningún hito premia comer menos, pasarse de agua ni saltarse comidas. Endpoints: `GET /api/agenda/logros/`, `POST /api/agenda/logros/vistos/`, `GET /api/agenda/capitulo/?lunes=`. En el frontend, `CelebracionesService` decide cuándo celebrar y `app-guerrero` (SVG propio con tres estados), `app-medalla` y `app-anillo` lo dibujan.

## Domain language

The domain is written in **Spanish**: model names, fields, API paths, AI prompts, and commit messages. Keep new domain code, fields, and prompts in Spanish to match.

## Docker / deploy

Root `Makefile` wraps Docker Compose with `--env-file .env.docker`: `make build` (build + up), `make up`, `make down`, `make restart`, `make logs`, `make ps`. Copy `.env.docker.example` → `.env.docker` first. Deploy target is a CasaOS home server.

## Commits

Commit messages are in Spanish and carry only the author's own name — do **not** add a `Co-Authored-By: Claude` trailer.

## Relevant skills (installed, auto-activate)

`django-expert` (models, DRF, ORM), `db-schema-conventions` + `postgresql-database-engineering` (schema/migrations), `ui-design-quality` (Angular + PrimeNG + Tailwind screens), `post-sprint-review` (after long AI-coding sessions), `pre-deploy-security-checklist` (before deploying).

**Aviso a la hora de comer:** cada comida del plan avisa dos veces, «Es hora de…» a su hora (`clave …:hora`) y «¿Cómo te fue?» 45 minutos después; comparten `datos.grupo`, así el segundo reemplaza al primero. Si la comida ya se contó no se avisa nada, y si el segundo ya le tocaba al calcular, el primero no se crea.

## Proteína con su comida, horas por día y repeticiones

Una toma que reemplaza algo de su comida (`toma.reemplaza` no vacío, comida del plan) sale del aviso con `datos.unida`: sin botón de confirmar (`accion_de` vacío, `confirmar` la rechaza) y lleva a `/comidas/contar`, donde la misma pantalla pregunta por la proteína (`tomas`), por el resto de la comida y pide una sola foto; `notificaciones.registrar_tomas_de_comida` guarda la toma y cierra su aviso en la misma transacción. Las horas de levantarse y acostarse son **una general o una por cada día** (`Habitos.horas_semana` vacío o con los siete días completos; el serializador lo exige) y la pantalla bloquea la que no se usa. Los recordatorios de la agenda se pueden repetir al crearlos (`repetir`: dia/semana/mes y `veces`, hasta 60 y dos años): cada repetición es un recordatorio propio que comparte `serie`; se borra uno o «este y los siguientes» (`?siguientes=1`).

**Contar una comida antes del aviso:** `GET /api/agenda/hoy/` trae `comidas` (las del plan de hoy, con su hora y si ya se contaron) y «Tu día» las lista con «Ya comí», que abre `/comidas/contar`; contar antes de la hora del aviso resuelve el aviso cuando llega.

## Ventanas de sueño y siestas

`agenda/ventanas.py` fija cuándo valen los botones. **«Me levanté»** (un solo botón): de 2 horas antes a 2 horas después de la hora prevista (`levantar.ventana` en `GET /hoy/`: libre, antes, abierta, cerrada); pasado ese rato el día queda «no respondió» y el mismo botón deja responder **una sola vez** con la hora (`POST /registros/levantar/ {hora}`, solo con la ventana cerrada y sin pasarse de ahora): es la única vez que se escribe una hora. **«Ya me acosté»**: desde 2 horas antes de la hora de acostarse hasta 2 horas antes de levantarse al día siguiente (`dormir.ventana`); pasado eso queda «no respondió» (`dormir.anoche_sin_respuesta`) y no se puede decir una hora. **«Voy a dormir» / «Dejé de dormir»** (siesta, `siesta` en `GET /hoy/`; `siesta_inicio`/`siesta_fin`; `POST /registros/siesta/iniciar|terminar/`): solo fuera de las horas de sueño, que van desde que abre el «ya me acosté» hasta que la persona se levanta (o pasa el rato para decirlo); no se empieza una con otra en curso y no cuentan en el promedio de sueño de la noche.

**Siesta sin terminar:** si «Voy a dormir» lleva más de 3 horas sin «Dejé de dormir» (`siesta.sin_respuesta`), el mismo botón deja decir la hora **una sola vez** (`POST /registros/siesta/terminar/ {hora}`, entre que empezó y ahora); a tiempo solo se anota la de ahora.

## Crecimiento personal

App `crecimiento`, por ahora solo dentro de Crecimiento (no comparte datos con el resto de la app). Cada persona crea sus **áreas** («Educación financiera»); dentro elige un **programa del catálogo** (no hay procesos ni proyectos sueltos: los programas son solo los que se registran) y le llegan sus **proyectos** (actividades), cada uno con sus **notas**. Borrar un área o un programa se lleva lo de abajo; los proyectos no se crean ni se borran por la API. Pantalla `/crecimiento` (pestaña «Crecimiento»; `?proyecto=ID` abre un proyecto, así llegan los avisos).

**El estándar:**
- **Programa** (`crecimiento/programas.py`): fuente (libro y autor) y sus proyectos con una `clave` estable (`Proceso.programa`, `Proyecto.clave`). Hoy hay uno, «Sana tus finanzas» (Jaime Jaramillo), con dos actividades: el taller de creencias (capítulo 1) y el diario de gastos (capítulo 2, paso 1). Las demás del libro se agregan cuando se pulan.
- **Tipo de proyecto** (`crecimiento/tipos.py`, forma en `tipos_base.Tipo`): `valida(datos)`, `avance(proyecto)` (0 a 100), `resumen(proyecto)`, `avisos(proyecto, fecha)` / `confirmar` / `resuelto`, `del_servidor` (llaves de `datos` que la app no puede escribir: lo cumplido) y `acciones` (`POST /proyectos/<id>/accion/<nombre>/`). Su pantalla va en `frontend/src/app/crecimiento/pantallas.ts` y recibe `proyecto`; lo común (título, estado, notas) lo pone la página.
- **Avisos**: `crecimiento/avisos.py` los pasa a `agenda.notificaciones` como `tipo='crecimiento'` (`datos`: proyecto, aviso, accion): llegan a la bandeja y al celular, la acción la guarda el tipo y se resuelven solos cuando el tipo dice. Se apagan con «Crecimiento» en «Avisos que quiero recibir» o desde el propio proyecto.

**Taller de creencias** (`crecimiento/creencias.py`, pantalla `taller-creencias`): los cuatro pasos de la página que armó el usuario (cuestionario sí/no por grupos, reflexiona sobre los «sí», transforma con sugerencia, resultado en post-its). Todo en `Proyecto.datos`; las fechas leídas (`dias`) solo las agrega el servidor (botón «Hoy ya las leí» o el aviso de las 08:00, ajustable) y cuentan **21 días seguidos** (si se salta un día, vuelve a empezar). Avance: un cuarto por paso.

**Diario de gastos** (`crecimiento/diario.py`, `views_diario.py`, pantalla `diario-gastos`): el ejercicio tal cual, sin mirar meses atrás. **Mis gastos** (`Rubro`): las 9 categorías del Excel del libro con sus rubros, más «Otros»; cada rubro con su valor, su parte cerebral (emocional = valor − cerebral; así el mixto se parte) y **cada cuánto se paga**: cada mes (tal cual), al año o dos veces al año (se divide entre 12; con el mes del pago, cuánto ahorrar por mes hasta él) o diario/hormiga (× días del mes, 30): todo suma **un solo gasto mensual**. **Registro** (`Gasto`, `DiaSinGasto`): lo gastado de verdad este mes, con la pregunta «¿pasa algo grave si no lo hago?» (sí = cerebral); se anota el mismo día (un día pasado no se llena), no se edita y solo se borra ese día, y «Hoy no gasté». Resumen (plan del mes contra lo anotado, por categoría), aviso a las 20:00 si el día no tiene nada y la guía «¿Cerebral o emocional?», con palabras propias (no se copia el libro).

## Modo pausa y «¿qué pasó?»

`agenda/pausa.py` y `Pausa` (inmutable de hecho: se termina con «ya volví», no se borra). «Voy a estar desconectado» (`POST /api/agenda/pausa/ {duracion: horas|hoy|dias|indefinida, cantidad, motivo}`, `DELETE` = «ya volví», `GET` la activa): mientras dura, `programados` no deja pasar ningún aviso (tampoco al celular) y al empezar se quitan los pendientes (`resolucion='pausa'`); al volver no se amontona lo que tocaba antes. Un día cuenta **en pausa** si la pausa cubre al menos 8 horas de él: `cumplimiento._dia` lo devuelve con `en_pausa` y sin porcentaje, no entra en `dias_periodo` y la racha (`_rachas`, `logros.calcular_racha`) lo salta sin sumarlo ni cortarla; una pausa de unas horas solo calla los avisos. Empieza siempre ahora: lo que ya pasó no se excusa después. Si pasan 24 h sin actividad (registros, comidas, avisos confirmados) y no hay pausa, llega un aviso al día `tipo='regreso'` («Ey, ¿qué pasó?», luego «llevas N días…») con la acción «Pausar hoy»; se quita solo cuando vuelve a haber actividad. En el frontend, `app-modo-pausa` (Tu día) y el aviso de arriba del layout mientras dura.

## Lo que pasó no se llena después

Regla del usuario («sería trampa»): lo de un día se anota ese día. Contar una comida (`nutricion/comidas._validar_fecha`) y anotar un gasto o «hoy no gasté» (`crecimiento/diario._validar_fecha`) solo aceptan hoy; los avisos de días que ya pasaron no se confirman y `resolver_automaticas` los quita solos (salvo `DE_FECHA`: agenda, control y dormir, que vale de madrugada con su ventana); la pausa no se pone hacia atrás. Lo que sí admite fecha pasada son las mediciones (una medida tomada por un profesional es un dato real, no un registro del día).

## Salud: protocolo Fadiman y otros suplementos

Programa `salud_protocolo` (área «Salud») dentro de Crecimiento, con dos proyectos: `fadiman` y `otros_suplementos` (`crecimiento/salud.py`, `views_salud.py`, pantalla `salud` en el frontend para los dos tipos). **Protocolo Fadiman**: ciclo de 3 días (día 1 toma, 2 observación, 3 normal; el siguiente vuelve a ser día 1: una toma cada 3 días) durante 4–8 semanas y descanso de 2–4; los ajustes van en `Proyecto.datos` (`inicio`, `semanas_ciclo`, `semanas_descanso`, `sustancia`, `dosis`, aviso) y el calendario se calcula (`dia_del_protocolo`), no se guarda. La app **no sugiere sustancias ni dosis**: las escribe la persona. Lo anotado (`TomaSalud`: `dosis` u `observacion` con ánimo/energía 1–5) es inmutable, solo se borra el mismo día y solo se anota lo de hoy; la toma solo se anota el día que toca (día 1, fuera del descanso); `fuera_de_protocolo` queda solo para datos viejos. `calendario` (en `GET /salud/<id>/`) trae la vuelta en curso día por día con cada toma `hecha`, `perdida`, `pendiente` o `antes` (de antes de registrarse) y lo dibuja `app-calendario-fadiman`. Avisos (`tipo='crecimiento'`): día 1, día 2 y inicio del descanso; se resuelven al anotar. **Otros suplementos**: cada suplemento es un **plan** en `Proyecto.datos['planes']` (qué, cuánto, días de la semana con lunes = 0, horas, `inicio` y `duracion_dias` o sin fin; `id` de 8 caracteres que se conserva al editar). A cada hora que toca llega un aviso con «Ya lo tomé» (clave `id@HH:MM`) que anota la toma ligada (`TomaSalud.plan`); también hay tomas sueltas. La hora de la toma es la de `anotado` (se anota cuando se hace) y sale en la pantalla. Los suplementos no tienen porcentaje (`Tipo.con_avance=False`: no se muestra ni cuenta en el avance del área). Los suplementos del plan de nutrición siguen en `nutricion`. Dentro de un área, «Agregar» solo ofrece los programas de esa área que no estén ya en proceso. `GET /api/crecimiento/salud/<proyecto>/`, `POST …/tomas/`, `DELETE …/tomas/<id>/`.
