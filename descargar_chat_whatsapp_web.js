/**
 * ====================================================================
 * EXTRACTOR MULTI-CHAT DE WHATSAPP WEB - OjoAlChat (OjoAI)
 * ====================================================================
 * 
 * NOVEDADES:
 * - BOTÓN DE DESCARGA INFALIBLE: Usa la API nativa de guardado de Windows (showSaveFilePicker)
 *   o enlaces directos con eventos aislados (stopPropagation) para que WhatsApp Web NO bloquee el clic.
 * - Copia directa al portapapeles y visualizador de texto en el panel.
 * - Limpieza de nombres sin tildes ni caracteres inválidos para Windows.
 * - Extracción multi-chat continua sin recargar la página.
 */

(function() {
    // 1. Evitar duplicar panel
    const existingPanel = document.getElementById('ojoai-panel');
    if (existingPanel) existingPanel.remove();

    // 2. Limpieza de nombres sin tildes para evitar errores de descarga en Windows/Navegadores
    function sanitizeFilename(name) {
        return name
            .normalize("NFD").replace(/[\u0300-\u036f]/g, "") // Quitar tildes (é -> e)
            .replace(/[\/\\?%*:|"<>]/g, '')                   // Quitar caracteres inválidos
            .replace(/\s+/g, '_')                             // Espacios a guiones bajos
            .replace(/_+/g, '_')
            .slice(0, 45);
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
                <span style="font-size:10px; background:#005c4b; color:#25d366; padding:2px 6px; border-radius:10px;">Auto-Extractor</span>
            </div>
            <button id="ojo-btn-close" style="background:none; border:none; color:#8696a0; cursor:pointer; font-size:16px;">✖</button>
        </div>

        <div style="background:#182229; padding:8px 10px; border-radius:8px; margin-bottom:10px; border:1px solid #222e35; display:flex; justify-content:space-between; align-items:center;">
            <div style="overflow:hidden; margin-right:8px;">
                <span style="color:#8696a0; font-size:10px; text-transform:uppercase; letter-spacing:0.5px;">Chat Activo:</span>
                <div id="ojo-detected-title" style="font-weight:bold; color:#53bdeb; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">${initialTitle || 'Ninguno'}</div>
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

        <div id="ojo-action-box" style="display:flex; flex-direction:column; gap:6px;">
            <button id="ojo-btn-start" style="background:#00a884; color:#111b21; border:none; padding:10px; border-radius:8px; font-weight:bold; cursor:pointer; font-size:13px;">▶ Iniciar Extracción Automática</button>
            <button id="ojo-btn-stop" style="background:#374248; color:#e9edef; border:none; padding:8px; border-radius:8px; cursor:pointer; font-size:12px; display:none;">⏹ Detener y Descargar ahora</button>
        </div>

        <!-- Contenedor infalible para descarga y guardado directo -->
        <div id="ojo-download-ready-box" style="display:none; margin-top:10px; flex-direction:column; gap:6px;">
            <button id="ojo-btn-download" style="width:100%; background:#25d366; color:#111b21; border:none; padding:12px 10px; border-radius:8px; font-weight:bold; cursor:pointer; font-size:13px; box-shadow:0 4px 14px rgba(37,211,102,0.4); text-transform:uppercase; letter-spacing:0.5px;">📥 Guardar Archivo en mi PC</button>
            <div style="display:flex; gap:6px;">
                <button id="ojo-btn-copy" style="flex:1; background:#202c33; color:#53bdeb; border:1px solid #2a3942; padding:7px; border-radius:8px; cursor:pointer; font-size:11px; font-weight:bold;">📋 Copiar Todo</button>
                <button id="ojo-btn-view" style="flex:1; background:#202c33; color:#ffd279; border:1px solid #2a3942; padding:7px; border-radius:8px; cursor:pointer; font-size:11px; font-weight:bold;">👁️ Ver Texto</button>
            </div>
            <div id="ojo-preview-box" style="display:none; margin-top:4px;">
                <textarea id="ojo-preview-textarea" style="width:100%; height:110px; background:#111b21; color:#e9edef; border:1px solid #2a3942; border-radius:6px; font-size:10px; padding:6px; box-sizing:border-box; resize:vertical; font-family:monospace;"></textarea>
                <div style="font-size:10px; color:#8696a0; margin-top:2px;">Tip: Puedes seleccionar todo este texto y guardarlo en el Bloc de Notas.</div>
            </div>
        </div>
    `;

    document.body.appendChild(panel);

    const messagesMap = new Map();
    let oldestDateFound = null;
    let timer = null;
    let consecutiveSameCount = 0;
    let lastMessagesTotal = 0;
    let isExtracting = false;
    let lastExportedText = '';
    let lastFilename = '';

    function parseMessageDate(preText) {
        if (!preText) return null;
        const match = preText.match(/(\d{1,2})[\/\.-](\d{1,2})[\/\.-](\d{2,4})/);
        if (!match) return null;
        let [_, d, m, y] = match;
        if (y.length === 2) y = "20" + y;
        return new Date(parseInt(y), parseInt(m) - 1, parseInt(d));
    }

    function checkActiveChatChange() {
        const titleNow = getChatTitle();
        if (titleNow && titleNow !== currentChatTitle) {
            currentChatTitle = titleNow;
            document.getElementById('ojo-detected-title').innerText = titleNow;
            document.getElementById('ojo-chat-name').value = sanitizeFilename(titleNow);

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
        lastExportedText = '';
        document.getElementById('ojo-count').innerText = '0';
        document.getElementById('ojo-oldest-date').innerText = '-';
        document.getElementById('ojo-status').innerText = statusMsg;
        document.getElementById('ojo-status').style.color = '#53bdeb';
        document.getElementById('ojo-download-ready-box').style.display = 'none';
        document.getElementById('ojo-preview-box').style.display = 'none';
        document.getElementById('ojo-btn-start').style.display = 'block';
        document.getElementById('ojo-btn-stop').style.display = 'none';
    }

    const chatWatcher = setInterval(checkActiveChatChange, 1000);

    document.getElementById('ojo-btn-refresh-chat').onclick = (e) => {
        e.preventDefault();
        e.stopPropagation();
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

        const inputName = document.getElementById('ojo-chat-name').value;
        const finalGroupName = sanitizeFilename(inputName || currentChatTitle || 'chat');
        const fromStr = fromDate ? fromDate.toISOString().slice(0,10) : 'inicio';
        const toStr = toDate ? toDate.toISOString().slice(0,10) : 'hoy';
        
        lastFilename = `chat_${finalGroupName}_${filtered.length}msgs_${fromStr}_a_${toStr}.txt`;
        lastExportedText = filtered.join('\n\n');

        // Configurar botón de descarga
        const btnDl = document.getElementById('ojo-btn-download');
        btnDl.innerText = `📥 Guardar Archivo (${filtered.length} msgs)`;
        document.getElementById('ojo-download-ready-box').style.display = 'flex';

        document.getElementById('ojo-status').innerText = `✔️ ${reason} (${filtered.length} msgs listos)`;
        document.getElementById('ojo-status').style.color = '#25d366';

        // Intento automático no invasivo en segundo plano
        try {
            const blob = new Blob([lastExportedText], { type: 'text/plain;charset=utf-8' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.style.display = 'none';
            a.href = url;
            a.download = lastFilename;
            document.documentElement.appendChild(a);
            a.click();
            setTimeout(() => { a.remove(); URL.revokeObjectURL(url); }, 2000);
        } catch (e) {}

        document.getElementById('ojo-btn-start').style.display = 'block';
        document.getElementById('ojo-btn-start').innerText = '▶ Extraer otro chat o rango';
        document.getElementById('ojo-btn-stop').style.display = 'none';
    }

    // Función infalible de guardado de archivo
    async function executeSave(text, filename) {
        if (!text) {
            alert("No hay mensajes disponibles para guardar.");
            return;
        }

        // Método 1: Ventana oficial de Windows "Guardar como..." (Chromium 86+)
        if (window.showSaveFilePicker) {
            try {
                const handle = await window.showSaveFilePicker({
                    suggestedName: filename,
                    types: [{
                        description: 'Archivo de texto (.txt)',
                        accept: { 'text/plain': ['.txt'] }
                    }]
                });
                const writable = await handle.createWritable();
                await writable.write(text);
                await writable.close();
                document.getElementById('ojo-status').innerText = '✔️ ¡Archivo guardado con éxito!';
                document.getElementById('ojo-status').style.color = '#25d366';
                alert("¡Archivo guardado con éxito en tu computadora!");
                return;
            } catch (err) {
                if (err.name === 'AbortError') return; // Cancelado por el usuario
                console.warn('showSaveFilePicker no completado, probando descarga estándar...', err);
            }
        }

        // Método 2: Descarga clásica por elemento 'a' con Blob
        try {
            const blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.style.display = 'none';
            a.href = url;
            a.download = filename;
            document.documentElement.appendChild(a);
            a.click();
            setTimeout(() => {
                a.remove();
                URL.revokeObjectURL(url);
            }, 2000);
            document.getElementById('ojo-status').innerText = '✔️ ¡Descarga iniciada!';
            document.getElementById('ojo-status').style.color = '#25d366';
            return;
        } catch (err) {
            console.warn('Blob falló:', err);
        }

        // Método 3: Descarga con Data URI
        try {
            const dataUri = 'data:text/plain;charset=utf-8,' + encodeURIComponent(text);
            const a = document.createElement('a');
            a.style.display = 'none';
            a.href = dataUri;
            a.download = filename;
            document.documentElement.appendChild(a);
            a.click();
            setTimeout(() => a.remove(), 2000);
            return;
        } catch (err) {
            console.warn('Data URI falló:', err);
        }

        // Método 4: Copia de emergencia y visor
        copyToClipboard(text);
        toggleTextView();
        alert("El navegador bloqueó la descarga automática, pero el texto fue COPIADO AL PORTAPAPELES y se muestra abajo para que lo pegues en el Bloc de Notas.");
    }

    function copyToClipboard(text) {
        if (!text) {
            alert("No hay texto para copiar.");
            return;
        }
        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(text).then(() => {
                alert("✔️ ¡Texto copiado al portapapeles con éxito!");
            }).catch(() => fallbackCopy(text));
        } else {
            fallbackCopy(text);
        }
    }

    function fallbackCopy(text) {
        const ta = document.createElement('textarea');
        ta.value = text;
        ta.style.position = 'fixed';
        ta.style.left = '-9999px';
        document.body.appendChild(ta);
        ta.select();
        try {
            document.execCommand('copy');
            alert("✔️ ¡Texto copiado al portapapeles con éxito!");
        } catch (e) {
            toggleTextView();
            alert("Selecciona el texto en la caja inferior y presiona Ctrl+C.");
        }
        document.body.removeChild(ta);
    }

    function toggleTextView() {
        const box = document.getElementById('ojo-preview-box');
        const ta = document.getElementById('ojo-preview-textarea');
        if (box.style.display === 'none') {
            box.style.display = 'block';
            ta.value = lastExportedText;
            ta.select();
        } else {
            box.style.display = 'none';
        }
    }

    // Asignación de clics con stopPropagation para que WhatsApp Web NO los intercepte
    document.getElementById('ojo-btn-download').onclick = (e) => {
        e.preventDefault();
        e.stopPropagation();
        e.stopImmediatePropagation();
        executeSave(lastExportedText, lastFilename);
    };

    document.getElementById('ojo-btn-copy').onclick = (e) => {
        e.preventDefault();
        e.stopPropagation();
        e.stopImmediatePropagation();
        copyToClipboard(lastExportedText);
    };

    document.getElementById('ojo-btn-view').onclick = (e) => {
        e.preventDefault();
        e.stopPropagation();
        e.stopImmediatePropagation();
        toggleTextView();
    };

    // Botones rápidos de rango de fechas
    document.getElementById('ojo-quick-1m').onclick = (e) => {
        e.preventDefault();
        e.stopPropagation();
        const d = new Date(); d.setDate(d.getDate() - 30);
        document.getElementById('ojo-date-from').value = formatDateInput(d);
        document.getElementById('ojo-date-to').value = formatDateInput(new Date());
    };
    document.getElementById('ojo-quick-3m').onclick = (e) => {
        e.preventDefault();
        e.stopPropagation();
        const d = new Date(); d.setDate(d.getDate() - 90);
        document.getElementById('ojo-date-from').value = formatDateInput(d);
        document.getElementById('ojo-date-to').value = formatDateInput(new Date());
    };
    document.getElementById('ojo-quick-all').onclick = (e) => {
        e.preventDefault();
        e.stopPropagation();
        document.getElementById('ojo-date-from').value = "2020-01-01";
        document.getElementById('ojo-date-to').value = formatDateInput(new Date());
    };

    // Iniciar
    document.getElementById('ojo-btn-start').onclick = (e) => {
        e.preventDefault();
        e.stopPropagation();
        checkActiveChatChange();
        const scrollContainer = getScrollContainer();
        if (!scrollContainer) {
            alert("No se detectó un chat abierto. Haz clic en el grupo o conversación que quieras descargar.");
            return;
        }

        document.getElementById('ojo-download-ready-box').style.display = 'none';
        document.getElementById('ojo-preview-box').style.display = 'none';
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
    document.getElementById('ojo-btn-stop').onclick = (e) => {
        e.preventDefault();
        e.stopPropagation();
        const fromVal = document.getElementById('ojo-date-from').value;
        const toVal = document.getElementById('ojo-date-to').value;
        const fromDate = fromVal ? new Date(fromVal + "T00:00:00") : null;
        const toDate = toVal ? new Date(toVal + "T23:59:59") : null;
        finishAndDownload(fromDate, toDate, "Descarga manual");
    };

    // Cerrar panel
    document.getElementById('ojo-btn-close').onclick = (e) => {
        e.preventDefault();
        e.stopPropagation();
        clearInterval(chatWatcher);
        if (timer) clearInterval(timer);
        panel.remove();
    };

    // Funciones de emergencia accesibles desde la consola
    window.descargarChat = () => executeSave(lastExportedText, lastFilename);
    window.copiarChat = () => copyToClipboard(lastExportedText);
})();
