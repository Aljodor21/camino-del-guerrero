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

Los avisos (agua, tomas de proteína, dormir, entreno, recordatorios) los arma `agenda/notificaciones.py`: se crean a su hora, quedan pendientes en la app **hasta que el usuario confirma** y al confirmar se guarda el dato en `RegistroHabito` (inmutable). El envío al celular (web push) lo hace `python manage.py enviar_avisos --cada 60` (servicio `avisos` en `docker-compose.yml`) y necesita `VAPID_*` en `.env.docker` (se generan con `python manage.py llaves_push`). El service worker es `frontend/public/sw.js`. Eso es solo para el navegador: en la app instalada (Capacitor) el web push no existe: ahí los avisos salen por Firebase (FCM, `agenda/fcm.py`: API HTTP v1 con la cuenta de servicio en `FIREBASE_CREDENCIALES_B64`; cada celular se registra en `TokenCelular` con `POST /api/agenda/push/celular/`) y, si Firebase no está disponible, el celular programa sus propios avisos con `@capacitor/local-notifications` a partir de `GET /api/agenda/avisos/proximos/` (`notificaciones.proximos`). `NotificacionesCelularService` (frontend) decide cuál usar; con Firebase activo no se programa nada local para no repetir. Los avisos de comida (`tipo='comida'`) no se confirman a ciegas: se resuelven al contar lo que se comió (`nutricion/comidas.py`, `RegistroComida`), que se compara con la minuta para el porcentaje de cumplimiento; la foto es opcional, privada y de apoyo (el porcentaje sale de lo que el usuario marca).

## Auditoría

La app `auditoria` deja una huella (`Evento`, inmutable) por cada consulta a `/api/` (middleware `AuditoriaMiddleware`) y por cada pantalla que abre la persona (`POST /api/auditoria/pantalla/`): quién, ruta (con su forma, para agrupar), resultado, duración, IP y dispositivo (se interpreta del User-Agent y de las cabeceras `X-Cliente` y `X-App-Version` que manda la app). Nunca guarda cuerpos de peticiones, fotos ni claves; la consulta tapa valores sensibles. Solo el administrador la ve (`/api/auditoria/eventos|resumen/`, pantalla `/admin/auditoria`). `limpiar_auditoria` borra lo de más de 90 días y lo corre el servicio `avisos` una vez al día.

## Domain language

The domain is written in **Spanish**: model names, fields, API paths, AI prompts, and commit messages. Keep new domain code, fields, and prompts in Spanish to match.

## Docker / deploy

Root `Makefile` wraps Docker Compose with `--env-file .env.docker`: `make build` (build + up), `make up`, `make down`, `make restart`, `make logs`, `make ps`. Copy `.env.docker.example` → `.env.docker` first. Deploy target is a CasaOS home server.

## Commits

Commit messages are in Spanish and carry only the author's own name — do **not** add a `Co-Authored-By: Claude` trailer.

## Relevant skills (installed, auto-activate)

`django-expert` (models, DRF, ORM), `db-schema-conventions` + `postgresql-database-engineering` (schema/migrations), `ui-design-quality` (Angular + PrimeNG + Tailwind screens), `post-sprint-review` (after long AI-coding sessions), `pre-deploy-security-checklist` (before deploying).
