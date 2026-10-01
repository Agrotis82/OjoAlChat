/**
 * ====================================================================
 * EXTRACTOR INTELIGENTE DE CHATS - OjoAlChat (OjoAI)
 * ====================================================================
 * 
 * NOVEDADES:
 * - Corrige la detección para tomar SIEMPRE el NOMBRE DEL GRUPO (no la lista de integrantes).
 * - Campo editable en el panel para ver y cambiar el nombre del archivo si se desea.
 * - Incluye la CANTIDAD DE MENSAJES en el nombre del archivo (ej: chat_Vecinas_Molineras_254msgs_...).
 * - Rango de fechas y parada automática (Auto-stop).
 * 
 * INSTRUCCIONES:
 * 1. Abre WhatsApp Web (web.whatsapp.com) y entra al grupo/chat.
 * 2. Presiona F12 > pestaña Consola (Console).
 * 3. Pega este código y presiona Enter.
 * 4. Verifica el nombre y fechas en el panel y haz clic en "▶ Iniciar Extracción Automática".
 */

(function() {
    // 1. Evitar duplicar el panel si ya estaba abierto
    const existingPanel = document.getElementById('ojoai-panel');
    if (existingPanel) existingPanel.remove();

    // 2. Verificar chat abierto
    const main = document.querySelector('#main');
    if (!main) {
        alert("Por favor abre primero el chat o grupo en WhatsApp Web.");
        return;
    }

    // 3. Detectar nombre del grupo (evitando la lista de integrantes)
    function getChatTitle() {
        const header = main.querySelector('header');
        if (!header) return 'chat';

        // En WhatsApp Web, el header contiene un botón con la info del chat.
        // La línea 0 es SIEMPRE el nombre del grupo. La línea 1 son los integrantes.
        const infoBtn = header.querySelector('div[role="button"]') || header;
        const lines = infoBtn.innerText.split('\n').map(l => l.trim()).filter(Boolean);

        if (lines.length > 0) {
            return lines[0];
        }
        return 'chat';
    }

    function sanitizeFilename(name) {
        return name
            .replace(/[\/\\?%*:|"<>]/g, '')   // Quitar caracteres no permitidos en archivos
            .replace(/\s+/g, '_')             // Reemplazar espacios por guiones bajos
            .replace(/_+/g, '_')              // Evitar guiones dobles
            .slice(0, 40);                    // Limitar largo
    }

    const detectedTitle = getChatTitle();
    const cleanInitialName = sanitizeFilename(detectedTitle);

    // 4. Buscar contenedor con scroll
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
        alert("No se pudo detectar el contenedor de mensajes. Asegúrate de tener el chat abierto.");
        return;
    }

    // Fechas por defecto (Último mes)
    const today = new Date();
    const oneMonthAgo = new Date();
    oneMonthAgo.setDate(today.getDate() - 30);
    const formatDateInput = d => d.toISOString().slice(0, 10);

    // 5. Crear interfaz flotante
    const panel = document.createElement('div');
    panel.id = 'ojoai-panel';
    panel.style.cssText = `
        position: fixed;
        top: 20px;
        right: 25px;
        z-index: 999999;
        background: #111b21;
        color: #e9edef;
        padding: 18px 22px;
        border-radius: 14px;
        box-shadow: 0 8px 32px rgba(0,0,0,0.6);
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        font-size: 13px;
        border: 1px solid #00a884;
        width: 320px;
    `;

    panel.innerHTML = `
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
            <div style="font-weight:bold; font-size:15px; color:#00a884; display:flex; align-items:center; gap:6px;">
                <span>👁️ OjoAlChat</span>
                <span style="font-size:10px; background:#005c4b; color:#25d366; padding:2px 6px; border-radius:10px;">Auto-Extractor</span>
            </div>
            <button id="ojo-btn-close" style="background:none; border:none; color:#8696a0; cursor:pointer; font-size:16px;">✖</button>
        </div>

        <div style="margin-bottom:10px;">
            <label style="display:block; font-size:11px; color:#8696a0; margin-bottom:3px;">📁 Nombre del grupo para el archivo:</label>
            <input type="text" id="ojo-chat-name" value="${cleanInitialName}" style="width:100%; background:#202c33; color:#53bdeb; font-weight:bold; border:1px solid #2a3942; border-radius:6px; padding:6px 8px; box-sizing:border-box;">
        </div>

        <div style="margin-bottom:8px;">
            <label style="display:block; font-size:11px; color:#8696a0; margin-bottom:3px;">📅 DESDE (Límite hacia atrás):</label>
            <input type="date" id="ojo-date-from" value="${formatDateInput(oneMonthAgo)}" style="width:100%; background:#202c33; color:#e9edef; border:1px solid #2a3942; border-radius:6px; padding:6px 8px; box-sizing:border-box;">
        </div>

        <div style="margin-bottom:10px;">
            <label style="display:block; font-size:11px; color:#8696a0; margin-bottom:3px;">📅 HASTA (Más reciente):</label>
            <input type="date" id="ojo-date-to" value="${formatDateInput(today)}" style="width:100%; background:#202c33; color:#e9edef; border:1px solid #2a3942; border-radius:6px; padding:6px 8px; box-sizing:border-box;">
        </div>

        <div style="display:flex; gap:6px; margin-bottom:12px;">
            <button id="ojo-quick-1m" style="flex:1; background:#202c33; color:#53bdeb; border:1px solid #2a3942; padding:4px; border-radius:6px; font-size:11px; cursor:pointer;">1 Mes</button>
            <button id="ojo-quick-3m" style="flex:1; background:#202c33; color:#53bdeb; border:1px solid #2a3942; padding:4px; border-radius:6px; font-size:11px; cursor:pointer;">3 Meses</button>
            <button id="ojo-quick-all" style="flex:1; background:#202c33; color:#53bdeb; border:1px solid #2a3942; padding:4px; border-radius:6px; font-size:11px; cursor:pointer;">Todo</button>
        </div>

        <div style="background:#202c33; border-radius:8px; padding:10px; margin-bottom:12px; font-size:12px;">
            <div style="display:flex; justify-content:space-between; margin-bottom:4px;">
                <span style="color:#8696a0;">Mensajes recopilados:</span>
                <span id="ojo-count" style="font-weight:bold; color:#00a884;">0</span>
            </div>
            <div style="display:flex; justify-content:space-between;">
                <span style="color:#8696a0;">Fecha más antigua leída:</span>
                <span id="ojo-oldest-date" style="font-weight:bold; color:#53bdeb;">-</span>
            </div>
            <div id="ojo-status" style="margin-top:6px; font-size:11px; color:#ffd279; text-align:center;">Listo para iniciar</div>
        </div>

        <div style="display:flex; flex-direction:column; gap:6px;">
            <button id="ojo-btn-start" style="background:#00a884; color:#111b21; border:none; padding:10px; border-radius:8px; font-weight:bold; cursor:pointer; font-size:13px;">▶ Iniciar Extracción Automática</button>
            <button id="ojo-btn-stop" style="background:#374248; color:#e9edef; border:none; padding:8px; border-radius:8px; cursor:pointer; font-size:12px; display:none;">⏹ Detener y Descargar ahora</button>
        </div>
    `;

    document.body.appendChild(panel);

    // 6. Parser de fechas
    function parseMessageDate(preText) {
        if (!preText) return null;
        const match = preText.match(/(\d{1,2})[\/\.-](\d{1,2})[\/\.-](\d{2,4})/);
        if (!match) return null;
        let [_, d, m, y] = match;
        if (y.length === 2) y = "20" + y;
        return new Date(parseInt(y), parseInt(m) - 1, parseInt(d));
    }

    const messagesMap = new Map();
    let oldestDateFound = null;
    let timer = null;
    let consecutiveSameCount = 0;
    let lastMessagesTotal = 0;

    function collectMessages(targetFromDate, targetToDate) {
        const elements = main.querySelectorAll('[data-pre-plain-text]');
        elements.forEach(el => {
            const meta = el.getAttribute('data-pre-plain-text') || '';
            const textEl = el.querySelector('span.selectable-text') || el;
            const text = textEl.innerText.trim();
            const msgDate = parseMessageDate(meta);

            if (msgDate) {
                if (!oldestDateFound || msgDate < oldestDateFound) {
                    oldestDateFound = msgDate;
                }
            }

            const key = meta + text;
            if (text && !messagesMap.has(key)) {
                messagesMap.set(key, {
                    fullText: `${meta}${text}`,
                    date: msgDate
                });
            }
        });

        document.getElementById('ojo-count').innerText = messagesMap.size;
        if (oldestDateFound) {
            document.getElementById('ojo-oldest-date').innerText = oldestDateFound.toLocaleDateString();
        }

        // Detectar si terminó de cargar historial
        if (messagesMap.size === lastMessagesTotal) {
            consecutiveSameCount++;
        } else {
            consecutiveSameCount = 0;
            lastMessagesTotal = messagesMap.size;
        }

        // Condición 1: Llegó a la fecha límite
        if (targetFromDate && oldestDateFound && oldestDateFound <= targetFromDate) {
            finishAndDownload(targetFromDate, targetToDate, "¡Fecha alcanzada!");
            return;
        }

        // Condición 2: Llegó al inicio del chat
        if (consecutiveSameCount >= 6) {
            finishAndDownload(targetFromDate, targetToDate, "¡Inicio del chat alcanzado!");
            return;
        }
    }

    function scrollStep() {
        scrollContainer.scrollTop = 0;
        setTimeout(() => {
            if (scrollContainer.scrollTop === 0) scrollContainer.scrollTop = 40;
            scrollContainer.scrollTop = 0;
        }, 150);
    }

    function finishAndDownload(fromDate, toDate, reason) {
        clearInterval(timer);
        timer = null;

        // Filtrar mensajes dentro del rango solicitado
        const filtered = [];
        messagesMap.forEach(item => {
            if (!item.date) {
                filtered.push(item.fullText);
            } else {
                let valid = true;
                if (fromDate && item.date < fromDate) valid = false;
                if (toDate && item.date > toDate) valid = false;
                if (valid) filtered.push(item.fullText);
            }
        });

        if (filtered.length === 0) {
            alert("No se encontraron mensajes dentro del rango de fechas especificado.");
            return;
        }

        document.getElementById('ojo-status').innerText = `✔️ ${reason} (${filtered.length} mensajes). Descargando...`;
        document.getElementById('ojo-status').style.color = '#25d366';

        // Nombre del archivo personalizado: chat_[Grupo]_[Cant]msgs_[Desde]_a_[Hasta].txt
        const inputName = document.getElementById('ojo-chat-name').value;
        const finalGroupName = sanitizeFilename(inputName || cleanInitialName || 'grupo');
        const fromStr = fromDate ? fromDate.toISOString().slice(0,10) : 'inicio';
        const toStr = toDate ? toDate.toISOString().slice(0,10) : 'hoy';
        
        // Incluye la cantidad de mensajes
        const finalFilename = `chat_${finalGroupName}_${filtered.length}msgs_${fromStr}_a_${toStr}.txt`;

        const blob = new Blob([filtered.join('\n\n')], { type: 'text/plain;charset=utf-8' });
        const a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = finalFilename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);

        setTimeout(() => {
            document.getElementById('ojo-btn-start').style.display = 'block';
            document.getElementById('ojo-btn-stop').style.display = 'none';
        }, 1000);
    }

    // Botones rápidos
    document.getElementById('ojo-quick-1m').onclick = () => {
        const d = new Date(); d.setDate(d.getDate() - 30);
        document.getElementById('ojo-date-from').value = formatDateInput(d);
        document.getElementById('ojo-date-to').value = formatDateInput(new Date());
    };
    document.getElementById('ojo-quick-3m').onclick = () => {
        const d = new Date(); d.setDate(d.getDate() - 90);
        document.getElementById('ojo-date-from').value = formatDateInput(d);
        document.getElementById('ojo-date-to').value = formatDateInput(new Date());
    };
    document.getElementById('ojo-quick-all').onclick = () => {
        document.getElementById('ojo-date-from').value = "2020-01-01";
        document.getElementById('ojo-date-to').value = formatDateInput(new Date());
    };

    // Iniciar
    document.getElementById('ojo-btn-start').onclick = () => {
        const fromVal = document.getElementById('ojo-date-from').value;
        const toVal = document.getElementById('ojo-date-to').value;

        const fromDate = fromVal ? new Date(fromVal + "T00:00:00") : null;
        const toDate = toVal ? new Date(toVal + "T23:59:59") : null;

        document.getElementById('ojo-btn-start').style.display = 'none';
        document.getElementById('ojo-btn-stop').style.display = 'block';
        document.getElementById('ojo-status').innerText = '🔄 Subiendo y recopilando mensajes...';
        document.getElementById('ojo-status').style.color = '#ffd279';

        collectMessages(fromDate, toDate);
        timer = setInterval(() => {
            scrollStep();
            collectMessages(fromDate, toDate);
        }, 750);
    };

    // Detener manual
    document.getElementById('ojo-btn-stop').onclick = () => {
        const fromVal = document.getElementById('ojo-date-from').value;
        const toVal = document.getElementById('ojo-date-to').value;
        const fromDate = fromVal ? new Date(fromVal + "T00:00:00") : null;
        const toDate = toVal ? new Date(toVal + "T23:59:59") : null;
        finishAndDownload(fromDate, toDate, "Descarga manual");
    };

    // Cerrar
    document.getElementById('ojo-btn-close').onclick = () => {
        if (timer) clearInterval(timer);
        panel.remove();
    };
})();
