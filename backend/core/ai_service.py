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
            url, json=payload, headers=headers, timeout=120)
        response.raise_for_status()
        data = response.json()

        if self.provider == 'ollama':
            return data.get('response', '')
        return data['choices'][0]['message']['content']

    def _parse_json(self, text):
        """Limpia y parsea el JSON, tolerando markdown y texto extra."""
        text = text.strip()
        # Quitar bloques markdown: ```json ... ``` o ``` ... ```
        if text.startswith('```'):
            text = text.split('```')[1]
            if text.startswith('json'):
                text = text[4:]
            text = text.strip()
        # Intentar parsear directamente
        return json.loads(text)

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
        prompt = f"""
Eres un nutricionista deportivo especializado en atletas de artes marciales y boxeo.
Genera un plan nutricional semanal en formato JSON para este atleta:

PERFIL:
- Sexo: {p['sexo']}
- Edad: {p['edad']}
- Estatura: {p['estatura']}
- Peso actual: {objetivo.peso_inicial} kg
- Peso objetivo: {objetivo.peso_objetivo if objetivo.peso_objetivo else 'No especificado'} kg
- Objetivo: {objetivo.get_objetivo_display()}
- Nacionalidad: {nacionalidad}
- Región / zona: {region}
- Restricciones alimentarias: {pref}
- Días de entrenamiento: {objetivo.dias_entrenamiento} por semana

INSTRUCCIONES:
- Usa ÚNICAMENTE platos y alimentos típicos de la región "{region}" ({nacionalidad}). Prioriza recetas caseras de esa zona, ingredientes que se consiguen fácil en plazas de mercado o tiendas locales.
- Si la región es conocida (ej: paisa, costeño, valluno, llanero, bogotano) usa sus platos característicos: frijoles, sancocho, arepas, bandeja, patacones, etc. Sé específico y fiel a la cultura culinaria local.
- Adapta calorías al objetivo (déficit=bajar, superávit=músculo, mantenimiento=mantener).
- Varía las comidas cada día, no repitas el mismo menú.
- Incluye porciones prácticas (ej: "2 huevos + 1 taza de arroz + ensalada de tomate").
- Días de entrenamiento: más carbohidratos complejos antes del entreno. Snacks: proteicos y simples.
- Respeta estrictamente las restricciones alimentarias.
- Descripciones CORTAS y directas, máximo 20 palabras por campo. No uses palabras en inglés.

El JSON debe tener exactamente esta estructura, sin texto adicional:
{{
  "nombre": "Plan nombre descriptivo",
  "dias": [
    {{
      "dia_semana": 1,
      "desayuno": "descripción detallada con porciones",
      "almuerzo": "descripción detallada con porciones",
      "cena": "descripción detallada con porciones",
      "snacks": "descripción de 1-2 snacks con porciones",
      "calorias_aprox": 2000
    }}
  ]
}}
Incluye los 7 días (dia_semana del 1=lunes al 7=domingo). Responde solo con el JSON, sin markdown ni texto extra.
"""
        return self._parse_json(self._chat(prompt))

    def generar_lista_mercado(self, plan):
        comidas = []
        for dia in plan.dias.all():
            comidas.append(f'{dia.get_dia_semana_display()}: {dia.desayuno} | {dia.almuerzo} | {dia.cena} | {dia.snacks}')
        texto_plan = '\n'.join(comidas)

        prompt = f"""
Analiza este plan alimentario semanal y genera una lista de mercado consolidada para 1 persona, 7 días.
Extrae todos los ingredientes, agrupa duplicados y estima cantidades totales.

PLAN:
{texto_plan}

Categorías permitidas para "categoria" (usa exactamente estos valores):
proteinas, verduras, frutas, lacteos, granos, condimentos

El JSON debe tener exactamente esta estructura, sin texto adicional:
{{
  "categorias": [
    {{
      "categoria": "proteinas",
      "items": [
        {{"nombre": "Huevos", "cantidad": "18 unidades"}},
        {{"nombre": "Pechuga de pollo", "cantidad": "1 kg"}}
      ]
    }}
  ]
}}
Solo incluye categorías que tengan items. Responde únicamente con el JSON, sin markdown.
"""
        return self._parse_json(self._chat(prompt))

    def generar_rutina(self, usuario, implementos, objetivo):
        p = self._perfil(usuario)
        nombres = [i.implemento.nombre for i in implementos] or ['Sin implemento']
        nivel = objetivo.get_nivel_actividad_display()
        dias  = objetivo.dias_entrenamiento
        duracion = objetivo.duracion_sesion
        prompt = f"""
Eres un entrenador de boxeo y acondicionamiento físico profesional.
Genera una rutina de boxeo semanal completa en formato JSON para este atleta:

PERFIL:
- Sexo: {p['sexo']}
- Edad: {p['edad']}
- Estatura: {p['estatura']}
- Objetivo: {objetivo.get_objetivo_display()}
- Nivel de actividad: {nivel}
- Días de entrenamiento por semana: {dias}
- Duración deseada por sesión: {duracion} minutos
- Implementos disponibles: {', '.join(nombres)}

INSTRUCCIONES OBLIGATORIAS:
- Genera EXACTAMENTE {dias} días de entrenamiento (no incluyas días de descanso).
- Cada sesión: entre 6 y 8 ejercicios. Duración total aproximada: {duracion} min.
- Nivel {nivel}: {'series 2-3, básico' if nivel == 'Principiante' else 'series 3-4, variado' if nivel == 'Intermedio' else 'series 4-5, circuitos'}.
- Incluye calentamiento y vuelta a la calma.
- Usa ejercicios reales de boxeo: jab, cross, uppercut, hook, combinaciones, esquivas, footwork, sombra, saco.
- Ejercicios de tiempo → duracion_segundos (int), repeticiones null. Ejercicios de fuerza/técnica → series + repeticiones, duracion_segundos null.
- Descripciones CORTAS (máximo 15 palabras). Varía ejercicios entre días.

El JSON debe tener exactamente esta estructura, sin texto adicional:
{{
  "nombre": "Nombre descriptivo de la rutina",
  "descripcion": "Descripción breve del programa",
  "dias": [
    {{
      "dia_semana": 1,
      "ejercicios": [
        {{
          "nombre": "Nombre del ejercicio",
          "descripcion": "Cómo ejecutarlo correctamente",
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
Responde solo con el JSON, sin markdown ni texto extra.
"""
        return self._parse_json(self._chat(prompt))
