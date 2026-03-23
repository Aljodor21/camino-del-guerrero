# Camino del Guerrero

Aplicación web mobile-first para boxeadores y atletas de combate. Genera rutinas de entrenamiento y planes nutricionales personalizados mediante IA, adaptados al nivel, objetivos y cultura culinaria del usuario. Incluye seguimiento de progreso, timers de sesión y lista de mercado semanal.

---

## Stack tecnológico

| Capa | Tecnología |
|---|---|
| Frontend | Angular 21 · PrimeNG · Tailwind CSS v4 |
| Backend | Django 5 · Django REST Framework |
| Autenticación | JWT (djangorestframework-simplejwt) |
| Base de datos | PostgreSQL |
| IA | Groq API — `llama-3.3-70b-versatile` (configurable) |
| Infraestructura | Docker + CasaOS (Ubuntu home server) |

---

## Integración con IA

El backend expone un `AIService` que abstrae el proveedor. Cambiar de modelo es solo cambiar variables de entorno.

```env
AI_PROVIDER=openai           # openai | ollama
AI_BASE_URL=https://api.groq.com/openai
AI_MODEL=llama-3.3-70b-versatile
AI_API_KEY=tu_api_key
```

### Funciones de IA implementadas

| Función | Descripción |
|---|---|
| `generar_rutina()` | Rutina semanal de boxeo: ejercicios técnicos con descripciones detalladas de ejecución, nivel, series y duración |
| `generar_plan_nutricional()` | Plan alimentario de 7 días basado en la región y cultura culinaria del usuario |
| `generar_lista_mercado()` | Extrae y consolida ingredientes del plan nutricional en una lista organizada por categorías |

Los prompts siguen principios de prompt engineering: rol experto bien definido, instrucciones numeradas, ejemplos concretos, restricciones explícitas y paso de verificación antes de responder.

---

## Estructura del proyecto

```
camino-del-guerrero/
├── backend/
│   ├── core/              # Settings, urls base, AIService
│   ├── users/             # Autenticación, roles, perfil, objetivo
│   ├── routines/          # Rutinas, ejercicios, implementos
│   ├── progress/          # Log de entrenamiento y registro de peso
│   └── nutricion/         # Plan nutricional y lista de mercado
├── frontend/
│   └── src/app/
│       ├── home/          # Landing page pública
│       ├── auth/          # Login y registro
│       ├── onboarding/    # Flujo de configuración inicial
│       ├── rutinas/       # Vista semanal + videos
│       ├── progreso/      # Sesión activa + historial de peso
│       ├── nutricion/     # Plan alimentario + lista de mercado
│       ├── admin/         # Gestión de implementos y ejercicios
│       ├── core/          # Guards, servicios, modelos
│       └── shared/        # Layout, componentes reutilizables
└── README.md
```

---

## Módulos del sistema

### Landing page
- Página pública en `/` con presentación de la app
- Nav adaptativa: muestra login/registro o "Ir al dashboard" según estado de sesión
- Soporte completo dark/light mode con logos reales de la marca
- Toggle de tema accesible desde la nav

### Autenticación
- Registro con email, nombre, sexo y fecha de nacimiento
- Login con JWT (access + refresh token)
- `SafeTokenRefreshView`: devuelve 401 en vez de 500 si el usuario no existe
- Logout redirige al home
- Guards:
  - `authGuard`: requiere sesión activa
  - `userGuard`: requiere sesión y bloquea admin (redirige a `/admin/implementos`)
  - `adminGuard`: requiere rol admin

### Onboarding (primer ingreso)
Flujo de 3 pasos que configura el perfil completo antes de generar los planes:

**Paso 1 — Perfil:**
- Peso inicial y peso meta
- Estatura
- Objetivo (bajar peso / ganar músculo / mantener / resistencia)
- Nivel de actividad (principiante / intermedio / avanzado)
- Días de entrenamiento por semana (3 / 4 / 5)
- Duración de sesión (30 / 45 / 60 min)
- Frecuencia de seguimiento de peso (15 días / 1 mes)
- Nacionalidad (autocomplete con 195 países)
- Región o zona (texto libre: paisa, costeño, bogotano, etc.)
- Restricciones alimentarias (opcional)

**Paso 2 — Implementos:** selección de equipamiento disponible

**Paso 3 — Generación:** la IA crea rutina + plan nutricional en paralelo

### Rutinas
- Vista semanal con selector de días (punto rojo en el día actual)
- Detalle de cada ejercicio: series, repeticiones, duración, descripción técnica
- Videos de YouTube embebidos dentro de la app (iframe en dialog, sin salir)
- Botón regenerar con IA en un clic

### Progreso
**Seguimiento de peso:**
- Registro de peso con nota opcional
- Historial con fecha y cálculo de cambio total

**Sesión de entrenamiento:**
- Elige el día de la rutina y arranca la sesión
- Timer por serie: cuenta regresiva para ejercicios con duración fija, cronómetro para el resto
- Auto-finaliza la serie al llegar a cero
- Timer de descanso de 60 segundos entre series con opción "Omitir"
- Videos de ejercicios visibles durante la sesión (in-app)
- Al finalizar guarda el log con todos los ejercicios y duración total

### Nutrición
**Plan alimentario:**
- Plan semanal de 7 días generado por IA
- Desayuno, almuerzo, cena, snacks y calorías aproximadas por día
- Adaptado a la región y cultura culinaria del usuario
- Regenerable en un clic

**Lista de mercado:**
- Generada por IA a partir del plan nutricional activo
- Ingredientes organizados por categoría (proteínas, verduras, frutas, lácteos, granos, condimentos)
- Cantidades consolidadas para 7 días / 1 persona
- Ítems chequeables con tachado visual y barra de progreso

### Panel de administración
- **Implementos:** CRUD del catálogo de implementos disponibles
- **Ejercicios:** edición inline de URL de YouTube por ejercicio
  - Búsqueda por nombre
  - Filtro "solo sin video"
  - Estadísticas: cuántos tienen video / sin video
  - Ordenamiento: sin video primero

---

## Modelo de datos

```
ROL ──< USUARIO >──< OBJETIVO_USUARIO
                 ──< REGISTRO_PESO
                 ──< USUARIO_IMPLEMENTO >── IMPLEMENTO
                 ──< REGISTRO_ENTRENAMIENTO
                 ──< RUTINA ──< DIA_RUTINA ──< EJERCICIO_DIA >── EJERCICIO
                 ──< PLAN_NUTRICIONAL ──< DIA_NUTRICIONAL
                 ──< LISTA_MERCADO ──< ITEM_MERCADO
```

### Campos clave del modelo `Usuario`
| Campo | Descripción |
|---|---|
| `nacionalidad` | País del usuario para personalizar el plan nutricional |
| `region` | Región/zona cultural (paisa, costeño, etc.) para recetas más específicas |
| `preferencias_alimentarias` | Restricciones dietarias (vegetariano, sin gluten, etc.) |
| `estatura` | En cm, usado en el perfil enviado a la IA |
| `frecuencia_peso` | Cada 15 o 30 días |

### Campos clave del modelo `ObjetivoUsuario`
| Campo | Descripción |
|---|---|
| `nivel_actividad` | principiante / intermedio / avanzado |
| `dias_entrenamiento` | 3 / 4 / 5 días por semana |
| `duracion_sesion` | 30 / 45 / 60 minutos |
| `fecha_inicio` | Usa `timezone.localdate` para respetar la zona horaria configurada |

---

## Permisos por rol

| Acción | Admin | Usuario |
|---|---|---|
| Gestionar catálogo de implementos | ✅ | ❌ |
| Agregar / editar video YouTube de ejercicios | ✅ | ❌ |
| Acceder a onboarding y rutas de usuario | ❌ | ✅ |
| Generar / regenerar rutina con IA | ❌ | ✅ |
| Generar / regenerar plan nutricional con IA | ❌ | ✅ |
| Registrar sesiones y peso | ❌ | ✅ |
| Ver su propio progreso | ❌ | ✅ |
| Ver lista de mercado | ❌ | ✅ |

---

## Instalación local

### Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

### Frontend
```bash
cd frontend
npm install
ng serve
```

### Variables de entorno (`backend/.env`)
```env
SECRET_KEY=tu_secret_key
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

DB_NAME=camino_db
DB_USER=camino_user
DB_PASSWORD=tu_password
DB_HOST=localhost
DB_PORT=5432

AI_PROVIDER=openai
AI_BASE_URL=https://api.groq.com/openai
AI_MODEL=llama-3.3-70b-versatile
AI_API_KEY=tu_groq_api_key
```

### Zona horaria (`backend/core/settings.py`)
```python
TIME_ZONE = 'America/Bogota'
```
Los modelos con fecha usan `default=timezone.localdate` (no `auto_now_add`) para respetar esta zona.

---

## Roadmap

### Completado
- [x] Landing page con dark/light mode y nav adaptativa por sesión
- [x] Auth completa: registro, login, JWT, guards por rol
- [x] Onboarding extendido: perfil completo + implementos + generación de planes
- [x] Rutinas: vista semanal, videos in-app, regeneración con IA
- [x] Progreso: timer countdown/countup, descanso automático, log de sesión
- [x] Nutrición: plan semanal + lista de mercado con checklist
- [x] Admin: implementos CRUD + ejercicios con edición inline y filtros
- [x] IA: prompts con prompt engineering para rutinas, nutrición y lista de mercado
- [x] Deduplicación de ejercicios (`get_or_create` por nombre)
- [x] Corrección de zona horaria en fechas
- [x] Protección de rutas por rol (`userGuard` + `adminGuard`)

### Próximos pasos
- [ ] Perfil editable: el usuario puede actualizar su región, peso, objetivo sin pasar por onboarding
- [ ] Gráfica de evolución de peso (histórico visual)
- [ ] Estadísticas de entrenamiento: sesiones por semana, tiempo total, ejercicios más frecuentes
- [ ] Notificaciones / recordatorios de registro de peso
- [ ] PWA: funcionalidad offline para el timer de sesión
- [ ] Docker Compose para deploy en CasaOS
- [ ] Compartir progreso (imagen o link público de resumen)
