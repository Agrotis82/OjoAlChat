import os
import json
import re
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from google import genai
from google.genai import types

class ProviderRecommendation(BaseModel):
    nombre: str = Field(description="Nombre de pila de la persona o nombre del negocio/proveedor")
    apellido: Optional[str] = Field(default="", description="Apellido si se menciona o infiere, sino dejar vacio")
    rubro: str = Field(description="Oficio, rubro o servicio (ej: Plomero, Electricista, Techista, Herrero, Piletero, Pediatra, etc.)")
    telefono: str = Field(description="Numero de telefono, celular o via de contacto compartida")
    barrio: Optional[str] = Field(default="Haras Santa Maria", description="Barrio, zona, lote o localidad mencionada")
    motivo: Optional[str] = Field(default="", description="Palabras de recomendacion, calidad o motivo (ej: muy cumplidor, honesto, recomendable)")
    avisado: Optional[str] = Field(default="No", description="Por defecto 'No'")
    notas: Optional[str] = Field(default="", description="Detalles adicionales: quien lo recomendo, trabajo especifico o contexto")

class RecommendationBatch(BaseModel):
    recomendados: List[ProviderRecommendation]

def _clean_json_text(text: str) -> str:
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()

class WhatsAppInsightExtractor:
    def __init__(self, api_key: Optional[str] = None, model: str = "gemini-3.8-flash"):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not self.api_key:
            raise ValueError("No se encontro una API Key de Gemini. Por favor configurala en la app o en las variables de entorno.")
        self.client = genai.Client(api_key=self.api_key)
        self.model = model

    def extract_recommendations(self, messages_text: str) -> List[Dict[str, Any]]:
        prompt = (
            "Eres un analista experto en extraer recomendaciones de servicios y personas a partir de chats de WhatsApp.\n"
            "Tu objetivo es encontrar TODAS las personas, profesionales, tecnicos o comercios recomendados en la conversacion.\n"
            "Presta especial atencion a pedidos de recomendacion y sus respuestas, y contactos compartidos.\n\n"
            "Debes responder en formato JSON con la siguiente estructura:\n"
            "{\n"
            '  "recomendados": [\n'
            '    {\n'
            '      "nombre": "Nombre de pila o comercio",\n'
            '      "apellido": "Apellido si aparece",\n'
            '      "rubro": "Profesion estandarizada (ej: Plomero, Electricista, etc.)",\n'
            '      "telefono": "Numero de telefono o contacto",\n'
            '      "barrio": "Barrio deducido o Haras Santa Maria",\n'
            '      "motivo": "Elogio o motivo (ej: muy cumplidor, honesto)",\n'
            '      "avisado": "No",\n'
            '      "notas": "Quien lo recomendo y contexto"\n'
            "    }\n"
            "  ]\n"
            "}\n\n"
            f"Historial de conversacion:\n{messages_text}"
        )

        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=RecommendationBatch,
                ),
            )
            data = json.loads(_clean_json_text(response.text))
            return data.get("recomendados", [])
        except Exception:
            # Fallback sin response_schema estricto para evitar restricciones de Developer API
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                ),
            )
            data = json.loads(_clean_json_text(response.text))
            return data.get("recomendados", [])

    def extract_dynamic_query(self, messages_text: str, user_query: str) -> Dict[str, Any]:
        prompt = (
            "Eres un asistente analista de datos avanzado para chats grupales de WhatsApp.\n"
            f"El usuario necesita recopilar la siguiente informacion especifica: \"{user_query}\".\n\n"
            "Instrucciones:\n"
            "1. Determina un conjunto de 4 a 7 nombres de columnas claras, elegantes y en español que mejor estructuren los datos solicitados.\n"
            "2. Analiza minuciosamente los mensajes del chat y extrae todas las ocurrencias que respondan a la consulta.\n"
            "3. Para cada ocurrencia, llena los valores correspondientes a esas columnas.\n"
            "4. Incluye siempre una columna adicional llamada 'cita_o_fuente' con la fecha o fragmento del mensaje para verificar el dato.\n"
            "5. Si no hay informacion relevante sobre la consulta, devuelve filas como una lista vacia.\n\n"
            "Debes responder UNICAMENTE con un objeto JSON con la siguiente estructura exacta:\n"
            "{\n"
            '  "columnas": ["Columna1", "Columna2", "Columna3", "cita_o_fuente"],\n'
            '  "filas": [\n'
            '    {\n'
            '      "Columna1": "valor...",\n'
            '      "Columna2": "valor...",\n'
            '      "Columna3": "valor...",\n'
            '      "cita_o_fuente": "fecha o mensaje..."\n'
            '    }\n'
            '  ]\n'
            "}\n\n"
            f"Historial de mensajes:\n{messages_text}"
        )

        # En Gemini Developer API, para esquemas libres/dinamicos se usa response_mime_type sin response_schema
        # para evitar el error 'additionalProperties is only supported in Gemini Enterprise'
        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
            ),
        )
        return json.loads(_clean_json_text(response.text))
