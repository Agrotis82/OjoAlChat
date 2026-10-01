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

        return clean_messages
