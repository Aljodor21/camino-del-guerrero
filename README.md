# Camino del Guerrero

Aplicación web mobile-first para llevar un proceso de cuerpo y comida de principio a fin: subir de peso, bajarlo o mantenerlo, con o sin entrenamiento. Sirve igual a quien entrena boxeo, yoga o en casa, y a quien solo quiere comer mejor.

La app **no inventa el plan de comida**: la minuta es la de la nutricionista y cada menú, cambio y lista de mercado sale de esa minuta y de su lista de intercambios. La IA propone, el servidor valida.

---

## Qué hace

| Módulo | Descripción |
|---|---|
| **Cuenta** | Registro, ingreso y recuperación de clave por correo; al cambiar la clave se cierran las sesiones abiertas. Los datos de inicio (nombre, sexo, nacimiento, estatura, nacionalidad, región) no se editan; solo el administrador los corrige, desde su pantalla de usuarios. |
| **Procesos** | Un solo proceso a la vez, con objetivo, fase (volumen, definición, mantenimiento), fechas y qué incluye (alimentación y/o entrenamiento). Si empieza con uno solo, el otro módulo se suma después al mismo proceso desde el perfil. Para empezar otro proceso se borra el actual. Los datos de inicio y la fecha meta no se editan. |
| **Control** | Al llegar la fecha de control (`fecha_fin_plan`) la app pregunta si se sigue con el proceso o hay cambios. Seguir pide un nuevo periodo (el mismo tiempo, otro o sin definir); un plan nuevo de comida pregunta lo mismo. La fecha anterior queda en el historial. Un módulo (alimentación o entrenamiento) se puede quitar mientras quede el otro, y borra lo que se armó con él. |
| **Proyección** | Estima cuánto podría cambiar el peso hasta el control, con todo lo que ya se sabe: el gasto (Mifflin-St Jeor con peso, estatura, edad y sexo, recalculado cada semana porque el cuerpo se adapta), el entrenamiento por enfoque, días y minutos (si no hay, dice que es solo alimentación), las calorías de la minuta y lo que aporta la proteína cuando su tabla nutricional está confirmada. El cambio se limita a lo que el cuerpo puede dar (1 % del peso por semana) y se separa en músculo, con un techo según el nivel, y grasa y agua. Es orientativa y lista sus supuestos. Con una key de OpenAI (`OPENAI_API_KEY`) y el permiso expreso de la persona, genera una imagen del cambio estimado a partir de su foto de frente, con esa composición; máximo 3 imágenes al día y quedan privadas. |
| **Medidas** | Peso, talla y medidas del cuerpo con fotos (frente, perfil, espalda). Las hace la persona a mano; son inmutables. Las fotos se reducen y se les quitan los metadatos del celular. |
| **Minuta** | Se carga desde el PDF de la nutricionista (se lee y se confirma), se escribe a mano o la calcula la IA. Una vez guardada no se edita; una nueva pasa al historial. |
| **Menú semanal** | Desayuno, onces, almuerzo, algo, cena y merienda de cada día, con las porciones exactas de la minuta. Usa solo los alimentos que la minuta nombra en su menú de ejemplo; la IA únicamente completa lo que la minuta no nombra (por ejemplo "1 porción de fruta") con alimentos de la lista de intercambios y lo que ya se sabe de la persona. Antes del día de inicio del proceso no hay menú. |
| **Cambios** | Cambiar un alimento por otro del mismo grupo, o pedir otra comida cuando no se puede con la actual. Siempre validado contra la minuta. |
| **Comer por fuera** | Una comida (por ejemplo el almuerzo) se marca como "fuera" entre semana o siempre: sigue en el menú pero no entra a la lista de mercado. |
| **Lista de alimentos** | Se ve la lista de intercambios que usa el plan, por grupos y con buscador, y se descarga como tabla (CSV) con el formato recomendado para proponer otra. Hoy la carga el administrador. |
| **Lista de mercado** | Solo lo que se cocina en casa, con cantidades exactas de las porciones y sin IA. Se arma para una semana, 15 días o un mes: lo fresco se compra cada semana (el menú cambia) y lo que dura (arroz, avena, aceite, semillas, leguminosas) sale para todo el periodo. Incluye la leche de la proteína, consejos de Ara y D1 y la promoción de Colanta del 15 y el 30. |
| **Suplementos** | Proteína (cualquier tipo), creatina y otros. Se guarda lo que dice la etiqueta (peso del envase, gramos y scoops de la porción del día) y en qué comidas se toma, repartida en scoops, y qué reemplaza de la minuta en cada una. Calcula cuánto dura el envase y guarda su foto (la del pote) y su información nutricional (un enlace y/o la foto o el PDF de la etiqueta). Los archivos son privados y se ven dentro de la app, en una ventana. Se mezcla con agua, leche o ambas (cuántos ml de cada uno, también por toma, con la tabla de la leche si se tiene); cada toma puede tener su hora y cómo se toma, y se pueden agregar otras tomas a la hora que la persona elija. La IA puede leer la tabla nutricional de la etiqueta; la persona la revisa y la confirma antes de que cuente. |
| **Avisos** | Agua, tomas de proteína, hora de dormir, entreno, recordatorios y contar la comida. Llegan al celular y a la app, y solo salen de la bandeja cuando se confirma la acción. |
| **Cumplimiento** | Al llegar el aviso de una comida se cuenta cuánto se comió de cada grupo (con nota y foto opcionales). La app lo compara con la minuta y muestra una torta con el porcentaje y lo que hizo falta. |
| **Agenda** | Recordatorios propios y los que la app sugiere según los suplementos. |
| **Rutinas** | Rutinas por implementos disponibles, con videos y sesiones con temporizadores. |

### Reglas que se cumplen en el servidor

- Los datos de inicio y la minuta guardada **no se editan** (`DatoInmutableError` → 409).
- Los alimentos de un menú o de un cambio **solo salen de la lista de intercambios de la nutricionista**; si la IA propone algo fuera de ella o con porciones distintas, se descarta y se arma el menú con los intercambios.
- Las grasas son solo aceites vegetales y aguacate, como dice la minuta.
- Las fotos de medidas y de comidas son privadas: solo las entrega la API a su dueño.
- Lo que la persona cuenta de una comida, una toma o un vaso de agua queda como registro inmutable.

---

## Stack

| Capa | Tecnología |
|---|---|
| Frontend | Angular 21 (zoneless, signals, `OnPush`) · PrimeNG · Tailwind CSS v4 · PWA con service worker |
| Backend | Django 6 · Django REST Framework · capa de servicios |
| Autenticación | JWT (`djangorestframework-simplejwt`) |
| Base de datos | PostgreSQL |
| IA | `AIService`: Claude con el SDK de Anthropic, Ollama o cualquier API con formato OpenAI |
| Notificaciones | Web Push con VAPID (`pywebpush`) |
| PDF y fotos | `pypdf`, Pillow |
| Infraestructura | Docker Compose en un servidor casero (CasaOS) |

La IA se cambia solo con variables de entorno (`AI_PROVIDER`, `AI_MODEL`, `AI_API_KEY`, `AI_BASE_URL`).

---

## Estructura

```
camino-del-guerrero/
├── backend/
│   ├── core/         # Settings, urls, AIService, errores de dominio
│   ├── users/        # Usuarios, perfil, procesos
│   ├── progress/     # Medidas con fotos y sesiones de entrenamiento
│   ├── routines/     # Rutinas, ejercicios, implementos
│   ├── nutricion/    # Minuta, intercambios, menú, mercado, suplementos, comidas
│   ├── agenda/       # Recordatorios, avisos, hábitos y notificaciones push
│   └── timer/        # Temporizadores de sesión
├── frontend/src/app/
│   ├── home/         # Landing pública
│   ├── auth/         # Ingreso y registro
│   ├── onboarding/   # Primer ingreso: perfil, medidas, minuta, suplementos y hábitos
│   ├── nutricion/    # Menú, mercado y plan
│   ├── comidas/      # Contar lo que se comió y ver el cumplimiento
│   ├── avisos/       # Bandeja de avisos y ajustes
│   ├── progreso/     # Medidas, agenda, suplementos y sesiones
│   ├── rutinas/      # Rutina semanal
│   ├── perfil/       # Datos y proceso
│   ├── admin/        # Catálogo de implementos y ejercicios
│   ├── core/         # Guards, servicios, modelos, constantes
│   └── shared/       # Layout y componentes reutilizables
├── docker-compose.yml
├── Makefile
└── CLAUDE.md         # Guía para trabajar el código con Claude Code
```

---

## Instalación local

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Variables en `backend/.env` (ver `backend/.env.example`): `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, `DB_*` y las de IA (`AI_PROVIDER`, `AI_MODEL`, `AI_API_KEY`).

### Frontend

```bash
cd frontend
npm install
ng serve
```

### Pruebas

```bash
cd backend
python manage.py test
```

Necesitan una base PostgreSQL (la misma configuración de `DB_*`).

---

## Recuperar la clave

Desde el login, "¿Olvidaste tu clave?" manda al correo el usuario y un enlace con el logo de la app. El enlace dura 30 minutos, sirve una sola vez, solo se abre en el navegador donde se pidió y pedir otro anula el anterior (se guarda su hash, nunca el enlace). Configura en el entorno `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`, `DEFAULT_FROM_EMAIL` y `FRONTEND_URL` (la dirección desde la que se abre la app). Sin `EMAIL_HOST` el correo sale en el log del backend, útil para probar.

## Notificaciones al celular

1. Generar las llaves: `python manage.py llaves_push` y poner `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY` y `VAPID_EMAIL` en el entorno.
2. Dejar corriendo `python manage.py enviar_avisos --cada 60` (en Docker es el servicio `avisos`).
3. En la app, Avisos → "Activar notificaciones". En iPhone hay que agregar la app a la pantalla de inicio desde Compartir.

Sin llaves la app funciona igual: los avisos llegan a la bandeja dentro de la app.

---

## Docker

Copiar `.env.docker.example` a `.env.docker` y rellenarlo (ese archivo no se sube a git). Luego:

```bash
make build     # construir y levantar
make up        # levantar sin reconstruir
make logs      # ver logs
make down      # apagar
```

Antes de actualizar una instalación con datos reales, hacer copia de la base de datos: algunas migraciones reemplazan estructuras viejas de suplementos y planes.

---

## Pendientes

- Probar las notificaciones en un celular real con llaves VAPID de producción.
- Lista de intercambios propia por nutricionista (hoy es la de Comfama).
- Más de una porción de suplemento al día.
- Reducir el tamaño del bundle inicial (hoy supera el presupuesto de 500 kB).
