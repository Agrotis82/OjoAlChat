import os
import json
import re
import time
import random
from typing import List, Dict, Any, Optional, Tuple
from pydantic import BaseModel, Field
from google import genai
from google.genai import types

from proveedores_ia import crear_cliente

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

def _safe_json_loads(text: str) -> Any:
    cleaned = _clean_json_text(text)
    if not cleaned:
        return {}
    try:
        return json.loads(cleaned)
    except Exception:
        # 1. Remover trailing commas en listas y objetos
        fixed = re.sub(r',\s*([\]}])', r'\1', cleaned)
        try:
            return json.loads(fixed)
        except Exception:
            pass
        # 2. Buscar primer bloque JSON balanceado
        m = re.search(r'(\{[\s\S]*\}|\[[\s\S]*\])', cleaned)
        if m:
            cand = re.sub(r',\s*([\]}])', r'\1', m.group(1))
            try:
                return json.loads(cand)
            except Exception:
                pass
        # 3. Reparar cierre truncado si hay un array de filas
        if "[" in cleaned:
            last_brace = cleaned.rfind("}")
            if last_brace != -1:
                cand = cleaned[:last_brace + 1] + "\n]}"
                fixed_c = re.sub(r',\s*([\]}])', r'\1', cand)
                try:
                    return json.loads(fixed_c)
                except Exception:
                    pass
        raise

def build_rule_based_summary(user_query: str, all_filas: List[Dict[str, Any]], partial_summaries: List[str]) -> str:
    """
    Construye una síntesis consolidada, estructurada y limpia sin duplicaciones
    cuando hay múltiples lotes de resultados.
    """
    if not all_filas and not partial_summaries:
        return "No se encontraron registros ni menciones que coincidan con la búsqueda solicitada."

    if not all_filas and partial_summaries:
        unique_points = []
        for s in partial_summaries:
            cleaned = s.strip()
            cleaned = re.sub(r'^(?:Se encontraron|Se extrajeron|Se analizaron los mensajes|Se identificaron|En el chat)\s*[^:]*:\s*', '', cleaned, flags=re.I)
            if cleaned and cleaned not in unique_points:
                unique_points.append(cleaned)
        if unique_points:
            lines = ["### 📋 Conclusiones Consolidadas de la Búsqueda:", ""]
            for p in unique_points[:10]:
                lines.append(f"- {p}")
            return "\n".join(lines)
        return partial_summaries[0]

    sample = all_filas[0]
    rubro_col = None
    for k in sample.keys():
        if any(term in k.lower() for term in ["rubro", "oficio", "servicio", "categoria", "tipo"]):
            rubro_col = k
            break

    nombre_col = None
    for k in sample.keys():
        if any(term in k.lower() for term in ["nombre", "proveedor", "persona", "contacto"]):
            nombre_col = k
            break

    total = len(all_filas)
    lines = [
        f"Se identificaron **{total} registros** en total a lo largo de las conversaciones analizadas.",
        ""
    ]

    if rubro_col:
        rubros_map: Dict[str, List[str]] = {}
        for r in all_filas:
            rb = str(r.get(rubro_col) or "Otros").strip()
            if not rb:
                rb = "Otros"
            nm = str(r.get(nombre_col) or "").strip() if nombre_col else ""
            if rb not in rubros_map:
                rubros_map[rb] = []
            if nm and nm not in rubros_map[rb]:
                rubros_map[rb].append(nm)

        lines.append("### 📌 Resumen por Rubro y Servicios Detectados:")
        sorted_rubros = sorted(rubros_map.items(), key=lambda x: len(x[1]), reverse=True)
        for rb, names in sorted_rubros:
            if names:
                ejemplos = ", ".join(names[:4])
                extra = f" (y otros)" if len(names) > 4 else ""
                lines.append(f"- **{rb}** ({len(names)} menciones): {ejemplos}{extra}")
            else:
                lines.append(f"- **{rb}**")
        lines.append("")
        lines.append("*(Consulta la tabla interactiva a continuación para ver todos los contactos, teléfonos, fechas y citas textuales).*")
    else:
        if nombre_col:
            unique_names = list(dict.fromkeys([str(r.get(nombre_col)).strip() for r in all_filas if str(r.get(nombre_col)).strip()]))
            if unique_names:
                lines.append("### 📌 Principales Registros Detectados:")
                ejemplos = ", ".join(unique_names[:10])
                extra = f" (y {len(unique_names) - 10} más)" if len(unique_names) > 10 else ""
                lines.append(f"- **Menciones destacadas:** {ejemplos}{extra}")
                lines.append("")
                lines.append("*(Consulta la tabla interactiva a continuación para explorar los detalles).*")

    return "\n".join(lines)

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

REGLA_TELEFONOS = (
    "REGLA DE TELÉFONOS (obligatoria): los contactos compartidos aparecen como "
    "'[CONTACTO: Nombre | teléfono]'. El teléfono de un proveedor sale SOLO de esas líneas "
    "o de un número escrito dentro del texto del mensaje. NUNCA uses el número que aparece como "
    "remitente, antes de los dos puntos del encabezado: es el vecino que escribe, no el proveedor. "
    "Si no hay teléfono del proveedor, dejalo vacío.\n"
)


MENSAJES_DE_CONTEXTO = 25

REGLA_REMITENTE = (
    "Quien escribe en el chat (el remitente, antes de los dos puntos) es un vecino, no un proveedor, salvo que "
    "el mensaje diga que ofrece ese servicio. No lo pongas como proveedor por compartir un contacto o recomendar a alguien.\n"
)

REGLA_CONTEXTO = (
    "Si el historial empieza con una sección 'CONTEXTO', son los mensajes anteriores al tramo: usala solo "
    "para entender a qué pregunta responde un mensaje. Extraé filas SOLO de la sección 'MENSAJES A ANALIZAR'.\n"
)


def _formatear(m: Any) -> str:
    return m.to_formatted_str() if hasattr(m, "to_formatted_str") else str(m)


def armar_texto_lote(mensajes: List[Any], inicio: int, lote: List[Any]) -> str:
    """
    El tramo a analizar, precedido por los mensajes anteriores como contexto. Sin eso, una respuesta
    ("te paso el de Martín") que cae al principio de un tramo pierde la pregunta que la explica.
    """
    previos = mensajes[max(0, inicio - MENSAJES_DE_CONTEXTO):inicio]
    texto = "\n".join(_formatear(m) for m in lote)
    if not previos:
        return texto
    contexto = "\n".join(_formatear(m) for m in previos)
    return f"### CONTEXTO (no extraer filas de acá)\n{contexto}\n\n### MENSAJES A ANALIZAR\n{texto}"


def _cola_digitos(valor: Any) -> str:
    """Últimos 8 dígitos de un teléfono, para comparar sin importar el formato."""
    digitos = re.sub(r"\D", "", str(valor or ""))
    return digitos[-8:] if len(digitos) >= 8 else ""


def telefonos_de_remitentes(mensajes: List[Any]) -> set:
    """Los teléfonos de quienes escriben en el lote (cuando WhatsApp muestra el número y no un nombre)."""
    return {cola for cola in (_cola_digitos(getattr(m, "sender", "")) for m in mensajes) if cola}


def descartar_telefonos_de_remitentes(filas: List[Dict[str, Any]], remitentes: set) -> int:
    """
    Vacía el teléfono de una fila cuando es el de quien escribió el mensaje: la IA a veces
    lo toma como si fuera del proveedor. Devuelve cuántos vació.
    """
    descartados = 0
    for fila in filas:
        for clave in list(fila.keys()):
            if "tel" not in clave.lower():
                continue
            if _cola_digitos(fila.get(clave)) in remitentes:
                fila[clave] = ""
                descartados += 1
                if "notas" in fila:
                    aviso = "teléfono descartado: era de quien escribió"
                    fila["notas"] = f"{fila['notas']} ; {aviso}" if fila.get("notas") else aviso
    return descartados


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
    def __init__(self, api_key: Optional[str] = None, model: str = "gemini-3.5-flash-lite",
                 provider: str = "gemini", base_url: Optional[str] = None):
        # provider: "gemini", "anthropic", "openai" o "compatible" (ver proveedores_ia.py)
        self.provider = provider
        self.llm = None
        if provider == "gemini":
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
        else:
            self.api_key = api_key
            self.llm = crear_cliente(provider, api_key, model, base_url)
            self.model = self.llm.modelo
            self.available_models = [self.model]
        self.last_models_used: List[str] = []
        self.fallback_occurred: bool = False
        # Teléfonos que la IA puso como del proveedor pero eran de quien escribió (ver descartar_telefonos_de_remitentes).
        self.telefonos_descartados: int = 0

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

    def _pedir(self, prompt: str, json: bool = True, schema: Any = None,
               temperatura: Optional[float] = None) -> Tuple[str, str]:
        """Manda el pedido al proveedor elegido y devuelve (texto, modelo_usado)."""
        if self.llm is not None:
            return self.llm.generar(prompt, json=json, temperatura=temperatura)
        opciones: Dict[str, Any] = {}
        if json:
            opciones["response_mime_type"] = "application/json"
        if schema is not None:
            opciones["response_schema"] = schema
        if temperatura is not None:
            opciones["temperature"] = temperatura
        response, model_used = self._generate_with_retry(prompt, types.GenerateContentConfig(**opciones))
        return response.text, model_used

    def extract_recommendations(self, messages_text: str) -> Tuple[List[Dict[str, Any]], str]:
        prompt = (
            "Eres un analista experto en extraer recomendaciones de servicios y personas a partir de chats de WhatsApp.\n"
            "Tu objetivo es encontrar TODAS las personas, profesionales, tecnicos o comercios recomendados en la conversacion.\n"
            "Presta especial atencion a pedidos de recomendacion y sus respuestas, y contactos compartidos.\n\n"
            + REGLA_TELEFONOS + REGLA_CONTEXTO + REGLA_REMITENTE + "\n"
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
            texto, model_used = self._pedir(prompt, schema=RecommendationBatch if self.llm is None else None)
            data = _safe_json_loads(texto)
            return data.get("recomendados", []), model_used
        except Exception:
            # Fallback sin response_schema estricto para evitar restricciones de Developer API
            texto, model_used = self._pedir(prompt)
            data = _safe_json_loads(texto)
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
            "6. Si no hay ocurrencias que cumplan los criterios en estos mensajes, devuelve 'filas': [] y en 'respuesta_directa' aclara brevemente que no hubo menciones.\n"
            "7. " + REGLA_TELEFONOS +
            "8. " + REGLA_CONTEXTO +
            "9. " + REGLA_REMITENTE + "\n"
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

        texto, model_used = self._pedir(prompt)
        return _safe_json_loads(texto), model_used

    def extract_recommendations_batched(
        self,
        messages: List[Any],
        chunk_size: int = 80,
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
        self.telefonos_descartados = 0
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

            chunk_text = armar_texto_lote(messages, idx * chunk_size, chunk)

            # Detectar si el lote proviene de un chat específico para completar chat_origen si falta
            chunk_chats = set(getattr(m, "source_chat", "") for m in chunk if getattr(m, "source_chat", ""))
            default_chat = list(chunk_chats)[0] if len(chunk_chats) == 1 else ""

            try:
                batch_results, used_model = self.extract_recommendations(chunk_text)
                if used_model and used_model not in models_used:
                    models_used.append(used_model)
                self.telefonos_descartados += descartar_telefonos_de_remitentes(
                    batch_results or [], telefonos_de_remitentes(chunk))
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

    def synthesize_executive_summary(
        self,
        user_query: str,
        all_filas: List[Dict[str, Any]],
        partial_summaries: List[str]
    ) -> str:
        """
        Produce una conclusión ejecutiva consolidada, fluida y organizada
        para evitar la repetición fragmentada de párrafos lote por lote.
        """
        if not all_filas and not partial_summaries:
            return "No se encontraron datos que coincidan con la búsqueda."

        # Construir contexto compacto para no exceder tokens ni demorar la respuesta
        if all_filas:
            first_row = all_filas[0]
            display_keys = list(first_row.keys())[:7]
            compact_filas = [
                {k: row.get(k, "") for k in display_keys if row.get(k) is not None}
                for row in all_filas[:60]
            ]
            data_context = (
                f"Total de registros detectados: {len(all_filas)}\n"
                f"Muestra de registros estructurados:\n"
                f"{json.dumps(compact_filas, ensure_ascii=False, indent=1)}"
            )
            if len(all_filas) > 60:
                data_context += f"\n... (y {len(all_filas) - 60} registros adicionales coincidentes)"
        else:
            data_context = "Puntos clave detectados en las conversaciones:\n" + "\n".join([f"- {s}" for s in partial_summaries[:15]])

        prompt = (
            "Vas a resumir datos extraídos de chats de WhatsApp de un barrio.\n"
            f"El usuario solicitó buscar en sus chats de WhatsApp lo siguiente:\n\"{user_query}\"\n\n"
            f"DATOS EXTRAÍDOS DE TODAS LAS CONVERSACIONES:\n{data_context}\n\n"
            "INSTRUCCIONES CRÍTICAS:\n"
            "1. Redacta un resumen ÚNICO, claro y breve en español rioplatense. No te presentes ni hables de vos.\n"
            "1b. Usá SOLO lo que dicen los datos. No agregues valoraciones, adjetivos ni conclusiones que no estén en las filas "
            "(por ejemplo 'confiable', 'calificados', 'reconocidos por su rapidez'). Si un dato no está, no lo supongas.\n"
            "1c. Dá el total exacto de registros que figura arriba.\n"
            "1d. No nombres a quienes escribieron en el chat ni muestres sus teléfonos (por ejemplo, 'recomendado por +54…'): "
            "son datos personales de los vecinos. Solo nombres y datos de lo que se buscó.\n"
            "2. NUNCA menciones lotes, ni 'Lote 1', ni repitas frases de apertura como 'Se encontraron...', 'Se analizaron los mensajes...' de manera fragmentada.\n"
            "3. Estructura la respuesta con un breve balance general y luego viñetas agrupadas por rubro, categoría o tema principal.\n"
            "4. Menciona con nombre y apellido a los profesionales, contactos o datos clave más destacados.\n"
            "5. Responde con precisión a lo que el usuario preguntó y aclara que en la tabla inferior se pueden consultar todos los detalles, contactos y teléfonos.\n"
            "6. Sé conciso pero exhaustivo, profesional y muy fácil de leer de un vistazo."
        )

        try:
            texto, _ = self._pedir(prompt, json=False, temperatura=0.2)
            text = texto.strip()
            if text:
                return text
        except Exception as e:
            print(f"[Aviso] No se pudo generar síntesis con IA ({e}), usando resumen estructurado.")

        return build_rule_based_summary(user_query, all_filas, partial_summaries)

    def extract_dynamic_query_batched(
        self,
        messages: List[Any],
        user_query: str,
        chunk_size: int = 80,
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
        self.telefonos_descartados = 0
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

            chunk_text = armar_texto_lote(messages, idx * chunk_size, chunk)

            chunk_chats = set(getattr(m, "source_chat", "") for m in chunk if getattr(m, "source_chat", ""))
            default_chat = list(chunk_chats)[0] if len(chunk_chats) == 1 else ""

            try:
                raw_res, used_model = self.extract_dynamic_query(chunk_text, user_query)
                if used_model and used_model not in models_used:
                    models_used.append(used_model)
                norm = normalize_dynamic_result(raw_res, default_chat=default_chat)
                self.telefonos_descartados += descartar_telefonos_de_remitentes(
                    norm.get("filas", []), telefonos_de_remitentes(chunk))
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

        pct_end = 100
        latest_model = models_used[-1] if models_used else self.model
        if progress_callback:
            progress_callback(
                total_chunks,
                total_chunks,
                pct_end,
                len(all_filas),
                "Consolidando conclusiones y resumen ejecutivo con IA...",
                latest_model
            )

        if not all_filas and not respuestas_parciales:
            if batch_errors:
                respuesta_final = f"Ocurrió un error al procesar los mensajes con la IA: {batch_errors[0]}"
            else:
                respuesta_final = "No se encontraron menciones ni datos relevantes que cumplan con todos los filtros y condiciones solicitadas en los mensajes analizados."
        elif total_chunks == 1:
            if respuestas_parciales:
                respuesta_final = respuestas_parciales[0]
            elif all_filas:
                respuesta_final = f"Se encontraron **{len(all_filas)} registros** relevantes en los mensajes analizados."
            else:
                respuesta_final = "No se encontraron menciones coincidentes."
        else:
            # Consolidar síntesis ejecutiva unificada (vía IA o fallback algorítmico)
            respuesta_final = self.synthesize_executive_summary(user_query, all_filas, respuestas_parciales)

        return {
            "respuesta_directa": respuesta_final,
            "columnas": unified_cols,
            "filas": all_filas,
            "modelos_usados": models_used,
            "errores_lotes": batch_errors,
            "telefonos_descartados": self.telefonos_descartados,
        }
