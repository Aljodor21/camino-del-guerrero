# Despliegue en uburoom

La app se despliega sola con el CI/CD de [Warden](https://github.com/Aljodor21/warden): cada merge a `main` construye y levanta los contenedores en el servidor. El subdominio ya lo publica Warden al guardar la app en su catálogo (o con su botón **Publicar**).

```
PR → ci.yml (GitHub) → merge a main → deploy.yml (runner de Warden en uburoom) → docker compose up
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
1. Revisa que exista el `.env` de la app en el servidor (el de Variables (.env) del panel de Warden).
2. Hace `pg_dump` de la base a `/home/alejo/camino/respaldos/` (guarda los últimos 10) antes de tocar nada.
3. Copia el `.env.docker` y ejecuta `docker compose up -d --build`. El backend corre `migrate` al arrancar.
4. Espera a que la web y la API respondan (hasta ~2 minutos). Si no, falla y muestra los logs.

Un despliegue a la vez: si llega otro merge, espera al anterior.

## Puesta en marcha (una sola vez)

1. **Dar de alta la app en Warden** (panel → Catálogo → Nueva app, o copiando a `~/warden/site/catalog/`):
   - `deploy/warden/camino.component`: la app, con su subdominio y puerto.
   - `deploy/warden/camino-datos.component`: respaldo de la base `camino_db` y las fotos. Warden deja fuera del backup a las apps de CI/CD (las que tienen URL git), por eso los datos van en un componente aparte.
2. **Registrar el runner** con el token de GitHub (repo → Settings → Actions → Runners → New self-hosted runner), desde el panel (Catálogo → Camino del Guerrero → **Runner y pasos**) o:
   ```bash
   sudo warden runner https://github.com/Aljodor21/camino-del-guerrero <TOKEN>
   ```
3. **El `.env.docker` de producción.** Si no existe, el primer despliegue lo crea solo a partir de `.env.docker.example` y se detiene, para que lo completes. Se edita en el panel de Warden: Catálogo → Camino del Guerrero → **Variables (.env)** (si todavía no está guardado, muestra el ejemplo del repo para que cambies los valores por los reales y guardes; nunca va a git; queda en `~/warden/site/env/camino-del-guerrero.env`, solo legible por tu usuario). Hace falta el modo admin. Valores reales en `SECRET_KEY`, `DB_PASSWORD` / `POSTGRES_PASSWORD` (el mismo), `ADMIN_PASSWORD`, las llaves `VAPID_*` (se generan con `python manage.py llaves_push`), el correo, `AI_*` y `OPENAI_API_KEY`. Dejar `DEBUG=False`.
4. **Proteger `main`** (repo → Settings → Branches): exigir pull request y que pasen los checks `Backend (pruebas)`, `Frontend (compila)` y `Docker Compose (válido)`.

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

La app de Android llama a `https://camino.servelejo.site/api` (`frontend/src/environments/environment.movil.ts`) y el backend ya acepta sus orígenes (`https://localhost`, `capacitor://localhost`).

**Se publica sola.** `.github/workflows/apk.yml` corre en GitHub (no en uburoom) con cada merge a `main` que toque `frontend/`: compila el APK, lo **firma** y lo publica como release `v1.0.<número de corrida>` con el archivo `camino-del-guerrero.apk` (se conservan los últimos 10). La pantalla **Descargar la app** (`/descargar-app`, también un aviso arriba y un acceso en Perfil) lee el último release de GitHub y descarga siempre `releases/latest/download/camino-del-guerrero.apk`, así que no hay que tocar nada al sacar versiones. Dentro de la app instalada esa pantalla no se ofrece.

**La descarga sale de nuestro dominio.** El botón apunta a `/api/app/descargar/`, no a GitHub (un enlace a otro dominio hace que el celular salte de página). El backend guarda una copia de la última versión en el volumen `apk_files` (la baja de GitHub la primera vez que alguien pide la versión o descarga, y borra las anteriores) y nginx se la entrega con `X-Accel-Redirect`: sale en el acto, con avance y reanudación, sin ocupar a Django. Si GitHub no responde, el botón manda al enlace de siempre (`releases/latest/download/camino-del-guerrero.apk`). La versión, el peso y la fecha los lee el servidor (`/api/app/version/`) porque Cloudflare le pone al sitio un `connect-src 'self'` que impide al navegador consultar a GitHub. Variables opcionales: `APK_REPO` y `APK_DIR`.

**La app sabe si está al día.** Al abrir la pantalla de descarga dentro de la app instalada, se compara su `versionName` (la que Android le puso al instalarla, `1.0.<corrida>`) con la última publicada: si está atrás, sale la alerta y el botón para actualizar. Android no actualiza solo una app instalada fuera de la Play Store; esto es lo que lo reemplaza. Usa el plugin `@capacitor/app` (viene de `npm ci`).

**La firma.** Android solo instala una versión encima de otra si trae la misma firma y un `versionCode` mayor (el workflow usa el número de corrida). La llave vive en cuatro secretos del repo: `KEYSTORE_BASE64`, `KEYSTORE_PASSWORD`, `KEY_ALIAS` y `KEY_PASSWORD`. La copia es `~/Android/camino-release.jks` (y sus claves en `camino-release.properties`) en tu equipo: **guárdala en un lugar seguro**, porque si se pierde, nadie podrá actualizar la app sin desinstalarla antes. Nunca va a git.

**Compilar a mano** (prueba local): `cd frontend && npm run build:movil && cd android && ./gradlew assembleDebug` (necesita el Android SDK; el APK de depuración se firma con otra llave y no se actualiza con el del release: desinstálalo antes de instalar el oficial).
