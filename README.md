# 🥊 Camino del Guerrero

Aplicación web para gestionar rutinas de entrenamiento de boxeo, registro de progreso físico, seguimiento de peso y plan nutricional generado por IA. Diseñada mobile-first con soporte multi-usuario.

---

## Stack tecnológico

| Capa | Tecnología |
|---|---|
| Frontend | Angular 21 + PrimeNG + Tailwind CSS |
| Backend | Django 5 + Django REST Framework |
| Autenticación | JWT (djangorestframework-simplejwt) |
| Base de datos | PostgreSQL (Docker) |
| IA | Conectable a cualquier modelo (Ollama, OpenAI, Gemini, etc.) |
| Infraestructura | Docker + CasaOS (Ubuntu home server) |

---

## Integración con IA

La app se comunica con un modelo de IA a través de una interfaz genérica configurable por variables de entorno. El proveedor puede cambiarse sin modificar el código de negocio.

```env
AI_PROVIDER=ollama          # ollama | openai | gemini | cualquier otro
AI_BASE_URL=http://localhost:11434
AI_MODEL=llama3
AI_API_KEY=opcional
```

El backend de Django tiene un servicio `AIService` que abstrae la conexión. Cambiar de modelo es solo cambiar las variables de entorno.

Responsabilidades de la IA:
- Generar rutina semanal según implementos disponibles del usuario
- Generar plan nutricional semanal según objetivo y peso actual
- A futuro: sugerir ajustes según historial de progreso

---

## Estructura del proyecto

```
camino-del-guerrero/
├── backend/
│   ├── core/              # Configuración global (settings, urls, wsgi)
│   ├── usuarios/          # Autenticación, roles y gestión de usuarios
│   ├── rutinas/           # Rutinas, ejercicios e implementos
│   ├── progreso/          # Log de entrenamiento y registro de peso
│   └── nutricion/         # Plan nutricional generado por IA
├── frontend/
│   └── src/
│       └── app/
│           ├── auth/
│           ├── rutinas/
│           ├── progreso/
│           └── nutricion/
├── CLAUDE.md              # Contexto para Claude Code
└── README.md
```

---

## Módulos del MVP

### Auth
- Registro e inicio de sesión con JWT
- Roles definidos en tabla `ROL` (admin / usuario)
- El admin solo gestiona el catálogo de implementos y agrega videos a los ejercicios

### Onboarding (primer ingreso)
- La app solicita el peso inicial del usuario
- El usuario elige su objetivo (bajar peso, ganar músculo, etc.)
- El usuario selecciona los implementos que tiene en casa
- Si no tiene nada, selecciona "Sin implemento" y la IA sugiere ejercicios de peso corporal
- Se configura la frecuencia de seguimiento de peso (15 días o 1 mes)
- Al finalizar el onboarding, la IA genera automáticamente la rutina y el plan nutricional del usuario

### Rutinas
- Cada usuario tiene su propia rutina semanal generada por IA
- La IA crea la rutina y sus ejercicios según los implementos disponibles del usuario
- La rutina se guarda en la BD y el usuario la consulta diariamente
- El admin puede agregar o editar el video de YouTube de cada ejercicio sugerido por la IA
- El usuario puede solicitar que la IA regenere su rutina cuando lo desee

### Progreso
- Log diario de entrenamiento (rounds, duración, notas)
- Registro de peso según frecuencia elegida (15 días o 1 mes)
- Historial personal individual por usuario

### Nutrición (IA)
- Plan alimentario semanal generado por IA, individual por usuario
- Se basa en el objetivo y peso actual del usuario
- Incluye desayuno, almuerzo, cena, snacks y calorías aproximadas por día
- Se guarda en la BD y el usuario lo consulta diariamente
- El usuario puede solicitar que la IA regenere su plan cuando lo desee

---

## Modelo de datos (v3 — normalizado)

### Diagrama de relaciones

```
ROL ──< USUARIO ──< OBJETIVO_USUARIO ──< PLAN_NUTRICIONAL ──< DIA_NUTRICIONAL
                 ──< REGISTRO_PESO
                 ──< USUARIO_IMPLEMENTO >── IMPLEMENTO ──< EJERCICIO_IMPLEMENTO >── EJERCICIO
                 ──< REGISTRO_ENTRENAMIENTO >── RUTINA ──< DIA_RUTINA ──< EJERCICIO_DIA >── EJERCICIO
```

### Tablas

#### Autenticación y usuarios
| Tabla | Descripción |
|---|---|
| `ROL` | Catálogo de roles (admin, usuario). Normalizado para agregar roles sin tocar código |
| `USUARIO` | Datos del usuario. `frecuencia_peso` guarda si eligió 15 o 30 días |
| `OBJETIVO_USUARIO` | Objetivo, peso inicial y peso meta. Historial por usuario |

#### Implementos y ejercicios
| Tabla | Descripción |
|---|---|
| `IMPLEMENTO` | Catálogo definido por el admin. `es_sin_implemento=true` para usuarios sin equipamiento |
| `USUARIO_IMPLEMENTO` | Junction: qué implementos tiene cada usuario |
| `EJERCICIO` | Ejercicio sugerido por la IA. El admin agrega el `url_youtube`. `requiere_implemento=false` = peso corporal |
| `EJERCICIO_IMPLEMENTO` | Junction: un ejercicio puede requerir varios implementos |

#### Rutinas
| Tabla | Descripción |
|---|---|
| `RUTINA` | Rutina semanal generada por IA, una por usuario. Se regenera cuando el usuario lo solicita |
| `DIA_RUTINA` | Días de la semana asignados a la rutina del usuario |
| `EJERCICIO_DIA` | Ejercicios por día con series, repeticiones y duración |

#### Progreso
| Tabla | Descripción |
|---|---|
| `REGISTRO_PESO` | Historial de peso por usuario con fecha y nota opcional |
| `REGISTRO_ENTRENAMIENTO` | Log diario: qué rutina hizo, cuántos rounds, duración y notas |

#### Nutrición
| Tabla | Descripción |
|---|---|
| `PLAN_NUTRICIONAL` | Plan generado por IA vinculado al objetivo del usuario |
| `DIA_NUTRICIONAL` | Detalle diario: comidas y calorías aproximadas |

---

## Flujo de un usuario nuevo

```
1. Registro → se asigna ROL de usuario
2. Onboarding → peso inicial + objetivo → OBJETIVO_USUARIO + REGISTRO_PESO
3. Selección de implementos → USUARIO_IMPLEMENTO
4. IA genera rutina semanal según implementos disponibles
5. IA genera plan nutricional según objetivo y peso
6. Cada 15 días o 1 mes → app solicita nuevo peso → REGISTRO_PESO
```

---

## Permisos por rol

| Acción | Admin | Usuario |
|---|---|---|
| Gestionar catálogo de implementos | ✅ | ❌ |
| Agregar / editar video YouTube de ejercicios | ✅ | ❌ |
| Ver todos los usuarios y su progreso | ✅ | ❌ |
| Gestionar usuarios | ✅ | ❌ |
| Generar / regenerar su rutina (IA) | ❌ | ✅ |
| Ver su rutina diaria | ✅ | ✅ |
| Registrar log de entrenamiento | ✅ | ✅ |
| Ver su propio progreso | ✅ | ✅ |
| Generar / regenerar su plan nutricional (IA) | ❌ | ✅ |

---

## Variables de entorno (backend)

Crear archivo `.env` en `/backend`:

```env
SECRET_KEY=tu_secret_key
DEBUG=True
DB_NAME=camino_db
DB_USER=camino_user
DB_PASSWORD=tu_password
DB_HOST=localhost
DB_PORT=5432

AI_PROVIDER=ollama
AI_BASE_URL=http://localhost:11434
AI_MODEL=llama3
AI_API_KEY=
```

---

## Instalación local

### Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

### Frontend
```bash
cd frontend
npm install
ng serve
```

### PostgreSQL (Docker — servidor CasaOS)
```bash
docker run -d \
  --name postgres \
  -e POSTGRES_PASSWORD=tu_password \
  -p 5432:5432 \
  -v postgres_data:/var/lib/postgresql/data \
  postgres:18

docker exec -it postgres psql -U postgres -c "CREATE DATABASE camino_db;"
docker exec -it postgres psql -U postgres -c "CREATE USER camino_user WITH PASSWORD 'tu_password';"
docker exec -it postgres psql -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE camino_db TO camino_user;"
```

---

## Roadmap

### Backend
- [x] Diseño de arquitectura y stack
- [x] Modelo de datos normalizado (v3)
- [x] Módulo Auth — usuarios, roles y JWT
- [x] Módulo Onboarding — peso, objetivo e implementos
- [x] Módulo Rutinas — generación por IA, una por usuario
- [x] Módulo Progreso — log de entrenamiento y registro de peso
- [x] Módulo Nutrición — plan semanal por IA, uno por usuario
- [x] Integración IA flexible — AIService con provider configurable (Ollama, OpenAI, Gemini)

### Frontend
- [ ] Auth — login y registro
- [ ] Onboarding — flujo de primer ingreso
- [ ] Rutinas — vista semanal y detalle por día
- [ ] Progreso — historial de peso y log de entrenamientos
- [ ] Nutrición — plan alimentario semanal
- [ ] PWA — funcionalidad offline para el timer

### Infraestructura
- [ ] Docker Compose para deploy en CasaOS