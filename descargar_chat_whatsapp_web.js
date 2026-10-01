/**
 * ====================================================================
 * EXTRACTOR MULTI-CHAT DE WHATSAPP WEB - OjoAlChat (OjoAI)
 * ====================================================================
 * 
 * NOVEDADES (SESIÓN CONTINUA MULTI-CHAT):
 * - Permite descargar múltiples chats en la misma sesión sin cerrar ni volver a pegar el código.
 * - DETECCIÓN AUTOMÁTICA AL CAMBIAR DE CHAT: Al hacer clic en otro grupo en la barra
 *   izquierda de WhatsApp, el panel detecta el nuevo grupo, reinicia los contadores
 *   y queda listo para volver a extraer en 1 clic.
 * - Nombre del archivo y cantidad de mensajes actualizados para cada chat.
 * - Botón de refresco manual "🔄 Detectar chat actual" por si cambiaste de pantalla.
 * 
 * INSTRUCCIONES:
 * 1. Abre WhatsApp Web y presiona F12 > Consola.
 * 2. Pega este código y presiona Enter una sola vez.
 * 3. El panel quedará activo: puedes extraer un chat, luego hacer clic en otro grupo
 *    y volver a extraer cuantas veces quieras.
 */

(function() {
    // 1. Evitar duplicar panel
    const existingPanel = document.getElementById('ojoai-panel');
    if (existingPanel) existingPanel.remove();

    // 2. Funciones auxiliares de sanitización y detección
    function sanitizeFilename(name) {
        return name
            .replace(/[\/\\?%*:|"<>]/g, '')
            .replace(/\s+/g, '_')
            .replace(/_+/g, '_')
            .slice(0, 40);
    }

    function getChatTitle() {
        const header = document.querySelector('#main header');
        if (!header) return '';
        const infoBtn = header.querySelector('div[role="button"]') || header;
        const lines = infoBtn.innerText.split('\n').map(l => l.trim()).filter(Boolean);
        return lines.length > 0 ? lines[0] : '';
    }

    function getScrollContainer() {
        const main = document.querySelector('#main');
        if (!main) return null;
        for (const el of main.querySelectorAll('*')) {
            const style = window.getComputedStyle(el);
            if ((style.overflowY === 'auto' || style.overflowY === 'scroll') && el.scrollHeight > el.clientHeight) {
                return el;
            }
        }
        return null;
    }

    // Fechas por defecto
    const today = new Date();
    const oneMonthAgo = new Date();
    oneMonthAgo.setDate(today.getDate() - 30);
    const formatDateInput = d => d.toISOString().slice(0, 10);

    const initialTitle = getChatTitle() || 'chat';
    let currentChatTitle = initialTitle;

    // 3. Crear panel flotante
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
        width: 330px;
    `;

    panel.innerHTML = `
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
            <div style="font-weight:bold; font-size:15px; color:#00a884; display:flex; align-items:center; gap:6px;">
                <span>👁️ OjoAlChat</span>
                <span style="font-size:10px; background:#005c4b; color:#25d366; padding:2px 6px; border-radius:10px;">Multi-Chat</span>
            </div>
            <button id="ojo-btn-close" style="background:none; border:none; color:#8696a0; cursor:pointer; font-size:16px;">✖</button>
        </div>

        <div style="background:#182229; padding:8px 10px; border-radius:8px; margin-bottom:10px; border:1px solid #222e35; display:flex; justify-content:space-between; align-items:center;">
            <div style="overflow:hidden; margin-right:8px;">
                <span style="color:#8696a0; font-size:10px; text-transform:uppercase; letter-spacing:0.5px;">Chat Activo:</span>
                <div id="ojo-detected-title" style="font-weight:bold; color:#53bdeb; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">${initialTitle || 'Ninguno (Abre un chat)'}</div>
            </div>
            <button id="ojo-btn-refresh-chat" title="Actualizar al chat actual" style="background:#202c33; color:#00a884; border:1px solid #2a3942; border-radius:6px; padding:4px 8px; cursor:pointer; font-size:11px;">🔄</button>
        </div>

        <div style="margin-bottom:8px;">
            <label style="display:block; font-size:11px; color:#8696a0; margin-bottom:3px;">📁 Nombre del archivo:</label>
            <input type="text" id="ojo-chat-name" value="${sanitizeFilename(initialTitle)}" style="width:100%; background:#202c33; color:#53bdeb; font-weight:bold; border:1px solid #2a3942; border-radius:6px; padding:6px 8px; box-sizing:border-box;">
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

    // 4. Variables de extracción
    const messagesMap = new Map();
    let oldestDateFound = null;
    let timer = null;
    let consecutiveSameCount = 0;
    let lastMessagesTotal = 0;
    let isExtracting = false;

    function parseMessageDate(preText) {
        if (!preText) return null;
        const match = preText.match(/(\d{1,2})[\/\.-](\d{1,2})[\/\.-](\d{2,4})/);
        if (!match) return null;
        let [_, d, m, y] = match;
        if (y.length === 2) y = "20" + y;
        return new Date(parseInt(y), parseInt(m) - 1, parseInt(d));
    }

    // 5. Función que detecta si el usuario hizo clic en otro chat
    function checkActiveChatChange() {
        const titleNow = getChatTitle();
        if (titleNow && titleNow !== currentChatTitle) {
            currentChatTitle = titleNow;
            document.getElementById('ojo-detected-title').innerText = titleNow;
            document.getElementById('ojo-chat-name').value = sanitizeFilename(titleNow);

            // Si no se está ejecutando una extracción, resetear contadores para el nuevo chat
            if (!isExtracting) {
                resetCounters(`Listo para extraer: ${titleNow}`);
            }
        }
    }

    function resetCounters(statusMsg = 'Listo para iniciar') {
        messagesMap.clear();
        oldestDateFound = null;
        consecutiveSameCount = 0;
        lastMessagesTotal = 0;
        document.getElementById('ojo-count').innerText = '0';
        document.getElementById('ojo-oldest-date').innerText = '-';
        document.getElementById('ojo-status').innerText = statusMsg;
        document.getElementById('ojo-status').style.color = '#53bdeb';
    }

    // Vigilante de cambio de chat cada 1 segundo
    const chatWatcher = setInterval(checkActiveChatChange, 1000);

    document.getElementById('ojo-btn-refresh-chat').onclick = () => {
        checkActiveChatChange();
        resetCounters(`Chat actualizado: ${currentChatTitle}`);
    };

    function collectMessages(targetFromDate, targetToDate) {
        const main = document.querySelector('#main');
        if (!main) return;

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

        if (messagesMap.size === lastMessagesTotal) {
            consecutiveSameCount++;
        } else {
            consecutiveSameCount = 0;
            lastMessagesTotal = messagesMap.size;
        }

        // Parada 1: Fecha alcanzada
        if (targetFromDate && oldestDateFound && oldestDateFound <= targetFromDate) {
            finishAndDownload(targetFromDate, targetToDate, "¡Fecha alcanzada!");
            return;
        }

        // Parada 2: Inicio del chat
        if (consecutiveSameCount >= 6) {
            finishAndDownload(targetFromDate, targetToDate, "¡Inicio del chat alcanzado!");
            return;
        }
    }

    function scrollStep(container) {
        if (!container) return;
        container.scrollTop = 0;
        setTimeout(() => {
            if (container.scrollTop === 0) container.scrollTop = 40;
            container.scrollTop = 0;
        }, 150);
    }

    function finishAndDownload(fromDate, toDate, reason) {
        clearInterval(timer);
        timer = null;
        isExtracting = false;

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
            document.getElementById('ojo-btn-start').style.display = 'block';
            document.getElementById('ojo-btn-stop').style.display = 'none';
            document.getElementById('ojo-status').innerText = 'Sin mensajes en este rango.';
            document.getElementById('ojo-status').style.color = '#ffd279';
            return;
        }

        document.getElementById('ojo-status').innerText = `✔️ ${reason} (${filtered.length} msgs descargados).`;
        document.getElementById('ojo-status').style.color = '#25d366';

        const inputName = document.getElementById('ojo-chat-name').value;
        const finalGroupName = sanitizeFilename(inputName || currentChatTitle || 'chat');
        const fromStr = fromDate ? fromDate.toISOString().slice(0,10) : 'inicio';
        const toStr = toDate ? toDate.toISOString().slice(0,10) : 'hoy';
        
        const finalFilename = `chat_${finalGroupName}_${filtered.length}msgs_${fromStr}_a_${toStr}.txt`;

        const blob = new Blob([filtered.join('\n\n')], { type: 'text/plain;charset=utf-8' });
        const a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = finalFilename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);

        // Volver a activar botón para poder extraer otro chat
        setTimeout(() => {
            document.getElementById('ojo-btn-start').style.display = 'block';
            document.getElementById('ojo-btn-start').innerText = '▶ Extraer otro chat o rango';
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
        checkActiveChatChange();
        const scrollContainer = getScrollContainer();
        if (!scrollContainer) {
            alert("No se detectó un chat abierto. Haz clic en el grupo o conversación que quieras descargar.");
            return;
        }

        // Reiniciar memoria para esta extracción
        messagesMap.clear();
        oldestDateFound = null;
        consecutiveSameCount = 0;
        lastMessagesTotal = 0;
        isExtracting = true;

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
            scrollStep(scrollContainer);
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
        clearInterval(chatWatcher);
        if (timer) clearInterval(timer);
        panel.remove();
    };
})();
