import os
import json
import re
import time
import random
from typing import List, Dict, Any, Optional, Tuple
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
    text = text.strip()
    match = re.search(r'(\{[\s\S]*\}|\[[\s\S]*\])', text)
    if match:
        return match.group(1).strip()
    return text

def normalize_dynamic_result(data: Any, default_chat: str = "") -> Dict[str, Any]:
    """
    Normaliza cualquier respuesta JSON devuelta por Gemini (lista directa de objetos,
    objeto con clave 'filas', o con clave personalizada) garantizando que nunca
    falle por formato inesperado.
    """
    filas: List[Dict[str, Any]] = []
    respuesta_directa = ""
    columnas: List[str] = []

    if isinstance(data, list):
        filas = [item for item in data if isinstance(item, dict)]
    elif isinstance(data, dict):
        respuesta_directa = str(data.get("respuesta_directa") or data.get("resumen") or "").strip()
        for key in ["filas", "resultados", "datos", "registros", "items", "proveedores", "recomendaciones", "recomendados"]:
            val = data.get(key)
            if isinstance(val, list):
                filas = [item for item in val if isinstance(item, dict)]
                break

        if not filas:
            for k, val in data.items():
                if isinstance(val, list) and val and isinstance(val[0], dict):
                    filas = val
                    break

        columnas = data.get("columnas") or []

    if filas and not columnas:
        columnas = list(filas[0].keys())

    if default_chat and filas:
        for f in filas:
            if "chat" in f and not f.get("chat"):
                f["chat"] = default_chat
            elif "chat_origen" in f and not f.get("chat_origen"):
                f["chat_origen"] = default_chat
            elif not f.get("chat") and not f.get("chat_origen"):
                f["chat"] = default_chat
                f["chat_origen"] = default_chat

    return {
        "respuesta_directa": respuesta_directa,
        "columnas": columnas,
        "filas": filas
    }

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

_DISCOVERED_MODELS_CACHE: Dict[str, List[str]] = {}

def discover_flash_models(client: genai.Client, cache_key: str = "") -> List[str]:
    """
    Descubre dinámicamente los modelos Flash disponibles en la cuenta del usuario,
    ordenados priorizando los más adecuados para procesamiento ágil de chats.
    """
    if cache_key and cache_key in _DISCOVERED_MODELS_CACHE:
        return _DISCOVERED_MODELS_CACHE[cache_key]

    curated_priority = [
        "gemini-3.5-flash-lite",
        "gemini-3.5-flash",
        "gemini-3.8-flash",
        "gemini-3.7-flash",
        "gemini-3.6-flash",
        "gemini-3-flash-preview",
    ]
    discovered = []
    try:
        pager = client.models.list()
        for m in pager:
            name = m.name.replace("models/", "") if hasattr(m, "name") and m.name else ""
            actions = getattr(m, "supported_actions", []) or []
            if actions and "generateContent" not in actions:
                continue
            if "flash" in name.lower() and not any(x in name.lower() for x in ["image", "tts", "audio", "embed"]):
                discovered.append(name)
    except Exception as e:
        print(f"[Aviso] No se pudieron listar modelos de Gemini: {e}")

    ordered = []
    for cp in curated_priority:
        if cp in discovered or not discovered:
            if cp not in ordered:
                ordered.append(cp)
    for d in discovered:
        if d not in ordered:
            ordered.append(d)

    result = ordered or curated_priority
    if cache_key:
        _DISCOVERED_MODELS_CACHE[cache_key] = result
    return result

class WhatsAppInsightExtractor:
    def __init__(self, api_key: Optional[str] = None, model: str = "gemini-3.5-flash-lite"):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not self.api_key:
            raise ValueError("No se encontro una API Key de Gemini. Por favor configurala en la app o en las variables de entorno.")
        self.client = genai.Client(
            api_key=self.api_key,
            http_options=types.HttpOptions(timeout=30000)
        )
        cache_id = self.api_key[:8] if self.api_key else ""
        self.available_models = discover_flash_models(self.client, cache_key=cache_id)
        self.model = model or (self.available_models[0] if self.available_models else "gemini-3.5-flash-lite")
        self.last_models_used: List[str] = []
        self.fallback_occurred: bool = False

    def _generate_with_retry(self, contents: str, config: types.GenerateContentConfig, max_retries: int = 2) -> Tuple[Any, str]:
        # Jerarquía ordenada: primero el modelo seleccionado/adecuado, luego los respaldos
        active_models = self.available_models or [
            "gemini-3.5-flash-lite",
            "gemini-3.5-flash",
            "gemini-3.8-flash",
            "gemini-3.7-flash",
            "gemini-3.6-flash",
        ]
        candidate_models = []
        if self.model:
            candidate_models.append(self.model)
        for m in active_models:
            if m not in candidate_models:
                candidate_models.append(m)

        model_errors = {}
        first_candidate = candidate_models[0]

        for model_name in candidate_models:
            for attempt in range(max_retries):
                try:
                    call_config = config.model_copy() if hasattr(config, "model_copy") else config
                    # Configurar thinking: 'minimal' para 3.5 elimina la latencia y responde en ~1.5s
                    if any(k in model_name for k in ["3.5-flash-lite", "3.1-flash-lite", "3.5-flash", "3.6-flash"]):
                        try:
                            call_config.thinking_config = types.ThinkingConfig(thinking_level="minimal")
                        except Exception:
                            call_config.thinking_config = None
                    elif any(k in model_name for k in ["3.8", "3.7", "gemini-3"]):
                        try:
                            call_config.thinking_config = types.ThinkingConfig(thinking_level="low")
                        except Exception:
                            call_config.thinking_config = None
                    elif "2.5" in model_name:
                        try:
                            call_config.thinking_config = types.ThinkingConfig(thinking_budget=0)
                        except Exception:
                            call_config.thinking_config = None
                    else:
                        call_config.thinking_config = None

                    response = self.client.models.generate_content(
                        model=model_name,
                        contents=contents,
                        config=call_config,
                    )
                    if model_name != first_candidate:
                        self.fallback_occurred = True
                    return response, model_name
                except Exception as e:
                    err_msg = str(e)
                    # Reintento de emergencia sin thinking si el modelo no soporta el parámetro
                    if call_config.thinking_config is not None and any(t in err_msg.lower() for t in ["thinking", "invalid_argument", "400"]):
                        try:
                            call_config.thinking_config = None
                            response = self.client.models.generate_content(
                                model=model_name,
                                contents=contents,
                                config=call_config,
                            )
                            if model_name != first_candidate:
                                self.fallback_occurred = True
                            return response, model_name
                        except Exception as inner_e:
                            err_msg = str(inner_e)

                    model_errors[f"{model_name}_intento_{attempt+1}"] = err_msg
                    err_lower = err_msg.lower()
                    if any(term in err_lower for term in ["503", "429", "unavailable", "high demand", "capacity", "temporary", "timeout", "deadline"]):
                        if attempt < max_retries - 1:
                            wait_sec = 0.8 + random.uniform(0.1, 0.4)
                            time.sleep(wait_sec)
                        else:
                            # Ante saturación/demanda, descender de inmediato al siguiente modelo
                            break
                    else:
                        # Si es error no transitorio (ej: modelo no habilitado en cuenta o 404), pasar directo al siguiente modelo
                        break

        summary = "; ".join([f"{k}: {v[:120]}" for k, v in model_errors.items()])
        raise RuntimeError(f"Error procesando con la IA ({summary})")

    def extract_recommendations(self, messages_text: str) -> Tuple[List[Dict[str, Any]], str]:
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
            response, model_used = self._generate_with_retry(prompt, config)
            data = json.loads(_clean_json_text(response.text))
            return data.get("recomendados", []), model_used
        except Exception:
            # Fallback sin response_schema estricto para evitar restricciones de Developer API
            config = types.GenerateContentConfig(
                response_mime_type="application/json",
            )
            response, model_used = self._generate_with_retry(prompt, config)
            data = json.loads(_clean_json_text(response.text))
            return data.get("recomendados", []), model_used

    def extract_dynamic_query(self, messages_text: str, user_query: str) -> Tuple[Any, str]:
        prompt = (
            "Eres un analista experto en datos y mensajes de WhatsApp.\n"
            "Tu tarea es analizar minuciosamente el historial de mensajes y cumplir rigurosamente con la solicitud del usuario.\n\n"
            f"SOLICITUD Y CRITERIOS DEL USUARIO:\n{user_query}\n\n"
            "INSTRUCCIONES:\n"
            "1. Cumple de forma estricta con TODOS los filtros, condiciones, oficios, exclusiones y nombres de columnas pedidos por el usuario.\n"
            "2. Si el usuario indicó nombres exactos de columnas (ej: proveedor_nombre, rubro, fecha, recomienda, chat, etc.), "
            "UTILIZA EXACTAMENTE esos nombres como claves de cada objeto en la lista 'filas'.\n"
            "3. En los mensajes verás encabezados de la forma '[NombreDelChat | 29/9/2026, 14:49] Remitente: Texto'. Si te piden la columna 'chat' o grupo, usa 'NombreDelChat'.\n"
            "4. En 'respuesta_directa', redacta un resumen claro en español de lo que encontraste (quiénes, qué dijeron, acuerdos o recomendaciones).\n"
            "5. En 'filas', agrega todas las ocurrencias o filas encontradas que cumplan con la solicitud del usuario.\n"
            "6. Si no hay ocurrencias que cumplan los criterios en estos mensajes, devuelve 'filas': [] y en 'respuesta_directa' aclara brevemente que no hubo menciones.\n\n"
            "Responde en formato JSON con la siguiente estructura (o directamente un array de objetos JSON con las columnas solicitadas):\n"
            "{\n"
            '  "respuesta_directa": "Resumen de lo encontrado...",\n'
            '  "columnas": ["col1", "col2", ...],\n'
            '  "filas": [\n'
            '    {\n'
            '      "col1": "valor...",\n'
            '      "col2": "valor..."\n'
            '    }\n'
            '  ]\n'
            "}\n\n"
            f"HISTORIAL DE MENSAJES A ANALIZAR:\n{messages_text}"
        )

        config = types.GenerateContentConfig(
            response_mime_type="application/json",
        )
        response, model_used = self._generate_with_retry(prompt, config)
        return json.loads(_clean_json_text(response.text)), model_used

    def extract_recommendations_batched(
        self,
        messages: List[Any],
        chunk_size: int = 200,
        deduplicate: bool = True,
        progress_callback: Optional[Any] = None
    ) -> List[Dict[str, Any]]:
        """
        Procesa los mensajes en lotes ágiles de tamaño `chunk_size` (200 por defecto) para
        garantizar respuestas rápidas (~2-4s por lote) sin saturar límites de tokens de salida.
        """
        if not messages:
            return []

        total_msgs = len(messages)
        chunks = [messages[i:i + chunk_size] for i in range(0, total_msgs, chunk_size)]
        total_chunks = len(chunks)
        
        all_recommendations: List[Dict[str, Any]] = []
        models_used: List[str] = []

        for idx, chunk in enumerate(chunks):
            chunk_num = idx + 1
            pct_start = int((idx / total_chunks) * 100)
            curr_model = models_used[-1] if models_used else self.model
            if progress_callback:
                progress_callback(
                    idx,
                    total_chunks,
                    pct_start,
                    len(all_recommendations),
                    f"Analizando lote {chunk_num} de {total_chunks} ({len(chunk)} mensajes)...",
                    curr_model
                )

            chunk_text = "\n".join([
                m.to_formatted_str() if hasattr(m, "to_formatted_str") else str(m)
                for m in chunk
            ])

            # Detectar si el lote proviene de un chat específico para completar chat_origen si falta
            chunk_chats = set(getattr(m, "source_chat", "") for m in chunk if getattr(m, "source_chat", ""))
            default_chat = list(chunk_chats)[0] if len(chunk_chats) == 1 else ""

            try:
                batch_results, used_model = self.extract_recommendations(chunk_text)
                if used_model and used_model not in models_used:
                    models_used.append(used_model)
                if batch_results:
                    for br in batch_results:
                        if not br.get("chat_origen") and default_chat:
                            br["chat_origen"] = default_chat
                    all_recommendations.extend(batch_results)
            except Exception as e:
                print(f"[Aviso] Error procesando lote {chunk_num}/{total_chunks}: {e}")

            pct_end = int((chunk_num / total_chunks) * 100)
            latest_model = models_used[-1] if models_used else self.model
            if progress_callback:
                progress_callback(
                    chunk_num,
                    total_chunks,
                    pct_end,
                    len(all_recommendations),
                    f"Lote {chunk_num} de {total_chunks} completado.",
                    latest_model
                )

        self.last_models_used = models_used
        if deduplicate:
            return deduplicate_recommendations(all_recommendations)
        return all_recommendations

    def extract_dynamic_query_batched(
        self,
        messages: List[Any],
        user_query: str,
        chunk_size: int = 200,
        progress_callback: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Procesa una consulta universal en lotes ágiles de 200 mensajes para
        garantizar velocidad instantánea, respuesta continua y sin timeouts.
        """
        if not messages:
            return {
                "respuesta_directa": "No hay mensajes cargados para analizar.",
                "columnas": [],
                "filas": [],
                "modelos_usados": []
            }

        total_msgs = len(messages)
        chunks = [messages[i:i + chunk_size] for i in range(0, total_msgs, chunk_size)]
        total_chunks = len(chunks)

        all_filas: List[Dict[str, Any]] = []
        unified_cols: List[str] = []
        respuestas_parciales: List[str] = []
        batch_errors: List[str] = []
        models_used: List[str] = []

        for idx, chunk in enumerate(chunks):
            chunk_num = idx + 1
            pct_start = int((idx / total_chunks) * 100)
            curr_model = models_used[-1] if models_used else self.model
            if progress_callback:
                progress_callback(
                    idx,
                    total_chunks,
                    pct_start,
                    len(all_filas),
                    f"Analizando lote {chunk_num} de {total_chunks} ({len(chunk)} mensajes)...",
                    curr_model
                )

            chunk_text = "\n".join([
                m.to_formatted_str() if hasattr(m, "to_formatted_str") else str(m)
                for m in chunk
            ])

            chunk_chats = set(getattr(m, "source_chat", "") for m in chunk if getattr(m, "source_chat", ""))
            default_chat = list(chunk_chats)[0] if len(chunk_chats) == 1 else ""

            try:
                raw_res, used_model = self.extract_dynamic_query(chunk_text, user_query)
                if used_model and used_model not in models_used:
                    models_used.append(used_model)
                norm = normalize_dynamic_result(raw_res, default_chat=default_chat)
                direct = str(norm.get("respuesta_directa", "")).strip()
                if direct and not any(term in direct.lower() for term in ["no se encontró", "no hay información", "no encontré", "no se encontraron", "no hubo menciones"]):
                    respuestas_parciales.append(direct)

                cols = norm.get("columnas", [])
                filas = norm.get("filas", [])
                if not unified_cols and cols:
                    unified_cols = cols
                if filas:
                    all_filas.extend(filas)
            except Exception as e:
                err_text = str(e)
                batch_errors.append(f"Lote {chunk_num}: {err_text}")
                print(f"[Aviso] Error en consulta dinámica lote {chunk_num}: {e}")

            pct_end = int((chunk_num / total_chunks) * 100)
            latest_model = models_used[-1] if models_used else self.model
            if progress_callback:
                progress_callback(
                    chunk_num,
                    total_chunks,
                    pct_end,
                    len(all_filas),
                    f"Lote {chunk_num} de {total_chunks} completado.",
                    latest_model
                )

        self.last_models_used = models_used

        # Sintetizar respuesta directa conservando datos incluso si un lote aislado falló
        if all_filas:
            prefix = ""
            if batch_errors:
                prefix = f"⚠️ *Nota: Hubo una interrupción en {len(batch_errors)} lote(s), pero se extrajeron los registros del resto de los mensajes exitosamente.*\n\n"
            if respuestas_parciales:
                respuesta_final = prefix + "\n\n".join(respuestas_parciales)
            else:
                respuesta_final = prefix + f"Se encontraron {len(all_filas)} registros relevantes en las conversaciones analizadas."
        elif batch_errors:
            respuesta_final = f"Ocurrió un error al procesar los mensajes con la IA: {batch_errors[0]}"
        elif respuestas_parciales:
            respuesta_final = "\n\n".join(respuestas_parciales)
        else:
            respuesta_final = "No se encontraron menciones ni datos relevantes que cumplan con todos los filtros y condiciones solicitadas en los mensajes analizados."

        return {
            "respuesta_directa": respuesta_final,
            "columnas": unified_cols,
            "filas": all_filas,
            "modelos_usados": models_used
        }
