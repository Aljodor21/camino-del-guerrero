import json

import requests
from django.conf import settings


class AIService:
    def __init__(self):
        self.provider = settings.AI_PROVIDER
        self.base_url = settings.AI_BASE_URL
        self.model = settings.AI_MODEL
        self.api_key = settings.AI_API_KEY

    def _chat(self, prompt):
        if self.provider == 'ollama':
            url = f'{self.base_url}/api/generate'
            payload = {'model': self.model, 'prompt': prompt, 'stream': False}
            headers = {}
        else:
            url = f'{self.base_url}/v1/chat/completions'
            payload = {
                'model': self.model,
                'messages': [{'role': 'user', 'content': prompt}],
            }
            headers = {'Authorization': f'Bearer {self.api_key}'}

        response = requests.post(url, json=payload, headers=headers, timeout=120)
        response.raise_for_status()
        data = response.json()

        if self.provider == 'ollama':
            return data.get('response', '')
        return data['choices'][0]['message']['content']

    def generar_plan_nutricional(self, usuario, objetivo):
        prompt = f"""
Genera un plan nutricional semanal en formato JSON para una persona con las siguientes características:
- Objetivo: {objetivo.get_objetivo_display()}
- Peso actual: {objetivo.peso_inicial} kg
- Peso objetivo: {objetivo.peso_objetivo} kg

El JSON debe tener exactamente esta estructura, sin texto adicional:
{{
  "nombre": "Plan nombre",
  "dias": [
    {{
      "dia_semana": 1,
      "desayuno": "descripción",
      "almuerzo": "descripción",
      "cena": "descripción",
      "snacks": "descripción",
      "calorias_aprox": 2000
    }}
  ]
}}
Incluye los 7 días (dia_semana del 1 al 7). Responde solo con el JSON, sin markdown.
"""
        respuesta = self._chat(prompt)
        return json.loads(respuesta.strip())

    def generar_rutina(self, usuario, implementos):
        nombres_implementos = [i.implemento.nombre for i in implementos] or ['Sin implemento']
        prompt = f"""
Genera una rutina de entrenamiento de boxeo semanal en formato JSON para un usuario con estos implementos disponibles: {', '.join(nombres_implementos)}.

El JSON debe tener exactamente esta estructura, sin texto adicional:
{{
  "nombre": "Nombre de la rutina",
  "descripcion": "Descripción breve",
  "dias": [
    {{
      "dia_semana": 1,
      "ejercicios": [
        {{
          "nombre": "Nombre ejercicio",
          "descripcion": "Descripción del ejercicio",
          "requiere_implemento": true,
          "series": 3,
          "repeticiones": 10,
          "duracion_segundos": null,
          "orden": 1
        }}
      ]
    }}
  ]
}}
Incluye entre 3 y 5 días de entrenamiento. Responde solo con el JSON, sin markdown.
"""
        respuesta = self._chat(prompt)
        return json.loads(respuesta.strip())
