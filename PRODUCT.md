# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users
Gente común en Colombia que quiere cambiar algo de su vida (comer mejor, ganar masa, bajar de peso, moverse más) y muchas veces no sabe por dónde empezar. Algunos tienen nutricionista (por ejemplo de Comfama) y otros no. Pueden entrenar boxeo, fuerza, funcional, cardio en casa o yoga, o no entrenar y solo ocuparse de la comida. Usan la app sobre todo desde el celular.

## Product Purpose
Acompañar un proceso con meta: un punto de partida que no cambia, un plan de comida que respeta lo que dio la nutricionista (o uno calculado si no la hay), un entreno a la medida y un registro honesto del avance. El éxito es que la persona sostenga su proceso, no que lo empiece.

## Positioning
El menú de cada semana sale solo de la minuta patrón y de la lista de intercambios: nada inventado, y cualquier cambio de comida vale lo mismo que la original. La app sirve para todos los niveles y deportes, y está pensada para quien no sabe qué hacer.

## Operating Context
- Onboarding por pasos: qué manejar (alimentación, entrenamiento o ambos), quién arma el plan (nutricionista o IA), objetivo y fase, inicio con medición inicial, hasta cuándo va, suplementos.
- Minuta por plantilla en la app o leída del PDF de Comfama; original adjunto como respaldo.
- Menú semanal, "No puedo con esta comida", comidas por fuera, lista de mercado.
- Rutinas por enfoque e implementos, sesión con temporizador.
- Medidas, fotos privadas de frente/perfil/espalda y comparación con el inicio.
- Agenda con recordatorios propios y sugeridos (control, reponer suplemento, qué sigue).

## Capabilities and Constraints
- Datos de inicio y minuta guardada son inmutables.
- La IA (Claude u otro proveedor configurable) propone; el servidor valida contra la minuta.
- Stack: Django 6 + DRF, Angular 21 + PrimeNG + Tailwind v4, Docker.

## Brand Commitments
- Nombre: Camino del Guerrero. "Guerrero" significa constancia y esfuerzo, no pelea: el tono es incluyente y de propósito, no de combate.
- Colores de marca: rojo #C0392B y dorado #D4AF37. Logos en `frontend/public/Logo claro-sf.png` y `Logo oscuro-sf.png`.
- Sin logos, estrellitas ni brillos de IA. La IA se nombra como herramienta.
- Textos en español colombiano, cercanos.

## Evidence on Hand
- Fotos de la landing en `frontend/public/home/` (sendero al amanecer, yoga en casa, sentadillas en casa, boxeo, desayuno colombiano, cinta métrica, amarrarse los tenis, cumbre). Generadas con IA por el usuario.
- No hay testimonios, usuarios reales, cifras ni prensa: no se inventan.

## Product Principles
1. Lo de la nutricionista manda; la app no se sale de su plan.
2. Para todos: ningún deporte, cuerpo o nivel es el "correcto".
3. El punto de partida es sagrado: se guarda y no se toca.
4. Acompañar más que exigir: avisar a tiempo, proponer, no regañar.

## Accessibility & Inclusion
Lectura cómoda en celular, contraste suficiente sobre fotos, movimiento reducido respetado. (Deducido del brief; no hay un estándar exigido.)
