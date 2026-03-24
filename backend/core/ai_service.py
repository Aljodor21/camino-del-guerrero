import json
from datetime import date

import requests
from django.conf import settings


class AIService:
    def __init__(self):
        self.provider = settings.AI_PROVIDER
        self.base_url = settings.AI_BASE_URL
        self.model = settings.AI_MODEL
        self.api_key = settings.AI_API_KEY

    def _chat(self, prompt, max_tokens=4096):
        if self.provider == 'ollama':
            url = f'{self.base_url}/api/generate'
            payload = {'model': self.model, 'prompt': prompt, 'stream': False}
            headers = {}
        else:
            url = f'{self.base_url}/v1/chat/completions'
            payload = {
                'model': self.model,
                'messages': [{'role': 'user', 'content': prompt}],
                'max_tokens': max_tokens,
            }
            headers = {'Authorization': f'Bearer {self.api_key}'}

        response = requests.post(
            url, json=payload, headers=headers, timeout=600)
        if not response.ok:
            raise Exception(f'AI error {response.status_code}: {response.text}')
        response.raise_for_status()
        data = response.json()

        if self.provider == 'ollama':
            return data.get('response', '')
        return data['choices'][0]['message']['content']

    def _chat_json(self, prompt, max_tokens=8192, retries=3):
        import re, time
        for attempt in range(retries + 1):
            try:
                return self._parse_json(self._chat(prompt, max_tokens))
            except json.JSONDecodeError:
                if attempt == retries:
                    raise
            except Exception as e:
                msg = str(e)
                if '429' in msg:
                    wait = 15
                    match = re.search(r'try again in (\d+(?:\.\d+)?)s', msg)
                    if match:
                        wait = float(match.group(1)) + 2
                    if attempt == retries:
                        raise
                    time.sleep(wait)
                else:
                    raise

    def _parse_json(self, text):
        """Limpia y parsea el JSON, tolerando markdown y texto extra."""
        import re
        text = text.strip()
        # Quitar bloque <think>...</think> de modelos de razonamiento
        text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()
        # Quitar bloques markdown: ```json ... ``` o ``` ... ```
        if text.startswith('```'):
            text = text.split('```')[1]
            if text.startswith('json'):
                text = text[4:]
            text = text.strip()
        # Intentar parsear directamente
        return json.loads(text, strict=False)

    def _perfil(self, usuario):
        edad = None
        if usuario.fecha_nacimiento:
            hoy = date.today()
            edad = hoy.year - usuario.fecha_nacimiento.year - (
                (hoy.month, hoy.day) < (
                    usuario.fecha_nacimiento.month, usuario.fecha_nacimiento.day)
            )
        return {
            'sexo':     usuario.sexo.nombre if usuario.sexo else 'No especificado',
            'edad':     f'{edad} años' if edad else 'No especificada',
            'estatura': f'{usuario.estatura} cm' if usuario.estatura else 'No especificada',
        }

    def generar_plan_nutricional(self, usuario, objetivo):
        p = self._perfil(usuario)
        pref = usuario.preferencias_alimentarias or 'Ninguna'
        nacionalidad = usuario.nacionalidad or 'No especificada'
        region = usuario.region or 'No especificada'
        es_dia_entreno = f"Los días de entrenamiento son {objetivo.dias_entrenamiento} por semana (distribuidos entre lunes y viernes preferiblemente)."
        prompt = f"""
Eres un nutricionista deportivo con 15 años de experiencia trabajando con boxeadores y atletas de combate en Latinoamérica. Tu especialidad es diseñar planes alimentarios basados en la gastronomía local de cada región, usando ingredientes reales que se consiguen en plazas de mercado y tiendas de barrio, no en supermercados de cadena ni restaurantes.

## PERFIL DEL ATLETA
- Sexo: {p['sexo']}
- Edad: {p['edad']}
- Estatura: {p['estatura']}
- Peso actual: {objetivo.peso_inicial} kg
- Peso objetivo: {objetivo.peso_objetivo if objetivo.peso_objetivo else 'No definido'} kg
- Objetivo principal: {objetivo.get_objetivo_display()}
- Nacionalidad: {nacionalidad}
- Región o zona cultural: {region}
- Restricciones o preferencias alimentarias: {pref}
- Frecuencia de entrenamiento: {objetivo.dias_entrenamiento} días por semana

## REGLAS OBLIGATORIAS

### Cultura culinaria (MÁS IMPORTANTE)
1. Usa EXCLUSIVAMENTE platos, ingredientes y preparaciones típicas de la región "{region}" dentro de {nacionalidad}.
2. Si la región es reconocible (paisa, costeño, valluno, santandereano, llanero, bogotano, caleño, etc.), usa sus platos emblema:
   - Paisa: fríjoles con pezuña, bandeja paisa, arepa de chócolo, mazamorra, chicharrón, aguapanela.
   - Costeño: arroz con coco, patacones, sancocho de pescado, bollo de yuca, fritos de maíz.
   - Valluno / Caleño: sancocho de gallina, cholado, lulada, empanadas de pipián, pandebono.
   - Bogotano: ajiaco, changua, chocolate con pan, papa criolla, calentado.
   - Santandereano: pepitoria, cabro, mute, arepa de maíz pelado.
3. Ingredientes que se encuentran en tiendas de barrio o plazas de mercado locales. NADA de ingredientes importados, nombres en inglés ni comida de restaurante gourmet.
4. PROHIBIDO usar estas verduras que NO son típicas de la cocina popular colombiana: acelgas, kale, espárragos, alcachofas, rúcula, berros, puerro, coliflor, coles de bruselas, remolacha. En su lugar usa: tomate, cebolla, zanahoria, habichuela, pepino, ahuyama, espinaca criolla, aguacate, cilantro, pimentón.

### Calorías y macros según objetivo
- Bajar peso: déficit de 300-400 kcal respecto al mantenimiento estimado.
- Ganar músculo: superávit de 200-300 kcal, alto en proteína (1.8-2.2 g/kg).
- Mantener peso: calorías de mantenimiento, balance de macros.
- Mejorar resistencia: alto en carbohidratos complejos, proteína moderada.

### Estructura diaria
4. Cada día debe incluir: desayuno, almuerzo, cena y snacks.
5. {es_dia_entreno} En días de entrenamiento: el almuerzo o desayuno previo al entreno debe ser más alto en carbohidratos complejos (arroz, papa, plátano, yuca). La cena post-entreno debe incluir proteína y vegetales.
6. Snacks: 1 o 2 opciones proteicas simples y locales (yogur, huevo cocido, maní, arepa con queso, fruta con leche).
7. Varía los platos cada día. No repitas el mismo menú en días consecutivos.

### Formato de porciones
8. Especifica cantidades concretas: "1 taza de arroz blanco", "2 muslos de pollo asado", "1 arepa mediana con 2 cucharadas de hogao". Nunca escribas solo el nombre del plato sin porciones.
9. Medidas permitidas ÚNICAMENTE: taza, cucharada, cucharadita, unidad, gramos, porciones. PROHIBIDO usar: "chorrito", "poquito", "al gusto", "un poco", "a discreción", "cantidad suficiente".
10. Máximo 25 palabras por campo (desayuno, almuerzo, cena, snacks). Directo y práctico.
11. No uses palabras en inglés. No uses nombres de suplementos.

### Restricciones alimentarias
11. Respeta ESTRICTAMENTE las restricciones indicadas: "{pref}". Si dice vegetariano, elimina toda carne. Si dice sin gluten, elimina pan de trigo, etc.

## VERIFICACIÓN ANTES DE RESPONDER
Antes de generar el JSON, verifica mentalmente:
- ¿Todos los platos son típicos de {region}?
- ¿Todas las porciones están especificadas con cantidades (taza, cucharada, unidad, gramos)?
- ¿Usé alguna palabra prohibida como "chorrito", "poquito", "al gusto"? Si sí, reemplázala.
- ¿Usé alguna verdura prohibida como acelgas, kale, espárragos? Si sí, cámbiala por tomate, zanahoria o habichuela.
- ¿Los 7 días tienen variedad (no se repite el mismo plato dos días seguidos)?
- ¿Las calorías están ajustadas al objetivo "{objetivo.get_objetivo_display()}"?

## FORMATO DE SALIDA
Responde ÚNICAMENTE con este JSON, sin markdown, sin texto antes ni después:
{{
  "nombre": "Plan [objetivo] para atleta de boxeo - [region]",
  "dias": [
    {{
      "dia_semana": 1,
      "desayuno": "Descripción con porciones exactas",
      "almuerzo": "Descripción con porciones exactas",
      "cena": "Descripción con porciones exactas",
      "snacks": "1-2 opciones con porciones",
      "calorias_aprox": 2100
    }}
  ]
}}
Incluye exactamente 7 días (dia_semana: 1=lunes hasta 7=domingo).
"""
        return self._chat_json(prompt)

    def generar_lista_mercado(self, plan):
        comidas = []
        for dia in plan.dias.all():
            comidas.append(f'{dia.get_dia_semana_display()}: {dia.desayuno} | {dia.almuerzo} | {dia.cena} | {dia.snacks}')
        texto_plan = '\n'.join(comidas)

        prompt = f"""
Eres un asistente de compras preciso. Tu única tarea es extraer los ingredientes del plan alimentario que se te da y convertirlos en una lista de mercado organizada para 1 persona durante 7 días.

## PLAN ALIMENTARIO DE LA SEMANA
{texto_plan}

## REGLAS ESTRICTAS DE EXTRACCIÓN

### Qué SÍ incluir
1. Solo ingredientes que aparecen EXPLÍCITAMENTE mencionados en el texto del plan anterior.
2. Consolida el mismo ingrediente que aparece en varios días: suma las cantidades en una sola entrada. Ejemplo: si hay "1 taza de arroz" en 5 días → "Arroz blanco: 5 tazas (aprox. 900g)".
3. Convierte las porciones a unidades de mercado prácticas: tazas → gramos/kg, unidades → docenas si aplica.
4. Escribe el nombre del ingrediente en su forma genérica de compra (ej: "Pechuga de pollo" no "pollo asado con papas").

### Qué NO incluir
5. NO agregues ingredientes que no estén en el texto (nada de sal, aceite, agua, azúcar, ni condimentos básicos a menos que el plan los mencione explícitamente).
6. NO inventes ingredientes por inferencia. Si el plan dice "sancocho de pollo" solo extrae "pollo" y las verduras que mencione, no inventes que lleva yuca si no lo dice.
7. NO incluyas preparaciones ni platos completos, solo el ingrediente en bruto (ej: "huevos", no "huevos revueltos").
8. NO repitas el mismo ingrediente en dos categorías distintas.

### Categorías
9. Clasifica cada ingrediente en exactamente una de estas categorías (usa estos valores exactos en minúscula):
   - proteinas: carnes, pollo, pescado, huevos, legumbres, fríjoles, lentejas
   - verduras: verduras, hortalizas, tubérculos (papa, yuca, plátano verde)
   - frutas: frutas frescas, jugos de fruta natural
   - lacteos: leche, queso, yogur, mantequilla, crema
   - granos: arroz, pasta, pan, arepa, avena, maíz
   - condimentos: salsas, especias, hogao, panela, caldo (solo si están explícitamente en el plan)
10. Si un ítem no encaja claramente en ninguna categoría, ponlo en la más cercana.
11. Omite categorías que no tengan ningún ítem.

## VERIFICACIÓN ANTES DE RESPONDER
Revisa mentalmente:
- ¿Cada ítem de la lista aparece textualmente en el plan?
- ¿Consolidé las repeticiones semanales en una sola cantidad?
- ¿Las cantidades son realistas para 1 persona en 7 días?
- ¿Hay algún ingrediente duplicado en dos categorías? Si sí, elimínalo de una.

## FORMATO DE SALIDA
Responde ÚNICAMENTE con este JSON, sin markdown, sin texto antes ni después:
{{
  "categorias": [
    {{
      "categoria": "proteinas",
      "items": [
        {{"nombre": "Huevos", "cantidad": "14 unidades"}},
        {{"nombre": "Pechuga de pollo", "cantidad": "1.2 kg"}}
      ]
    }}
  ]
}}
"""
        return self._chat_json(prompt)

    # ── Configuración por enfoque ─────────────────────────────────────
    _ENFOQUE_CONFIG = {
        'boxeo': {
            'persona': 'Eres un entrenador de boxeo profesional con 15 años de experiencia entrenando atletas de barrio en Latinoamérica. Diseñas rutinas PRÁCTICAS y REALIZABLES con lo que el atleta tiene en casa o en su gimnasio local.',
            'implementos_desc': {
                'Saco de boxeo':      'golpes directos (jab, cross, uppercut, hook) con potencia real, trabajo de distancia',
                'Guantes de boxeo':   'necesarios para golpear el saco o el escudo; sin ellos solo se hace sombra',
                'Cuerda para saltar': 'cardio específico de boxeo, coordinación y ritmo de pies',
                'Escudo':             'trabajo en pareja con el entrenador o compañero, combinaciones con target real',
                'Vendas':             'protección de manos, siempre se usan con guantes',
                'Pera de velocidad':  'velocidad de golpe, timing, coordinación ojo-mano',
                'Sin implemento':     'solo trabajo de sombra, ejercicios de peso corporal y footwork',
            },
            'estructura': '1. Calentamiento (5-8 min): trote en sitio, movilidad articular, activación de hombros.\n2. Bloque técnico: golpes, combinaciones o footwork según el día.\n3. Bloque físico: fuerza, resistencia o cardio con los implementos disponibles.\n4. Vuelta a la calma (3-5 min): estiramientos y respiración.',
            'ejercicios_permitidos': (
                '- Sombra (siempre): jab, cross, uppercut, hook, combinaciones 1-2, 1-2-3, bob and weave, slip, footwork en L, pivote.\n'
                '- Con saco: rounds al saco, golpes de poder, combinaciones al saco.\n'
                '- Con cuerda: salto de cuerda constante, salto alternado, doble giro.\n'
                '- Con escudo: combinaciones con escudo, jab-cross, hooks al escudo.\n'
                '- Físico: burpees, sentadillas con salto, planchas, abdominales, lagartijas, mountain climbers.'
            ),
            'variedad': 'Distribuye los días entre: técnica ofensiva, técnica defensiva, combinaciones, trabajo físico, velocidad.',
            'busqueda_media': (
                '- Jab → "boxing jab"\n- Cross → "boxing cross"\n- Uppercut → "boxing uppercut"\n'
                '- Hook → "boxing hook"\n- Combinación 1-2 → "boxing jab cross combination"\n'
                '- Sombra → "shadow boxing"\n- Bob and weave → "boxing bob weave"\n'
                '- Slip → "boxing slip dodge"\n- Footwork → "boxing footwork"\n'
                '- Pivote → "boxing pivot footwork"\n- Rounds al saco → "boxing heavy bag"\n'
                '- Pera de velocidad → "boxing speed bag"\n- Escudo → "boxing focus mitts"\n'
                '- Cuerda → "jump rope boxing"\n- Burpees → "burpee exercise"\n'
                '- Sentadillas con salto → "jump squat exercise"\n- Planchas → "plank exercise"\n'
                '- Lagartijas → "push up exercise"\n- Mountain climbers → "mountain climber exercise"\n'
                '- Abdominales → "boxing abs workout"\n- Calentamiento → "boxing warm up"\n'
                '- Estiramientos → "boxing cool down stretch"'
            ),
        },
        'cardio_casa': {
            'persona': 'Eres un entrenador de cardio en casa con 10 años de experiencia diseñando rutinas intensas y efectivas sin necesidad de ir al gimnasio. Tus rutinas usan implementos básicos como cuerda, colchoneta y peso corporal.',
            'implementos_desc': {
                'Cuerda para saltar': 'cardio de alto impacto, coordinación y quema calórica',
                'Colchoneta':         'ejercicios de suelo, abdominales, estiramientos y yoga',
                'Mancuernas':         'resistencia adicional en ejercicios de peso corporal',
                'Sin implemento':     'peso corporal puro: burpees, saltos, mountain climbers',
            },
            'estructura': '1. Calentamiento dinámico (5 min): jumping jacks, trote en sitio, movilidad.\n2. Bloque cardio principal: intervalos o circuitos continuos.\n3. Bloque de fuerza corporal: ejercicios de tonificación.\n4. Vuelta a la calma (5 min): respiración y estiramientos.',
            'ejercicios_permitidos': (
                '- Cardio: salto de cuerda, jumping jacks, burpees, mountain climbers, saltos en estrella, trote en sitio, high knees.\n'
                '- Fuerza corporal: sentadillas, zancadas, planchas, lagartijas, abdominales, puente de glúteos, superman.\n'
                '- Cardio HIIT: tabata de burpees, intervalos de cuerda, circuitos de saltos.\n'
                '- Con colchoneta: abdominales variados, estiramiento, yoga básico.'
            ),
            'variedad': 'Distribuye los días entre: día de cardio puro, día de fuerza corporal, día HIIT mixto.',
            'busqueda_media': (
                '- Salto de cuerda → "jump rope cardio"\n- Jumping jacks → "jumping jacks exercise"\n'
                '- Burpees → "burpee exercise"\n- Mountain climbers → "mountain climber exercise"\n'
                '- High knees → "high knees cardio"\n- Sentadillas → "squat exercise"\n'
                '- Zancadas → "lunge exercise"\n- Planchas → "plank exercise"\n'
                '- Lagartijas → "push up exercise"\n- Abdominales → "crunches exercise"\n'
                '- Puente de glúteos → "glute bridge exercise"\n- Superman → "superman exercise"\n'
                '- HIIT circuito → "hiit workout home"\n- Calentamiento → "cardio warm up"\n'
                '- Estiramientos → "full body stretch cool down"'
            ),
        },
        'funcional': {
            'persona': 'Eres un entrenador de entrenamiento funcional e HIIT con 12 años de experiencia. Diseñas circuitos intensos que mejoran fuerza, resistencia y agilidad usando movimientos naturales del cuerpo y los implementos disponibles.',
            'implementos_desc': {
                'Cuerda para saltar': 'intervalos de cardio entre bloques funcionales',
                'Colchoneta':         'movimientos de suelo y core',
                'Mancuernas':         'carga adicional para sentadillas, peso muerto rumano, press',
                'Kettlebell':         'swings, cleans, press funcional',
                'Sin implemento':     'movimientos funcionales de peso corporal: burpees, sentadillas, dominadas',
            },
            'estructura': '1. Calentamiento funcional (5-8 min): movilidad articular completa.\n2. Bloque de fuerza funcional: movimientos compuestos pesados.\n3. Bloque HIIT: circuito de alta intensidad con poco descanso.\n4. Core y vuelta a la calma (5 min).',
            'ejercicios_permitidos': (
                '- Funcional básico: sentadillas, sentadillas con salto, zancadas alternas, burpees, lagartijas, dominadas (si hay barra).\n'
                '- Core: plancha, plancha lateral, hollow body, russian twist, mountain climbers.\n'
                '- HIIT: tabata de burpees, circuito 40-20, intervalos de salto.\n'
                '- Con mancuernas/kettlebell: swings, goblet squat, peso muerto rumano, press de hombros.\n'
                '- Cardio: salto de cuerda, jumping jacks, box jumps.'
            ),
            'variedad': 'Distribuye los días entre: día de fuerza funcional, día HIIT cardiovascular, día de core y movilidad.',
            'busqueda_media': (
                '- Sentadillas → "squat exercise"\n- Sentadilla con salto → "jump squat exercise"\n'
                '- Zancadas → "lunge exercise"\n- Burpees → "burpee exercise"\n'
                '- Lagartijas → "push up exercise"\n- Plancha → "plank exercise"\n'
                '- Mountain climbers → "mountain climber exercise"\n- Russian twist → "russian twist exercise"\n'
                '- Kettlebell swing → "kettlebell swing"\n- Goblet squat → "goblet squat"\n'
                '- Peso muerto rumano → "romanian deadlift"\n- Salto de cuerda → "jump rope hiit"\n'
                '- Circuito HIIT → "hiit circuit workout"\n- Calentamiento → "functional warm up"\n'
                '- Vuelta calma → "cool down stretch"'
            ),
        },
        'fuerza': {
            'persona': 'Eres un entrenador de fuerza y acondicionamiento con 15 años de experiencia. Diseñas programas de hipertrofia y fuerza progresiva adaptados a lo que el atleta tiene disponible en casa o gimnasio básico.',
            'implementos_desc': {
                'Mancuernas':    'ejercicios unilaterales y bilaterales de press, jalón, curl, extensión',
                'Barra':         'sentadilla, press de banca, peso muerto, remo',
                'Kettlebell':    'swings, press, goblet squat, remo',
                'Colchoneta':    'ejercicios de suelo y core',
                'Bandas elásticas': 'tensión constante para jalones, curls y extensiones',
                'Sin implemento': 'calistenia: lagartijas, fondos, sentadillas, dominadas',
            },
            'estructura': '1. Calentamiento específico (5-8 min): movilidad de articulaciones a trabajar.\n2. Ejercicio principal compuesto (el más exigente).\n3. Ejercicios accesorios (2-3 ejercicios de soporte).\n4. Core y vuelta a la calma.',
            'ejercicios_permitidos': (
                '- Piernas: sentadillas, sentadilla goblet, zancadas, peso muerto, hip thrust, step-up.\n'
                '- Pecho: lagartijas, lagartijas diamante, press con mancuernas, fondos en silla.\n'
                '- Espalda: remo con mancuernas, remo invertido, jalón con banda, dominadas.\n'
                '- Hombros: press de hombros, elevaciones laterales, Arnold press.\n'
                '- Brazos: curl de bíceps, extensión de tríceps, curl martillo.\n'
                '- Core: plancha, hollow body, dead bug, russian twist.'
            ),
            'variedad': 'Organiza los días por grupos musculares: día de piernas, día de empuje (pecho/hombros/tríceps), día de jalón (espalda/bíceps), día full-body.',
            'busqueda_media': (
                '- Sentadilla → "squat exercise"\n- Peso muerto → "deadlift exercise"\n'
                '- Lagartijas → "push up exercise"\n- Press mancuernas → "dumbbell press"\n'
                '- Remo mancuernas → "dumbbell row"\n- Fondos → "tricep dips"\n'
                '- Dominadas → "pull up exercise"\n- Curl bíceps → "bicep curl"\n'
                '- Extensión tríceps → "tricep extension"\n- Zancadas → "lunge exercise"\n'
                '- Hip thrust → "hip thrust exercise"\n- Plancha → "plank exercise"\n'
                '- Kettlebell swing → "kettlebell swing"\n- Calentamiento → "strength training warm up"\n'
                '- Vuelta calma → "cool down stretch"'
            ),
        },
        'movilidad': {
            'persona': 'Eres un instructor certificado de yoga y movilidad con 10 años de experiencia. Diseñas secuencias que mejoran flexibilidad, movilidad articular, fuerza suave y bienestar mental, adaptadas al nivel del practicante.',
            'implementos_desc': {
                'Colchoneta':    'base para todas las posturas de suelo, vinyasa y restaurativas',
                'Bloque de yoga': 'soporte para posturas con poca flexibilidad',
                'Banda elástica': 'asistencia en estiramientos profundos',
                'Sin implemento': 'posturas de pie, sentado y suelo sin soporte',
            },
            'estructura': '1. Respiración y centrado (3-5 min): respiración diafragmática.\n2. Calentamiento articular: círculos de cuello, hombros, caderas.\n3. Bloque principal: secuencia de posturas o movilidad.\n4. Posturas restaurativas y savasana (5 min).',
            'ejercicios_permitidos': (
                '- Calentamiento: círculos de cuello, hombros, caderas, tobillos, Cat-Cow.\n'
                '- Estiramiento activo: postura del guerrero I y II, triángulo, media luna.\n'
                '- Movilidad de cadera: paloma, mariposa, lagartija baja, cuadrado.\n'
                '- Core suave: tabla, puente, bird-dog, dead bug.\n'
                '- Equilibrio: árbol, guerrero III, media luna.\n'
                '- Restaurativas: niño, piernas en pared, torsión supina, savasana.'
            ),
            'variedad': 'Distribuye los días entre: movilidad de caderas y piernas, apertura de espalda y hombros, equilibrio y core suave.',
            'busqueda_media': (
                '- Cat-Cow → "cat cow yoga"\n- Guerrero I → "warrior one yoga"\n'
                '- Guerrero II → "warrior two yoga"\n- Triángulo → "triangle pose yoga"\n'
                '- Paloma → "pigeon pose yoga"\n- Mariposa → "butterfly pose yoga"\n'
                '- Lagartija baja → "low lunge yoga"\n- Tabla → "plank yoga"\n'
                '- Puente → "bridge pose yoga"\n- Bird-dog → "bird dog exercise"\n'
                '- Árbol → "tree pose yoga"\n- Postura del niño → "childs pose yoga"\n'
                '- Torsión supina → "supine twist yoga"\n- Calentamiento → "yoga warm up"\n'
                '- Savasana → "savasana relaxation"'
            ),
        },
    }

    def generar_rutina(self, usuario, implementos, objetivo):
        p = self._perfil(usuario)
        nombres = [i.implemento.nombre for i in implementos] or ['Sin implemento']
        implementos_extra = (getattr(usuario, 'implementos_adicionales', '') or '').strip()
        nivel = objetivo.get_nivel_actividad_display()
        dias  = objetivo.dias_entrenamiento
        duracion = objetivo.duracion_sesion
        nacionalidad = usuario.nacionalidad or 'No especificada'
        region = usuario.region or 'No especificada'
        enfoque = getattr(objetivo, 'enfoque_entrenamiento', 'boxeo') or 'boxeo'

        cfg = self._ENFOQUE_CONFIG.get(enfoque, self._ENFOQUE_CONFIG['boxeo'])

        nivel_config = {
            'Principiante': 'series: 2-3, carga baja, descanso 60-90s. Prioriza aprender la mecánica correcta antes que la intensidad. Explica cada ejercicio con detalle.',
            'Intermedio':   'series: 3-4, carga moderada, descanso 45-60s. Mezcla técnica con acondicionamiento físico.',
            'Avanzado':     'series: 4-5, carga alta, poco descanso (30-45s). Alta intensidad y variedad.',
        }.get(nivel, 'series: 3')

        implementos_contexto = '; '.join(
            f"{n} → {cfg['implementos_desc'].get(n, 'uso general')}" for n in nombres
        )

        prompt = f"""
{cfg['persona']}

## PERFIL DEL ATLETA
- Sexo: {p['sexo']}
- Edad: {p['edad']}
- Estatura: {p['estatura']}
- Nacionalidad: {nacionalidad} | Región: {region}
- Objetivo: {objetivo.get_objetivo_display()}
- Enfoque de entrenamiento: {objetivo.get_enfoque_entrenamiento_display()}
- Nivel: {nivel}
- Días de entrenamiento por semana: {dias}
- Duración por sesión: {duracion} minutos
- Implementos disponibles: {', '.join(nombres)}
- Implementos adicionales del atleta: {implementos_extra if implementos_extra else 'Ninguno'}
- Contexto de implementos: {implementos_contexto}

## ESTRUCTURA DE LA SESIÓN
Cada sesión de {duracion} minutos debe seguir este orden:
{cfg['estructura']}

## REGLAS OBLIGATORIAS

### Implementos — LA REGLA MÁS IMPORTANTE
1. SOLO usa ejercicios que requieran los implementos que el atleta tiene: {', '.join(nombres)}{f', {implementos_extra}' if implementos_extra else ''}.
2. Si NO tiene un implemento, NUNCA lo menciones ni lo uses.
3. Si solo tiene "Sin implemento" → toda la sesión es con peso corporal.
4. requiere_implemento = true SOLO si el ejercicio usa uno de los implementos listados.

### Cantidad y nivel
5. Genera EXACTAMENTE {dias} días. No pongas días de descanso.
6. Cada sesión: entre 6 y 8 ejercicios (incluyendo calentamiento y vuelta a la calma).
7. Nivel {nivel}: {nivel_config}

### Ejercicios permitidos para este enfoque ({objetivo.get_enfoque_entrenamiento_display()})
{cfg['ejercicios_permitidos']}

### Tipos de ejercicio
8. Por TIEMPO (cardio, circuitos): duracion_segundos = entero, series = entero, repeticiones = null.
9. Por REPETICIONES (técnica, fuerza): series = entero, repeticiones = entero, duracion_segundos = null.
10. Nunca pongas duracion_segundos y repeticiones con valor al mismo tiempo.

### Descripciones técnicas
11. Entre 35 y 60 palabras. Estructura: posición inicial → ejecución → punto clave → error común.
12. Adapta el lenguaje al nivel {nivel}: para Principiante, explica como si fuera la primera vez.

### Campo busqueda_media — CRÍTICO para mostrar GIFs al atleta
13. Cada ejercicio debe tener "busqueda_media": término de 2-4 palabras en inglés.
14. Usa estos términos estandarizados:
{cfg['busqueda_media']}

### Variedad entre días
15. {cfg['variedad']}
16. No repitas el mismo ejercicio principal dos días seguidos.

## VERIFICACIÓN ANTES DE RESPONDER
- ¿Hay exactamente {dias} días?
- ¿Todos los ejercicios con implementos usan SOLO los que tiene el atleta ({', '.join(nombres)}{f', {implementos_extra}' if implementos_extra else ''})?
- ¿Cada ejercicio tiene "busqueda_media" en inglés?
- ¿Ningún ejercicio tiene duracion_segundos y repeticiones con valor al mismo tiempo?
- ¿requiere_implemento es true solo cuando usa un implemento de la lista?
- ¿El nivel y enfoque ({objetivo.get_enfoque_entrenamiento_display()}) corresponden al perfil?

## FORMATO DE SALIDA
Responde ÚNICAMENTE con este JSON, sin markdown, sin texto antes ni después:
{{
  "nombre": "Nombre descriptivo de la rutina",
  "descripcion": "Resumen del programa en 1-2 oraciones",
  "dias": [
    {{
      "dia_semana": 1,
      "ejercicios": [
        {{
          "nombre": "Nombre claro del ejercicio",
          "descripcion": "Descripción técnica completa de 35-60 palabras",
          "busqueda_media": "exercise term",
          "requiere_implemento": false,
          "series": 3,
          "repeticiones": 12,
          "duracion_segundos": null,
          "orden": 1
        }}
      ]
    }}
  ]
}}
"""
        return self._chat_json(prompt)
