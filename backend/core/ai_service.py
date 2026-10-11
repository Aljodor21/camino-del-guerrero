import json
from datetime import date

import anthropic
import requests
from django.conf import settings

# Modelos de Claude que aceptan el respaldo automático cuando el modelo declina responder.
CLAUDE_CON_RESPALDO = ('claude-fable-5-1', 'claude-opus-5-5', 'claude-opus-5', 'claude-sonnet-5-5')


class AIService:
    def __init__(self):
        self.provider = settings.AI_PROVIDER
        self.base_url = settings.AI_BASE_URL
        self.model = settings.AI_MODEL
        self.api_key = settings.AI_API_KEY

    def _chat_claude(self, prompt, max_tokens):
        """Claude con el SDK oficial de Anthropic (AI_PROVIDER=anthropic)."""
        cliente = anthropic.Anthropic(api_key=self.api_key, timeout=600)
        opciones = {}
        if self.model in CLAUDE_CON_RESPALDO:
            opciones = {'betas': ['server-side-fallback-2026-07-01'], 'fallbacks': 'default'}
        respuesta = cliente.beta.messages.create(
            model=self.model,
            # El razonamiento del modelo también cuenta en max_tokens: se deja holgura.
            max_tokens=max(max_tokens, 16000),
            messages=[{'role': 'user', 'content': prompt}],
            **opciones,
        )
        if respuesta.stop_reason == 'refusal':
            raise Exception('Claude no quiso responder esta solicitud.')
        if respuesta.stop_reason == 'max_tokens':
            raise Exception('La respuesta de Claude quedó cortada.')
        return ''.join(b.text for b in respuesta.content if b.type == 'text')

    def _chat(self, prompt, max_tokens=4096):
        if self.provider == 'anthropic':
            return self._chat_claude(prompt, max_tokens)
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
            if 'deepseek.com' in self.base_url:
                # v4-flash/v4-pro piensan por defecto y se comen el max_tokens
                # razonando antes de escribir el JSON — lo desactivamos.
                payload['thinking'] = {'type': 'disabled'}
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
                if attempt == retries:
                    raise
                msg = str(e)
                wait = 3
                if '429' in msg:
                    wait = 15
                    match = re.search(r'try again in (\d+(?:\.\d+)?)s', msg)
                    if match:
                        wait = float(match.group(1)) + 2
                # DeepSeek a veces devuelve contenido vacío/cortado o un 5xx
                # transitorio — reintentamos en vez de fallar de una.
                time.sleep(wait)

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

    def _proceso(self, usuario, proceso):
        """Datos del proceso que comparten los prompts de nutrición y rutina."""
        ultima = usuario.mediciones.first()
        peso_actual = ultima.peso_kg if ultima else (
            proceso.medicion_inicial.peso_kg if proceso.medicion_inicial else None)
        entreno = getattr(proceso, 'entrenamiento', None) if proceso.incluye_entrenamiento else None
        return {
            'objetivo':      proceso.get_objetivo_display(),
            'fase':          proceso.get_fase_display() or 'No definida',
            'peso_actual':   f'{peso_actual} kg' if peso_actual else 'No registrado',
            'peso_objetivo': f'{proceso.peso_objetivo} kg' if proceso.peso_objetivo else 'No definido',
            'entrenamiento': entreno,
        }

    def calcular_minuta(self, usuario, proceso, kcal, proteina, kcal_porcion):
        p = self._perfil(usuario)
        c = self._proceso(usuario, proceso)
        prompt = f"""
Eres un nutricionista deportivo colombiano. Arma la MINUTA PATRÓN de un atleta: cuántas porciones de cada grupo de intercambio come en cada comida del día. No escribas platos: solo porciones. Luego el atleta elige los alimentos con su lista de intercambios.

## ATLETA
- Sexo: {p['sexo']} · Edad: {p['edad']} · Estatura: {p['estatura']}
- Peso actual: {c['peso_actual']} · Peso objetivo: {c['peso_objetivo']}
- Objetivo: {c['objetivo']} · Fase: {c['fase']}
- Restricciones o preferencias: {usuario.preferencias_alimentarias or 'Ninguna'}

## METAS DEL DÍA (ya calculadas, no las cambies)
- Calorías: {kcal} kcal (la suma de tus porciones debe quedar a menos de 5 % de esto).
- Proteína: {proteina} g por kilo de peso.

## CALORÍAS DE UNA PORCIÓN POR GRUPO
{kcal_porcion}

## REGLAS
1. Comidas posibles: desayuno, onces (media mañana), almuerzo, algo (media tarde), cena, merienda. Usa 5 o 6 comidas; no dejes más de 4 horas sin comer.
2. Porciones en múltiplos de 0.5.
3. Proteína (carnes, sustitutos, lácteos, leguminosas) repartida en el día, no toda en una comida.
4. Cereales, raíces, tubérculos y plátanos como base de energía, más en desayuno y almuerzo. En volumen, más cereales y grasas buenas.
5. Verduras en almuerzo y cena; frutas en las comidas intermedias.
6. "semillas" y "agua" van en "dia" (se comen o toman en cualquier momento). Agua: entre 8 y 10 vasos.
7. Respeta las restricciones del atleta (si no come carne, usa leguminosas y sustitutos).

## FORMATO DE SALIDA
Responde ÚNICAMENTE con este JSON, sin markdown ni texto extra. Grupos válidos: sustitutos, lacteos, carnes, leguminosas, cereales, verduras, frutas, grasas, semillas, agua.
{{"porciones": {{"cereales": {{"desayuno": 2, "almuerzo": 4, "cena": 2}}, "agua": {{"dia": 8}}}}, "recomendaciones": "2 o 3 recomendaciones cortas para este atleta."}}
"""
        return self._chat_json(prompt, max_tokens=1500)

    def generar_lista_mercado(self, texto_plan, num_personas=1, excluir=None):
        personas_txt = f'{num_personas} persona' if num_personas == 1 else f'{num_personas} personas'

        excluir = excluir or []
        bloque_excluir = ''
        if excluir:
            lista_excluir = ', '.join(excluir)
            bloque_excluir = f"""
## YA COMPRADOS — NO INCLUIR
El atleta ya compró estos ítems hace poco y todavía le duran (son de compra quincenal): {lista_excluir}.
NO los incluyas en la lista, aunque aparezcan en el plan de la semana.
"""

        prompt = f"""
Eres un asesor colombiano de mercado y meal prep, preciso y práctico. Tu tarea tiene tres partes: (1) extraer los ingredientes del plan alimentario y convertirlos en una lista de mercado organizada para {personas_txt} durante 7 días, (2) dar consejos reales de dónde comprar cada cosa más barato en Colombia, y (3) armar un plan de preparación de inicio de semana para ahorrar tiempo entre semana.

## PLAN ALIMENTARIO DE LA SEMANA
{texto_plan}
{bloque_excluir}

## REGLAS ESTRICTAS DE EXTRACCIÓN

### Qué SÍ incluir
1. Solo ingredientes que aparecen EXPLÍCITAMENTE mencionados en el texto del plan anterior.
2. El plan está escrito para 1 persona por porción — MULTIPLICA cada cantidad por {num_personas} antes de consolidar, porque la lista es para {personas_txt}.
3. Consolida el mismo ingrediente que aparece en varios días: suma las cantidades YA multiplicadas en una sola entrada.
4. La cantidad final SIEMPRE debe ser algo que se compre tal cual en una tienda colombiana — NUNCA cucharadas, cucharaditas ni tazas en el resultado final (esas son medidas de cocina, no de compra):
   - Sólidos y granos (arroz, lentejas, azúcar, panela, avena, carnes, harinas): usa LIBRAS como unidad principal (1 libra = 500g). Ejemplo: si hay "1 taza de arroz" en 5 días para 1 persona → "Arroz blanco: 2 libras" (redondea hacia arriba al medio o entero más cercano, nunca dejes gramos sueltos como "900g").
   - Líquidos (aceite, vinagre, salsas líquidas, jugo): usa BOTELLA con la presentación real que se vende en Colombia: 250 ml, 500 ml o 1 L — elige la que más se acerque sin quedar corto. Ejemplo: "2 cucharaditas de vinagre" en varios días → "Vinagre blanco: 1 botella de 250 ml".
   - Unidades discretas (huevos, arepas, panes): unidad o docena.
   - Condimentos en polvo que se compran en bolsa/paquete pequeño (sal, comino, pimienta, color): 1 paquete o bolsita pequeña, nunca "cucharadita".
5. Escribe el nombre del ingrediente en su forma genérica de compra (ej: "Pechuga de pollo" no "pollo asado con papas").

### Qué NO incluir
6. NO agregues ingredientes que no estén en el texto (nada de sal, aceite, agua, azúcar, ni condimentos básicos a menos que el plan los mencione explícitamente).
7. NO inventes ingredientes por inferencia. Si el plan dice "sancocho de pollo" solo extrae "pollo" y las verduras que mencione, no inventes que lleva yuca si no lo dice.
8. NO incluyas preparaciones ni platos completos, solo el ingrediente en bruto (ej: "huevos", no "huevos revueltos").
9. NO repitas el mismo ingrediente en dos categorías distintas.

### Categorías
10. Clasifica cada ingrediente en exactamente una de estas categorías (usa estos valores exactos en minúscula):
   - proteinas: carnes, pollo, pescado, huevos, legumbres, fríjoles, lentejas
   - verduras: verduras, hortalizas, tubérculos (papa, yuca, plátano verde)
   - frutas: frutas frescas, jugos de fruta natural
   - lacteos: leche, queso, yogur, mantequilla, crema
   - granos: arroz, pasta, pan, arepa, avena, maíz
   - condimentos: salsas, especias, hogao, panela, caldo (solo si están explícitamente en el plan)
11. Si un ítem no encaja claramente en ninguna categoría, ponlo en la más cercana.
12. Omite categorías que no tengan ningún ítem.

### Frecuencia de compra
12b. Clasifica cada ítem también por frecuencia (usa exactamente "semanal" o "quincenal"):
   - semanal: todo lo perecedero — carnes frescas, pescado, verduras, frutas, lácteos, huevos.
   - quincenal: todo lo no perecedero que dura semanas — granos secos (arroz, lentejas, fríjoles, avena, pasta), enlatados, panela, aceite, vinagre, condimentos, aseo.

### Consejos de compra (ahorro real)
13. Genera de 3 a 5 tips concretos de dónde comprar más barato cada tipo de producto DE ESTA LISTA en Colombia:
    - Granos, enlatados, aseo: normalmente más baratos en tiendas de descuento duro (D1, Ara, Justo & Bueno).
    - Carnes, frutas y verduras frescas: normalmente más baratas en plaza de mercado o tienda de barrio que en supermercado de cadena.
    - Lácteos: comparar precio de marca propia en D1/Ara contra marca reconocida antes de comprar.
14. Usa ÚNICAMENTE nombres reales de tiendas colombianas: D1, Ara, Justo & Bueno, Éxito, Olímpica, Carulla, plaza de mercado, tienda de barrio. No inventes cadenas que no existen.
15. Sé específico con los ítems de ESTA lista (ej. "el arroz y las lentejas" en vez de "los granos en general").

### Plan de preparación (meal prep de inicio de semana)
16. Genera de 4 a 6 pasos concretos de qué preparar el domingo o primer día, basados en los platos REALES del plan de la semana (arriba), para que el resto de la semana solo sea calentar o armar.
17. Cada paso debe ser accionable: qué cocinar, cuánta cantidad, y cómo guardarlo (nevera o congelador, cuántos días dura).
18. Prioriza lo que más tiempo toma entre semana: proteínas (cocinar y porcionar de una vez), granos base (arroz, lentejas, frijoles), y lo que se dañe rápido si no se prepara bien. Ten en cuenta que la cantidad ya está pensada para {personas_txt}.

## VERIFICACIÓN ANTES DE RESPONDER
Revisa mentalmente:
- ¿Cada ítem de la lista aparece textualmente en el plan?
- ¿Consolidé las repeticiones semanales en una sola cantidad?
- ¿Multipliqué las cantidades por {num_personas} antes de consolidar?
- ¿Las cantidades son realistas para {personas_txt} en 7 días?
- ¿Alguna cantidad quedó en cucharadas, cucharaditas o tazas? Si sí, conviértela a libras (sólidos/granos) o botella de 250/500/1000 ml (líquidos).
- ¿Hay algún ingrediente duplicado en dos categorías? Si sí, elimínalo de una.
- ¿Cada ítem tiene frecuencia "semanal" o "quincenal" asignada correctamente?
- ¿Excluí los ítems de la sección "YA COMPRADOS" si aplica?
- ¿Los consejos de compra mencionan solo tiendas reales de Colombia y son específicos a los ítems de esta lista?
- ¿El plan de preparación se basa en los platos reales de esta semana, no en genéricos?

## FORMATO DE SALIDA
Responde ÚNICAMENTE con este JSON, sin markdown, sin texto antes ni después:
{{
  "categorias": [
    {{
      "categoria": "proteinas",
      "items": [
        {{"nombre": "Huevos", "cantidad": "14 unidades", "frecuencia": "semanal"}},
        {{"nombre": "Pechuga de pollo", "cantidad": "3 libras", "frecuencia": "semanal"}},
        {{"nombre": "Vinagre blanco", "cantidad": "1 botella de 250 ml", "frecuencia": "quincenal"}}
      ]
    }}
  ],
  "consejos_compra": [
    "El arroz y las lentejas salen más baratos en D1 o Ara que en un supermercado grande.",
    "La pechuga de pollo y las verduras frescas cómpralas en la plaza de mercado o tienda de barrio."
  ],
  "plan_preparacion": [
    "Domingo: cocina las 5 pechugas de pollo de una vez, porciona en recipientes y congela 3, deja 2 en nevera para lunes y martes.",
    "Domingo: cocina 2 tazas de arroz, guárdalo en nevera hasta 3 días y recaliéntalo con un poco de agua."
  ]
}}
"""
        return self._chat_json(prompt)

    def _minuta_texto(self, usuario, minuta):
        ejemplo = '\n'.join(f'- {t}: {texto}' for t, texto in minuta.menu_ejemplo.items()) or 'No trae.'
        autor = 'dado por su nutricionista' if minuta.origen == 'nutricionista' else 'calculado para él'
        return f"""## PLAN DEL ATLETA ({autor})
- Calorías: {minuta.kcal or 'no indica'} kcal al día. Proteína: {minuta.proteina_g_kg or 'no indica'} g por kilo.
- Región o zona cultural del atleta: {usuario.region or 'No especificada'} ({usuario.nacionalidad or 'Colombia'})
- Restricciones o preferencias: {usuario.preferencias_alimentarias or 'Ninguna'}
- Recomendaciones: {minuta.recomendaciones or 'Ninguna'}

## MENÚ DE EJEMPLO DEL PLAN (guía de estilo, no se copia igual todos los días)
{ejemplo}"""

    _REGLAS_INTERCAMBIO = """## REGLAS OBLIGATORIAS (si una comida no las cumple, se descarta)
1. Usa ÚNICAMENTE alimentos de la LISTA DE INTERCAMBIOS de abajo, identificados por su número (id). No existe ningún otro alimento: nada que no esté en la lista.
2. Cada comida debe cubrir EXACTAMENTE las porciones pedidas por grupo: la suma de porciones de los alimentos de un grupo es igual a lo pedido. Ni más ni menos, y ningún grupo que no se pida.
3. Cada alimento solo cuenta para el grupo bajo el que aparece en la lista.
4. Las porciones son múltiplos de 0.5. Una porción es la medida casera indicada (ej. "Arroz blanco = 6 cucharadas" → 2 porciones son 12 cucharadas).
5. Usa máximo 2 alimentos por grupo en una comida (3 para cereales).
6. Los alimentos "Libres" son opcionales para dar sabor o acompañar (ensalada, bebida): van con porciones 0.
7. Arma platos reales y caseros de la cocina colombiana, que tengan sentido juntos y para ese momento del día. El nombre del plato es corto (máximo 6 palabras), en español, sin inventar preparaciones raras.
8. Respeta las restricciones del atleta."""

    def proponer_menu(self, usuario, minuta, catalogo, pedidos, evitar):
        bloque_evitar = ''
        if evitar:
            bloque_evitar = f"\n## PLATOS DE LA SEMANA PASADA (no los repitas)\n{', '.join(evitar)}\n"
        prompt = f"""
Eres un nutricionista deportivo colombiano. Tu tarea es armar el menú de la semana de un atleta usando SOLO su lista de intercambios y cumpliendo exacto su minuta patrón. No eres tú quien decide las cantidades: la minuta ya las fijó.

{self._minuta_texto(usuario, minuta)}
{bloque_evitar}
{self._REGLAS_INTERCAMBIO}
9. Varía: no repitas el mismo plato en días seguidos ni el mismo alimento principal más de 3 veces en la semana en el mismo momento del día.
10. Usa el mismo aceite de cocina toda la semana (es lo que se compra); varía las otras grasas.

## COMIDAS A ARMAR (fecha, día, momento: grupo porciones)
{pedidos}

## LISTA DE INTERCAMBIOS (id: alimento = medida casera de 1 porción)
{catalogo}

## VERIFICACIÓN ANTES DE RESPONDER
Para cada comida: ¿todos los id están en la lista bajo el grupo correcto? ¿La suma por grupo es exactamente la pedida? ¿Armaste todas las comidas pedidas?

## FORMATO DE SALIDA
Responde ÚNICAMENTE con este JSON, sin markdown ni texto extra. "componentes" es una lista de [id, porciones]:
{{"comidas": [{{"fecha": "2026-10-05", "tiempo": "desayuno", "nombre": "Huevos pericos con arepa", "componentes": [[12, 3], [40, 2], [210, 1], [215, 1]]}}]}}
"""
        # Sin reintentos: si la IA se corta o falla, el menú se arma con los intercambios y no se hace esperar.
        return self._chat_json(prompt, max_tokens=24000, retries=0)

    def proponer_comida(self, usuario, minuta, tiempo, requerido, catalogo, actual, motivo):
        prompt = f"""
Eres un nutricionista deportivo colombiano. El atleta no puede hacer la comida que le tocaba y necesita otra opción para su {tiempo.lower()}, sin salirse de su minuta patrón.

{self._minuta_texto(usuario, minuta)}

## POR QUÉ LA CAMBIA
{motivo}
Comida actual: {actual or 'ninguna'}.

{self._REGLAS_INTERCAMBIO}

## PORCIONES QUE DEBE CUBRIR ESTA COMIDA
{requerido}

## LISTA DE INTERCAMBIOS (id: alimento = medida casera de 1 porción)
{catalogo}

## FORMATO DE SALIDA
Responde ÚNICAMENTE con este JSON, sin markdown ni texto extra. "componentes" es una lista de [id, porciones]:
{{"nombre": "Arroz con pollo y ensalada", "componentes": [[45, 2], [12, 2]]}}
"""
        return self._chat_json(prompt, max_tokens=1024)

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

    def generar_rutina(self, usuario, implementos, proceso):
        p = self._perfil(usuario)
        c = self._proceso(usuario, proceso)
        config = proceso.entrenamiento
        nombres = [i.implemento.nombre for i in implementos] or ['Sin implemento']
        implementos_extra = (getattr(usuario, 'implementos_adicionales', '') or '').strip()
        nivel = config.get_nivel_actividad_display()
        dias  = config.dias_entrenamiento
        duracion = config.duracion_sesion
        nacionalidad = usuario.nacionalidad or 'No especificada'
        region = usuario.region or 'No especificada'
        enfoque = getattr(config, 'enfoque_entrenamiento', 'boxeo') or 'boxeo'

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
- Objetivo: {c['objetivo']} (fase: {c['fase']})
- Enfoque de entrenamiento: {config.get_enfoque_entrenamiento_display()}
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

### Ejercicios permitidos para este enfoque ({config.get_enfoque_entrenamiento_display()})
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
- ¿El nivel y enfoque ({config.get_enfoque_entrenamiento_display()}) corresponden al perfil?

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
