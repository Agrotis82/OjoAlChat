/**
 * ====================================================================
 * EXTRACTOR DE CHATS DE WHATSAPP WEB - OjoAlChat (OjoAI)
 * ====================================================================
 * 
 * INSTRUCCIONES DE USO:
 * 1. Abre WhatsApp Web (web.whatsapp.com) en tu navegador (Chrome, Edge, Brave, etc.).
 * 2. Entra al chat o grupo que quieres descargar.
 * 3. Presiona F12 (o Clic derecho > Inspeccionar) y ve a la pestaña "Consola" (Console).
 *    (Si es la primera vez que usas la consola, escribe "permitir pegar" o "allow pasting" y presiona Enter).
 * 4. Copia y pega TODO este código y presiona Enter.
 * 5. Aparecerá una ventanita flotante arriba a la derecha contando los mensajes mientras sube solo.
 * 6. Cuando quieras terminar, haz clic en "Detener y Descargar .txt".
 */

(function() {
    // 1. Verificar que haya un chat abierto
    const main = document.querySelector('#main');
    if (!main) {
        alert("Por favor abre primero el chat o grupo en WhatsApp Web.");
        return;
    }

    // 2. Buscar el contenedor que tiene el scroll de mensajes
    function getScrollContainer() {
        for (const el of main.querySelectorAll('*')) {
            const style = window.getComputedStyle(el);
            if ((style.overflowY === 'auto' || style.overflowY === 'scroll') && el.scrollHeight > el.clientHeight) {
                return el;
            }
        }
        return null;
    }

    const scrollContainer = getScrollContainer();
    if (!scrollContainer) {
        alert("No se pudo detectar el contenedor de mensajes.");
        return;
    }

    // 3. Crear panel flotante de control
    const panel = document.createElement('div');
    panel.id = 'wa-extractor-panel';
    panel.style.cssText = `
        position: fixed;
        top: 20px;
        right: 30px;
        z-index: 999999;
        background: #111b21;
        color: #e9edef;
        padding: 16px 20px;
        border-radius: 12px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.5);
        font-family: sans-serif;
        font-size: 14px;
        border: 1px solid #00a884;
    `;
    panel.innerHTML = `
        <div style="font-weight: bold; margin-bottom: 8px; color: #00a884;">Extractor de WhatsApp</div>
        <div style="margin-bottom: 12px;">Mensajes recopilados: <span id="wa-count" style="font-weight: bold; color: #53bdeb;">0</span></div>
        <button id="wa-btn-download" style="
            background: #00a884;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 8px;
            font-weight: bold;
            cursor: pointer;
            margin-right: 8px;
        ">Detener y Descargar .txt</button>
        <button id="wa-btn-cancel" style="
            background: #374248;
            color: #e9edef;
            border: none;
            padding: 8px 12px;
            border-radius: 8px;
            cursor: pointer;
        ">Cancelar</button>
    `;
    document.body.appendChild(panel);

    const messagesMap = new Map();

    // 4. Función para leer los mensajes visibles en el DOM
    function collectMessages() {
        const elements = main.querySelectorAll('[data-pre-plain-text]');
        elements.forEach(el => {
            const meta = el.getAttribute('data-pre-plain-text') || '';
            const textEl = el.querySelector('span.selectable-text') || el;
            const text = textEl.innerText.trim();
            if (text && !messagesMap.has(meta + text)) {
                messagesMap.set(meta + text, `${meta}${text}`);
            }
        });
        const countSpan = document.getElementById('wa-count');
        if (countSpan) countSpan.innerText = messagesMap.size;
    }

    // 5. Iniciar scroll automático hacia arriba
    collectMessages();
    const interval = setInterval(() => {
        collectMessages();
        scrollContainer.scrollTop = 0; // Provoca que WhatsApp cargue mensajes más antiguos
    }, 800);

    // 6. Descargar archivo
    function download() {
        clearInterval(interval);
        panel.remove();

        if (messagesMap.size === 0) {
            alert("No se recopilaron mensajes.");
            return;
        }

        const content = Array.from(messagesMap.values()).join('\n\n');
        const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
        const a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = `chat_whatsapp_${new Date().toISOString().slice(0,10)}.txt`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
    }

    document.getElementById('wa-btn-download').onclick = download;
    document.getElementById('wa-btn-cancel').onclick = () => {
        clearInterval(interval);
        panel.remove();
    };
})();
