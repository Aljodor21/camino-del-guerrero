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
