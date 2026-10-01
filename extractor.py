import os
import json
import re
import time
import random
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
    chat_origen: Optional[str] = Field(default="", description="Nombre del grupo o chat de donde surge la recomendacion")

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

def deduplicate_recommendations(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Deduplica recomendaciones cruzadas (entre chats o dentro del mismo chat)
    utilizando el teléfono normalizado (últimos 8 dígitos) o tupla (nombre, rubro).
    Fusiona chats de origen, elogios/motivos y notas adicionales sin perder datos.
    """
    merged_map: Dict[str, Dict[str, Any]] = {}

    for item in items:
        nombre = str(item.get("nombre") or "").strip()
        apellido = str(item.get("apellido") or "").strip()
        rubro = str(item.get("rubro") or "").strip()
        telefono = str(item.get("telefono") or "").strip()
        barrio = str(item.get("barrio") or "Haras Santa Maria").strip()
        motivo = str(item.get("motivo") or "").strip()
        avisado = str(item.get("avisado") or "No").strip()
        notas = str(item.get("notas") or "").strip()
        chat_origen = str(item.get("chat_origen") or "").strip()

        # Extraer dígitos para clave telefónica (últimos 8 dígitos evitan prefijos de país/área dispares)
        digits = re.sub(r"\D", "", telefono)
        key_phone = digits[-8:] if len(digits) >= 8 else None

        # Claves normalizadas de texto
        norm_name = re.sub(r"[^a-z0-9]", "", nombre.lower())
        norm_rubro = re.sub(r"[^a-z0-9]", "", rubro.lower())

        if key_phone:
            match_key = f"tel_{key_phone}"
        elif norm_name and norm_rubro:
            match_key = f"nr_{norm_name}_{norm_rubro}"
        elif norm_name:
            match_key = f"n_{norm_name}"
        else:
            match_key = f"raw_{len(merged_map)}"

        if match_key not in merged_map:
            merged_map[match_key] = {
                "nombre": nombre,
                "apellido": apellido,
                "rubro": rubro,
                "telefono": telefono,
                "barrio": barrio,
                "motivo": motivo,
                "avisado": avisado,
                "notas": notas,
                "chat_origen": chat_origen,
            }
        else:
            existing = merged_map[match_key]
            # Conservar nombre o apellido más completo
            if len(nombre) > len(existing["nombre"]):
                existing["nombre"] = nombre
            if apellido and not existing["apellido"]:
                existing["apellido"] = apellido
            # Completar rubro si estaba vacío o muy genérico
            if len(rubro) > len(existing["rubro"]):
                existing["rubro"] = rubro
            # Conservar teléfono si el anterior estaba vacío
            if not existing["telefono"] and telefono:
                existing["telefono"] = telefono
            # Fusionar chats de origen sin duplicar
            existing_chats = [c.strip() for c in existing["chat_origen"].split(",") if c.strip()]
            new_chats = [c.strip() for c in chat_origen.split(",") if c.strip()]
            for nc in new_chats:
                if nc and nc not in existing_chats:
                    existing_chats.append(nc)
            existing["chat_origen"] = ", ".join(existing_chats)

            # Fusionar motivos/elogios si son diferentes
            if motivo and motivo not in existing["motivo"]:
                if existing["motivo"]:
                    existing["motivo"] += f" ; {motivo}"
                else:
                    existing["motivo"] = motivo

            # Fusionar notas
            if notas and notas not in existing["notas"]:
                if existing["notas"]:
                    existing["notas"] += f" ; {notas}"
                else:
                    existing["notas"] = notas

    return list(merged_map.values())

class WhatsAppInsightExtractor:
    def __init__(self, api_key: Optional[str] = None, model: str = "gemini-2.5-flash"):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not self.api_key:
            raise ValueError("No se encontro una API Key de Gemini. Por favor configurala en la app o en las variables de entorno.")
        self.client = genai.Client(api_key=self.api_key)
        self.model = model

    def _generate_with_retry(self, contents: str, config: types.GenerateContentConfig, max_retries: int = 3) -> Any:
        candidate_models = [self.model]
        # Cascada de modelos estables de respaldo si el principal experimenta saturación (503 / 429)
        fallbacks = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash", "gemini-3.8-flash"]
        for fb in fallbacks:
            if fb not in candidate_models:
                candidate_models.append(fb)

        last_error = None
        for model_name in candidate_models:
            for attempt in range(max_retries):
                try:
                    response = self.client.models.generate_content(
                        model=model_name,
                        contents=contents,
                        config=config,
                    )
                    return response
                except Exception as e:
                    last_error = e
                    err_msg = str(e).lower()
                    # Si es error transitorio (503 Unavailable, 429 Rate Limit, High demand)
                    if any(term in err_msg for term in ["503", "429", "unavailable", "high demand", "capacity", "temporary"]):
                        wait_sec = (attempt + 1) * 2 + random.uniform(0.5, 1.5)
                        time.sleep(wait_sec)
                    else:
                        # Error no transitorio (ej: schema no soportado), pasar al siguiente intento o fallback
                        break
        raise last_error

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
            '      "notas": "Quien lo recomendo y contexto",\n'
            '      "chat_origen": "Nombre del chat o grupo de origen (si aparece entre corchetes)"\n'
            "    }\n"
            "  ]\n"
            "}\n\n"
            f"Historial de conversacion:\n{messages_text}"
        )

        try:
            config = types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=RecommendationBatch,
            )
            response = self._generate_with_retry(prompt, config)
            data = json.loads(_clean_json_text(response.text))
            return data.get("recomendados", [])
        except Exception:
            # Fallback sin response_schema estricto para evitar restricciones de Developer API
            config = types.GenerateContentConfig(
                response_mime_type="application/json",
            )
            response = self._generate_with_retry(prompt, config)
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

        config = types.GenerateContentConfig(
            response_mime_type="application/json",
        )
        response = self._generate_with_retry(prompt, config)
        return json.loads(_clean_json_text(response.text))

    def extract_recommendations_batched(
        self,
        messages: List[Any],
        chunk_size: int = 700,
        deduplicate: bool = True,
        progress_callback: Optional[Any] = None
    ) -> List[Dict[str, Any]]:
        """
        Procesa los mensajes en lotes de tamaño `chunk_size` para sortear el límite
        de tokens de salida de los LLMs (~4k-8k tokens en JSON) y asegurar la extracción
        del 100% de los contactos recomendados sin truncamiento.
        
        Si `deduplicate=False`, devuelve cada mención por separado sin fusionar.
        """
        if not messages:
            return []

        total_msgs = len(messages)
        chunks = [messages[i:i + chunk_size] for i in range(0, total_msgs, chunk_size)]
        total_chunks = len(chunks)
        
        all_recommendations: List[Dict[str, Any]] = []

        for idx, chunk in enumerate(chunks):
            chunk_num = idx + 1
            if progress_callback:
                progress_callback(
                    chunk_num,
                    total_chunks,
                    len(all_recommendations),
                    f"Procesando lote {chunk_num} de {total_chunks} ({len(chunk)} mensajes)..."
                )

            chunk_text = "\n".join([
                m.to_formatted_str() if hasattr(m, "to_formatted_str") else str(m)
                for m in chunk
            ])

            # Detectar si el lote proviene de un chat específico para completar chat_origen si falta
            chunk_chats = set(getattr(m, "source_chat", "") for m in chunk if getattr(m, "source_chat", ""))
            default_chat = list(chunk_chats)[0] if len(chunk_chats) == 1 else ""

            try:
                batch_results = self.extract_recommendations(chunk_text)
                if batch_results:
                    for br in batch_results:
                        if not br.get("chat_origen") and default_chat:
                            br["chat_origen"] = default_chat
                    all_recommendations.extend(batch_results)
            except Exception as e:
                print(f"[Aviso] Error procesando lote {chunk_num}/{total_chunks}: {e}")

            if progress_callback:
                progress_callback(
                    chunk_num,
                    total_chunks,
                    len(all_recommendations),
                    f"Lote {chunk_num}/{total_chunks} finalizado. {len(all_recommendations)} menciones detectadas."
                )

        if deduplicate:
            return deduplicate_recommendations(all_recommendations)
        return all_recommendations

    def extract_dynamic_query_batched(
        self,
        messages: List[Any],
        user_query: str,
        chunk_size: int = 800,
        progress_callback: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Procesa una consulta universal en lotes para abarcar todo el historial
        sin exceder la ventana de tokens de salida.
        """
        if not messages:
            return {"columnas": [], "filas": []}

        total_msgs = len(messages)
        chunks = [messages[i:i + chunk_size] for i in range(0, total_msgs, chunk_size)]
        total_chunks = len(chunks)

        all_filas: List[Dict[str, Any]] = []
        unified_cols: List[str] = []

        for idx, chunk in enumerate(chunks):
            chunk_num = idx + 1
            if progress_callback:
                progress_callback(
                    chunk_num,
                    total_chunks,
                    len(all_filas),
                    f"Analizando lote {chunk_num} de {total_chunks}..."
                )

            chunk_text = "\n".join([
                m.to_formatted_str() if hasattr(m, "to_formatted_str") else str(m)
                for m in chunk
            ])

            try:
                res = self.extract_dynamic_query(chunk_text, user_query)
                cols = res.get("columnas", [])
                filas = res.get("filas", [])
                if not unified_cols and cols:
                    unified_cols = cols
                if filas:
                    all_filas.extend(filas)
            except Exception as e:
                print(f"[Aviso] Error en consulta dinámica lote {chunk_num}: {e}")

        return {
            "columnas": unified_cols,
            "filas": all_filas
        }
