import re
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class ChatMessage:
    raw_header: str
    date: str
    time: str
    sender: str
    text: str
    source_chat: str = ""

    def to_formatted_str(self) -> str:
        src = getattr(self, "source_chat", "")
        if src:
            return f"[{src} | {self.date}, {self.time}] {self.sender}: {self.text}"
        return f"[{self.date}, {self.time}] {self.sender}: {self.text}"

class WhatsAppParser:
    # Formats:
    # 1. [2:49 p. m., 29/9/2026] Sender: Text
    # 2. [29/9/2026, 14:49:10] Sender: Text
    # 3. 29/9/2026, 14:49 - Sender: Text
    # 4. 29/09/26, 2:49 p. m. - Sender: Text
    
    PATTERN_BRACKET = re.compile(
        r"^\[(?P<p1>\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}|\d{1,2}:\d{2}(?::\d{2})?(?:\s*[ap]\.?\s*m\.?)?),?\s*(?P<p2>\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}|\d{1,2}:\d{2}(?::\d{2})?(?:\s*[ap]\.?\s*m\.?)?)\]\s+(?P<sender>[^:]+):\s*(?P<text>.*)$",
        re.IGNORECASE
    )
    
    PATTERN_DASH = re.compile(
        r"^(?P<date>\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}),?\s+(?P<time>\d{1,2}:\d{2}(?::\d{2})?(?:\s*[ap]\.?\s*m\.?)?)\s*-\s*(?P<sender>[^:]+):\s*(?P<text>.*)$",
        re.IGNORECASE
    )

    SYSTEM_PATTERNS = [
        re.compile(r"los mensajes y las llamadas están cifrados", re.I),
        re.compile(r"mensajes temporales", re.I),
        re.compile(r"creó el grupo", re.I),
        re.compile(r"cambió el icono", re.I),
        re.compile(r"cambió el asunto", re.I),
        re.compile(r"te añadió", re.I),
        re.compile(r"salió del grupo", re.I),
        re.compile(r"<multimedia omitido>", re.I),
        re.compile(r"<archivo omitido>", re.I),
        re.compile(r"<media omitted>", re.I),
    ]

    def is_system_message(self, text: str) -> bool:
        for p in self.SYSTEM_PATTERNS:
            if p.search(text):
                return True
        return False

    def parse(self, raw_content: str, source_chat: str = "", *args, **kwargs) -> List[ChatMessage]:
        if not raw_content:
            return []
        lines = str(raw_content).splitlines()
        messages: List[ChatMessage] = []
        current_msg: Optional[ChatMessage] = None

        for line in lines:
            line_str = line.strip('\r\n')
            if not line_str.strip():
                continue

            match_bracket = self.PATTERN_BRACKET.match(line_str)
            match_dash = self.PATTERN_DASH.match(line_str) if not match_bracket else None

            if match_bracket:
                p1 = match_bracket.group("p1").strip()
                p2 = match_bracket.group("p2").strip()
                # Un componente de hora siempre contiene ':' o mención de am/pm
                is_p1_time = ":" in p1 or any(x in p1.lower() for x in ["am", "pm", "a. m.", "p. m.", "m."])
                if is_p1_time:
                    time, date = p1, p2
                else:
                    date, time = p1, p2
                
                sender = match_bracket.group("sender").strip()
                text = match_bracket.group("text").strip()

                if current_msg:
                    messages.append(current_msg)
                
                current_msg = ChatMessage(
                    raw_header=f"[{date}, {time}] {sender}",
                    date=date,
                    time=time,
                    sender=sender,
                    text=text,
                )
                current_msg.source_chat = source_chat
            elif match_dash:
                date = match_dash.group("date")
                time = match_dash.group("time")
                sender = match_dash.group("sender").strip()
                text = match_dash.group("text").strip()

                if current_msg:
                    messages.append(current_msg)

                current_msg = ChatMessage(
                    raw_header=f"{date}, {time} - {sender}",
                    date=date,
                    time=time,
                    sender=sender,
                    text=text,
                )
                current_msg.source_chat = source_chat
            else:
                # Continuation of multiline message
                if current_msg:
                    current_msg.text += "\n" + line_str
                else:
                    # Ignore headers or system lines before first message
                    pass

        if current_msg:
            messages.append(current_msg)

        # Filter out system messages and empty text
        clean_messages = [
            m for m in messages 
            if not self.is_system_message(m.text) and m.text.strip()
        ]

        # El script de WhatsApp Web guarda los mensajes por pantallas, de la más nueva a la más vieja.
        # Ordenarlos por fecha y hora deja cada pregunta junto a sus respuestas. El orden es estable:
        # los mensajes del mismo minuto quedan como venían.
        clean_messages.sort(key=message_sort_key)
        return clean_messages


def message_sort_key(m: "ChatMessage"):
    """(año, mes, día, minuto del día) a partir de '29/9/2026' y '2:49 p. m.' o '14:49:10'."""
    fecha = re.match(r"(\d{1,2})[/.-](\d{1,2})[/.-](\d{2,4})", m.date or "")
    if not fecha:
        return (9999, 0, 0, 0)
    dia, mes, anio = (int(x) for x in fecha.groups())
    if anio < 100:
        anio += 2000
    hora = re.match(r"(\d{1,2}):(\d{2})", m.time or "")
    minutos = 0
    if hora:
        h, mi = int(hora.group(1)), int(hora.group(2))
        t = (m.time or "").lower().replace(" ", "").replace(".", "")
        if "pm" in t and h != 12:
            h += 12
        elif "am" in t and h == 12:
            h = 0
        minutos = h * 60 + mi
    return (anio, mes, dia, minutos)


_CONTACTO_RE = re.compile(r"\[CONTACTO: (?P<nombre>.+?) \| (?P<telefono>[^|\]]+)(?: \| (?P<extras>[^\]]+))?\]")
_PEDIDO_RE = re.compile(r"\?|recomiend|alguien|alguno|necesito|busco|tienen|conocen|me pasan|pasame", re.I)


def extraer_contactos(messages: List[ChatMessage], mensajes_atras: int = 15) -> List[dict]:
    """
    Todas las tarjetas de contacto compartidas ([CONTACTO: Nombre | teléfono]), sin IA, con el pedido
    al que probablemente responden: el mensaje anterior más cercano del mismo chat, de otra persona,
    que pregunta o pide algo. Los mensajes tienen que estar en orden (WhatsAppParser.parse los ordena).
    """
    filas = []
    por_chat: dict = {}
    for m in messages:
        por_chat.setdefault(getattr(m, "source_chat", ""), []).append(m)

    for chat, msgs in por_chat.items():
        for i, m in enumerate(msgs):
            for c in _CONTACTO_RE.finditer(m.text):
                pedido = ""
                for previo in reversed(msgs[max(0, i - mensajes_atras):i]):
                    if previo.sender != m.sender and "[CONTACTO:" not in previo.text and _PEDIDO_RE.search(previo.text):
                        pedido = previo.text.strip().replace("\n", " ")[:200]
                        break
                telefono = c.group("telefono").strip()
                filas.append({
                    "nombre_contacto": c.group("nombre").strip(),
                    "telefono": "" if telefono == "sin número" else telefono,
                    "extras": (c.group("extras") or "").strip(),
                    "compartio": m.sender,
                    "chat": chat,
                    "fecha": m.date,
                    "pedido_previo": pedido,
                })
    return filas
