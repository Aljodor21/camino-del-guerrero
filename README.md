# 🥊 Camino del Guerrero

Aplicación web para gestionar rutinas de entrenamiento de boxeo, registro de progreso físico y seguimiento de peso. Diseñada mobile-first con soporte multi-usuario.

---

## Stack tecnológico

| Capa | Tecnología |
|---|---|
| Frontend | Angular 21 + PrimeNG + Tailwind CSS |
| Backend | Django 5 + Django REST Framework |
| Autenticación | JWT (djangorestframework-simplejwt) |
| Base de datos | PostgreSQL |
| Infraestructura | Docker + CasaOS (Ubuntu home server) |

---

## Estructura del proyecto

```
camino-del-guerrero/
├── backend/
│   ├── core/              # Configuración global (settings, urls, wsgi)
│   ├── users/             # Autenticación, roles y gestión de usuarios
│   ├── routines/          # Rutinas y ejercicios con video YouTube
│   ├── timer/             # Lógica de rounds y descanso
│   ├── progress/          # Log diario y registro de peso
│   └── manage.py
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── auth/
│   │   │   ├── routines/
│   │   │   ├── timer/
│   │   │   └── progress/
│   └── angular.json
└── README.md
```

---

## Módulos del MVP

### Auth
- Registro e inicio de sesión con JWT
- Roles: `admin` y `user`
- El admin gestiona rutinas y ejercicios
- El usuario registra su progreso personal

### Rutinas
- El admin crea rutinas (ej: Boxeo, Cardio, Fuerza)
- Cada rutina tiene días de la semana asignados
- Cada día tiene ejercicios con sets, reps y duración
- Cada ejercicio tiene un video de YouTube embebido

### Timer
- Rounds configurables (duración y descanso)
- Alarma entre rounds
- Contador de rounds completados

### Progreso
- Log diario de entrenamiento (rounds, duración, notas)
- Registro de peso quincenal/mensual
- Historial personal por usuario

---

## Modelo de datos principal

```
User ──< TrainingLog
User ──< WeightRecord
Routine ──< RoutineDay ──< RoutineDayExercise >── Exercise
```

### Entidades clave

**User:** `id, nombre, email, password, role, fecha_registro`

**Exercise:** `id, nombre, descripcion, youtube_url, tipo`

**Routine:** `id, nombre, tipo, descripcion, creado_por`

**RoutineDay:** `id, routine_id, dia_semana, orden`

**RoutineDayExercise:** `routineday_id, exercise_id, sets, reps, duracion_seg`

**TrainingLog:** `id, user_id, fecha, routine_id, rounds_completados, notas, duracion_min`

**WeightRecord:** `id, user_id, fecha, peso_kg`

---

## Permisos por rol

| Acción | Admin | Usuario |
|---|---|---|
| Crear/editar rutinas | ✅ | ❌ |
| Ver rutinas | ✅ | ✅ |
| Registrar log diario | ✅ | ✅ |
| Ver su propio progreso | ✅ | ✅ |
| Ver progreso de otros | ✅ | ❌ |

---

## Variables de entorno (backend)

Crear un archivo `.env` en `/backend`:

```env
SECRET_KEY=tu_secret_key
DEBUG=True
DB_NAME=camino_db
DB_USER=camino_user
DB_PASSWORD=tu_password
DB_HOST=localhost
DB_PORT=5432
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

---

## Roadmap

- [x] Diseño de arquitectura y modelo de datos
- [ ] Módulo Auth (usuarios y roles)
- [ ] Módulo Rutinas (CRUD admin + visualización)
- [ ] Módulo Timer (rounds + descanso)
- [ ] Módulo Progreso (log + peso)
- [ ] PWA (funcionalidad offline)
- [ ] Docker Compose para deploy en CasaOS
- [ ] IA para sugerencias personalizadas (fase futura)