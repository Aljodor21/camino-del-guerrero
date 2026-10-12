# Despliegue en uburoom

La app se despliega sola con el CI/CD de [Warden](https://github.com/Aljodor21/warden): cada merge a `main` construye y levanta los contenedores en el servidor y publica el subdominio en el túnel de Cloudflare.

```
PR → ci.yml (GitHub) → merge a main → deploy.yml (runner de Warden en uburoom) → docker compose up → warden publish
```

- **Dirección:** `https://camino.servelejo.site` (túnel de Cloudflare → `localhost:8085`).
- **Puerto:** 8085. El 80 lo usa el panel de Warden y el 8080 ntfy.
- **Proyecto de Compose:** `camino-del-guerrero` (fijado en `docker-compose.yml`; los volúmenes y contenedores llevan ese nombre).

## Qué hace cada workflow

**`.github/workflows/ci.yml`** (en cada pull request, en los servidores de GitHub, sin tocar uburoom):
- Backend: `manage.py check`, que no falten migraciones y las pruebas, contra un PostgreSQL de prueba.
- Frontend: build de producción y build móvil.
- Compose: que `docker-compose.yml` sea válido.

**`.github/workflows/deploy.yml`** (al llegar algo a `main`, en el runner de uburoom):
1. Revisa que exista el `.env.docker` del servidor.
2. Hace `pg_dump` de la base a `/home/alejo/camino/respaldos/` (guarda los últimos 10) antes de tocar nada.
3. Copia el `.env.docker` y ejecuta `docker compose up -d --build`. El backend corre `migrate` al arrancar.
4. Espera a que la web y la API respondan (hasta ~2 minutos). Si no, falla y muestra los logs.
5. `sudo warden publish` para que el túnel publique el subdominio.

Un despliegue a la vez: si llega otro merge, espera al anterior.

## Puesta en marcha (una sola vez)

1. **Dar de alta la app en Warden** (panel → Catálogo → Nueva app, o copiando a `~/warden/site/catalog/`):
   - `deploy/warden/camino.component`: la app, con su subdominio y puerto.
   - `deploy/warden/camino-datos.component`: respaldo de la base `camino_db` y las fotos. Warden deja fuera del backup a las apps de CI/CD (las que tienen URL git), por eso los datos van en un componente aparte.
2. **Registrar el runner** con el token de GitHub (repo → Settings → Actions → Runners → New self-hosted runner), desde el panel (Catálogo → Registrar runner) o:
   ```bash
   sudo warden runner https://github.com/Aljodor21/camino-del-guerrero <TOKEN>
   ```
3. **Crear el `.env.docker` de producción** en el servidor (nunca va a git), partiendo de `.env.docker.example`:
   ```bash
   mkdir -p ~/camino && cp .env.docker.example ~/camino/.env.docker && chmod 600 ~/camino/.env.docker
   ```
   Poner valores reales en `SECRET_KEY`, `DB_PASSWORD` / `POSTGRES_PASSWORD` (el mismo), `ADMIN_PASSWORD`, las llaves `VAPID_*` (se generan con `python manage.py llaves_push`), el correo, `AI_*` y `OPENAI_API_KEY`. Dejar `DEBUG=False`.
4. **Permitir `warden publish` al runner** (una vez, con sudo):
   ```bash
   echo 'alejo ALL=(root) NOPASSWD: /usr/local/bin/warden publish' | sudo tee /etc/sudoers.d/warden-runner
   sudo visudo -cf /etc/sudoers.d/warden-runner
   ```
5. **Proteger `main`** (repo → Settings → Branches): exigir pull request y que pasen los checks `Backend (pruebas)`, `Frontend (compila)` y `Docker Compose (válido)`.

Después, cada PR aprobado y mezclado en `main` se despliega solo. También se puede lanzar a mano desde Actions → deploy → Run workflow.

## Primer despliegue y datos

Los datos viven en volúmenes de Docker (`postgres_data`, `media_files`) y sobreviven a cada despliegue. Antes de empezar de verdad con tu proceso, vacía los datos de prueba:

```bash
cd <carpeta del runner>/_work/camino-del-guerrero/camino-del-guerrero
docker compose --env-file .env.docker down -v   # borra la base y las fotos
```

y vuelve a lanzar el workflow. No lo hagas después de tener datos reales.

## Volver atrás

- **Código:** revertir el merge en GitHub; el siguiente despliegue deja la versión anterior.
- **Base de datos:** el respaldo previo está en `/home/alejo/camino/respaldos/`:
  ```bash
  gunzip -c respaldos/antes-del-deploy-<fecha>.sql.gz | docker exec -i camino-del-guerrero-db-1 sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
  ```
  Antes de actualizar con datos reales conviene revisar que la migración nueva no reemplace estructuras (pasó con suplementos y planes).

## La app instalada (APK)

La APK llama a `https://camino.servelejo.site/api` (`frontend/src/environments/environment.movil.ts`). El backend ya acepta los orígenes de la app (`https://localhost`, `capacitor://localhost`). Compilar: `cd frontend && npm run build:movil` y luego `npm run apk` (necesita el Android SDK).
