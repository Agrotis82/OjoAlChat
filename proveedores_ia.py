"""
Proveedores de IA para OjoAlChat, además de Gemini (que vive en extractor.py con su cascada de modelos).

Cada cliente expone lo mismo: generar(prompt, json, temperatura) -> (texto, modelo_usado).
El texto se parsea afuera con _safe_json_loads, así que alcanza con que el modelo responda JSON.
"""
from typing import Optional, Tuple

# id -> datos para la barra lateral de la app
PROVEEDORES = {
    "gemini": {
        "nombre": "Google Gemini",
        "variables": ["GEMINI_API_KEY", "GOOGLE_API_KEY"],
        "clave_url": "https://aistudio.google.com/apikey",
    },
    "anthropic": {
        "nombre": "Anthropic (Claude)",
        "variables": ["ANTHROPIC_API_KEY"],
        "clave_url": "https://console.anthropic.com/settings/keys",
        "modelos": ["claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-4-5"],
    },
    "openai": {
        "nombre": "OpenAI (ChatGPT)",
        "variables": ["OPENAI_API_KEY"],
        "clave_url": "https://platform.openai.com/api-keys",
    },
    "compatible": {
        "nombre": "Otro compatible con OpenAI (DeepSeek, Groq, OpenRouter, Ollama…)",
        "variables": ["OJO_API_KEY"],
        "clave_url": "",
    },
}

# Servicios que hablan la API de OpenAI: solo cambia la dirección.
SERVICIOS_COMPATIBLES = {
    "DeepSeek": "https://api.deepseek.com",
    "Groq": "https://api.groq.com/openai/v1",
    "OpenRouter": "https://openrouter.ai/api/v1",
    "Ollama (en esta computadora)": "http://localhost:11434/v1",
}

# Modelos de Claude que aceptan el respaldo automático ante un rechazo (fallbacks: "default").
_CLAUDE_CON_RESPALDO = {"claude-opus-5-5", "claude-sonnet-5-5", "claude-opus-5", "claude-fable-5-1"}


class ClienteClaude:
    def __init__(self, api_key: str, modelo: str):
        import anthropic

        self.modelo = modelo or "claude-opus-5-5"
        # El SDK reintenta solo los 429, 5xx y errores de conexión.
        self.client = anthropic.Anthropic(api_key=api_key, max_retries=3, timeout=300.0)

    def generar(self, prompt: str, json: bool = True, temperatura: Optional[float] = None) -> Tuple[str, str]:
        # La temperatura no se manda: los modelos actuales de Claude no la aceptan.
        pedido = dict(
            model=self.modelo,
            max_tokens=16000,
            messages=[{"role": "user", "content": prompt}],
        )
        if self.modelo in _CLAUDE_CON_RESPALDO:
            # Si el modelo rechaza el pedido por una política de seguridad, la API lo repite con otro modelo.
            respuesta = self.client.beta.messages.create(
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
                **pedido,
            )
        else:
            respuesta = self.client.messages.create(**pedido)

        if respuesta.stop_reason == "refusal":
            raise RuntimeError("Claude rechazó el pedido por sus políticas de seguridad.")
        texto = "".join(bloque.text for bloque in respuesta.content if bloque.type == "text")
        return texto, respuesta.model


class ClienteOpenAI:
    """OpenAI y cualquier servicio compatible con su API (base_url)."""

    def __init__(self, api_key: str, modelo: str, base_url: Optional[str] = None):
        import openai

        if not modelo:
            raise ValueError("Elegí el modelo a usar (por ejemplo, el que figura en la página del servicio).")
        self.openai = openai
        self.modelo = modelo
        # Ollama no pide clave, pero la librería exige algún valor.
        self.client = openai.OpenAI(api_key=api_key or "sin-clave", base_url=base_url or None,
                                    max_retries=3, timeout=300.0)

    def generar(self, prompt: str, json: bool = True, temperatura: Optional[float] = None) -> Tuple[str, str]:
        extras = {}
        if json:
            extras["response_format"] = {"type": "json_object"}
        if temperatura is not None:
            extras["temperature"] = temperatura
        mensajes = [{"role": "user", "content": prompt}]
        try:
            respuesta = self.client.chat.completions.create(model=self.modelo, messages=mensajes, **extras)
        except self.openai.BadRequestError:
            # Algunos modelos o servicios no aceptan temperatura o formato JSON: se repite sin esos extras.
            if not extras:
                raise
            respuesta = self.client.chat.completions.create(model=self.modelo, messages=mensajes)
        return respuesta.choices[0].message.content or "", respuesta.model or self.modelo


def crear_cliente(proveedor: str, api_key: str, modelo: str, base_url: Optional[str] = None):
    if proveedor == "anthropic":
        return ClienteClaude(api_key, modelo)
    if proveedor in ("openai", "compatible"):
        return ClienteOpenAI(api_key, modelo, base_url if proveedor == "compatible" else None)
    raise ValueError(f"Proveedor de IA desconocido: {proveedor}")
