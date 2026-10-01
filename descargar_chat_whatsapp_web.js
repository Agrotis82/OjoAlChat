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
 * - Tarjetas de contacto con su número: abre cada tarjeta (o "Ver todos") y escribe
 *   [CONTACTO: Nombre | +54 9 11 5555-1234]. Expande "Leer más" y no corta antes de tiempo.
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

    // La lista de mensajes es el elemento con scroll más alto de #main. WhatsApp la puede reemplazar
    // mientras carga, así que se busca de nuevo en cada vuelta.
    function getScrollContainer() {
        const main = document.querySelector('#main');
        if (!main) return null;
        let best = null;
        for (const el of main.querySelectorAll('div')) {
            if (el.scrollHeight <= el.clientHeight + 10) continue;
            const style = window.getComputedStyle(el);
            if (style.overflowY !== 'auto' && style.overflowY !== 'scroll') continue;
            if (!best || el.scrollHeight > best.scrollHeight) best = el;
        }
        return best;
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
            <div style="display:flex; justify-content:space-between; margin-bottom:4px;">
                <span style="color:#8696a0;">Contactos compartidos:</span>
                <span id="ojo-contacts" style="font-weight:bold; color:#00a884;">0</span>
            </div>
            <div style="display:flex; justify-content:space-between;">
                <span style="color:#8696a0;">Fecha más antigua leída:</span>
                <span id="ojo-oldest-date" style="font-weight:bold; color:#53bdeb;">-</span>
            </div>
            <div id="ojo-status" style="margin-top:6px; font-size:11px; color:#ffd279; text-align:center;">Listo para iniciar</div>
        </div>

        <div id="ojo-action-box" style="display:flex; flex-direction:column; gap:6px;">
            <button id="ojo-btn-start" style="background:#00a884; color:#111b21; border:none; padding:10px; border-radius:8px; font-weight:bold; cursor:pointer; font-size:13px;">▶ Iniciar Extracción Automática</button>
            <button id="ojo-btn-continue" style="background:#ffd279; color:#111b21; border:none; padding:9px; border-radius:8px; font-weight:bold; cursor:pointer; font-size:12px; display:none;">⏩ Seguir bajando desde donde quedó</button>
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
    let lastProgressAt = Date.now();
    // Orden de captura: cada pasada encuentra mensajes más viejos que la anterior, y dentro de una
    // pasada están en el orden de la pantalla. Con eso el archivo sale del más viejo al más nuevo.
    let passNumber = 0;
    const IDLE_LIMIT_MS = 60000;
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
        contactCache.clear();
        contactsFound = 0;
        contactsWithoutPhone = 0;
        document.getElementById('ojo-count').innerText = '0';
        document.getElementById('ojo-contacts').innerText = '0';
        document.getElementById('ojo-oldest-date').innerText = '-';
        document.getElementById('ojo-status').innerText = statusMsg;
        document.getElementById('ojo-status').style.color = '#53bdeb';
        document.getElementById('ojo-download-ready-box').style.display = 'none';
        document.getElementById('ojo-preview-box').style.display = 'none';
        document.getElementById('ojo-btn-start').style.display = 'block';
        document.getElementById('ojo-btn-stop').style.display = 'none';
        document.getElementById('ojo-btn-continue').style.display = 'none';
    }

    const chatWatcher = setInterval(checkActiveChatChange, 1000);

    document.getElementById('ojo-btn-refresh-chat').onclick = (e) => {
        e.preventDefault();
        e.stopPropagation();
        checkActiveChatChange();
        resetCounters(`Chat actualizado: ${currentChatTitle}`);
    };

    // ---------- Lectura de mensajes, tarjetas de contacto y fechas ----------
    // Probado contra WhatsApp Web el 1/10/2026. Si WhatsApp cambia su HTML, revisar estos selectores.

    const sleep = ms => new Promise(r => setTimeout(r, ms));
    const contactCache = new Map(); // data-id del mensaje -> [{ nombre, telefonos, extras }]
    let contactsFound = 0;
    let contactsWithoutPhone = 0;

    const DIAS = ['domingo', 'lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado'];
    const DIVIDER_RE = /^(hoy|ayer|domingo|lunes|martes|miércoles|miercoles|jueves|viernes|sábado|sabado|\d{1,2}\/\d{1,2}\/\d{2,4})$/i;

    // "Hoy", "Ayer", "domingo" o "8/9/2026", tal como los muestra WhatsApp entre días.
    function parseDivider(text) {
        const t = text.trim().toLowerCase();
        const base = new Date();
        base.setHours(0, 0, 0, 0);
        if (t === 'hoy') return base;
        if (t === 'ayer') { base.setDate(base.getDate() - 1); return base; }
        const dia = DIAS.indexOf(t.replace('miercoles', 'miércoles').replace('sabado', 'sábado'));
        if (dia >= 0) {
            for (let i = 2; i <= 7; i++) {
                const d = new Date(base);
                d.setDate(base.getDate() - i);
                if (d.getDay() === dia) return d;
            }
        }
        return parseMessageDate(t);
    }

    const pad = n => String(n).padStart(2, '0');
    const fmtDate = d => `${d.getDate()}/${d.getMonth() + 1}/${d.getFullYear()}`;

    // El texto propio del mensaje, sin el mensaje citado ni la vista previa de un link.
    function messageText(pre) {
        const spans = [...pre.querySelectorAll('span.selectable-text')].filter(s =>
            !s.closest('[data-testid*="quoted"]') &&
            !s.closest('[aria-label*="itado"]') &&
            !s.closest('[data-testid="link-preview-container"]') &&
            !(s.parentElement && s.parentElement.closest('span.selectable-text'))
        );
        return spans.map(s => s.innerText.trim()).filter(Boolean).join('\n');
    }

    function isClickable(el) {
        return el && el.getBoundingClientRect().width > 0;
    }

    async function waitFor(fn, timeoutMs) {
        const start = Date.now();
        while (Date.now() - start < timeoutMs) {
            const v = fn();
            if (v) return v;
            await sleep(150);
        }
        return null;
    }

    // Lee el cuadro "Ver contacto" o "N contactos": nombre y teléfonos de cada uno.
    async function readContactDialog(dialog) {
        const result = [];
        const seen = new Set();
        const scroller = [...dialog.querySelectorAll('div')].find(d => d.scrollHeight > d.clientHeight + 20 &&
            ['auto', 'scroll'].includes(getComputedStyle(d).overflowY));
        for (let pass = 0; pass < 30; pass++) {
            const nodes = [...dialog.querySelectorAll('[data-testid="cell-frame-title"], div[dir="auto"]')];
            let current = null;
            nodes.forEach(n => {
                if (n.matches('[data-testid="cell-frame-title"]')) {
                    const nombre = n.innerText.trim();
                    current = result.find(c => c.nombre === nombre);
                    if (!current) {
                        current = { nombre, telefonos: [], extras: [] };
                        result.push(current);
                    }
                    return;
                }
                if (!current) return;
                const valueEl = n.querySelector('[data-testid="selectable-text"]');
                if (!valueEl) return;
                const value = valueEl.innerText.trim();
                const label = [...n.children].map(c => c.innerText.trim()).find(t => t && t !== value) || '';
                const key = current.nombre + '|' + value;
                if (!value || seen.has(key)) return;
                seen.add(key);
                if (value.replace(/\D/g, '').length >= 7 && /^[+\d\s()-]+$/.test(value)) {
                    current.telefonos.push(value);
                } else if (/empresa/i.test(label)) {
                    current.extras.push(`empresa: ${value}`);
                }
            });
            if (!scroller || scroller.scrollTop + scroller.clientHeight >= scroller.scrollHeight - 5) break;
            scroller.scrollTop += scroller.clientHeight - 40;
            await sleep(300);
        }
        return result;
    }

    async function closeDialog() {
        const btn = document.querySelector('[role="dialog"] button[aria-label="Cerrar"]');
        if (btn) btn.click();
        // Nunca usar Escape: en WhatsApp Web cierra el chat abierto.
        await waitFor(() => !document.querySelector('[role="dialog"]'), 4000);
    }

    // Abre la tarjeta (un contacto) o "Ver todos" (varios), lee los datos y la cierra.
    async function resolveContacts(row) {
        const id = row.getAttribute('data-id');
        if (contactCache.has(id)) return contactCache.get(id);
        const verTodos = row.querySelector('button[title="Ver todos"]');
        const vcardName = row.querySelector('[data-testid="vcard-msg"] [data-testid="selectable-text"]');
        const opener = verTodos || vcardName;
        let contacts = [];
        if (isClickable(opener)) {
            opener.click();
            const dialog = await waitFor(() => document.querySelector('[role="dialog"]'), 3000);
            if (dialog) {
                await sleep(300);
                contacts = await readContactDialog(dialog);
                await closeDialog();
            }
        }
        if (contacts.length === 0) {
            const nombre = (vcardName || row.querySelector('[title]'))?.innerText?.trim() || 'contacto';
            contacts = [{ nombre, telefonos: [], extras: [] }];
        }
        contactCache.set(id, contacts);
        contactsFound += contacts.length;
        contactsWithoutPhone += contacts.filter(c => c.telefonos.length === 0).length;
        return contacts;
    }

    function contactLine(c) {
        const tel = c.telefonos.length ? c.telefonos.join(' / ') : 'sin número';
        const extras = c.extras.length ? ' | ' + c.extras.join(' | ') : '';
        return `[CONTACTO: ${c.nombre} | ${tel}${extras}]`;
    }

    // Toca "Leer más" en los mensajes visibles, para guardar el texto completo.
    async function expandReadMore() {
        const buttons = [...document.querySelectorAll('#main [data-testid*="read-more"]')].filter(isClickable);
        buttons.forEach(b => b.click());
        if (buttons.length) await sleep(400);
    }

    // Si WhatsApp ofrece traer mensajes anteriores desde el celular, lo toca.
    function clickLoadOlder() {
        const el = [...document.querySelectorAll('#main div, #main button, #main span')].find(e =>
            e.children.length === 0 && /mensajes anteriores/i.test(e.innerText || ''));
        if (el && isClickable(el)) {
            (el.closest('button,[role="button"]') || el).click();
            return true;
        }
        return false;
    }

    async function collectMessages(targetFromDate, targetToDate) {
        const main = document.querySelector('#main');
        if (!main) return;

        await expandReadMore();

        // Mensajes y separadores de día, en el orden en que aparecen.
        const rows = [...main.querySelectorAll('[data-id]')];
        const dividers = [...main.querySelectorAll('span, div')].filter(e =>
            e.children.length === 0 && !e.closest('[data-id]') && DIVIDER_RE.test((e.innerText || '').trim()));
        const items = [...rows, ...dividers].sort((a, b) =>
            a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING ? -1 : 1);

        let currentDate = null;
        passNumber++;
        let position = 0;
        for (const el of items) {
            if (!el.hasAttribute('data-id')) {
                currentDate = parseDivider(el.innerText) || currentDate;
                continue;
            }
            const id = el.getAttribute('data-id');
            const pre = el.querySelector('[data-pre-plain-text]');
            const isContact = !!el.querySelector('[data-testid="vcard-msg"], button[title="Ver todos"]');
            let meta = pre ? pre.getAttribute('data-pre-plain-text') : '';
            let msgDate = pre ? parseMessageDate(meta) : null;
            if (msgDate) currentDate = msgDate;
            else msgDate = currentDate;

            if (!isContact && (!pre || messagesMap.has(id))) continue;
            if (isContact && messagesMap.has(id)) continue;

            if (!meta) {
                // La burbuja de varios contactos no trae fecha ni remitente: se arman igual que las demás.
                const hora = el.querySelector('[data-testid="msg-meta"]')?.innerText.trim().split('\n')[0] || '';
                const autor = el.querySelector('span[aria-label$=":"]')?.getAttribute('aria-label').replace(/:$/, '').trim() || 'Desconocido';
                meta = `[${hora}, ${msgDate ? fmtDate(msgDate) : ''}] ${autor}: `;
            }

            if (msgDate && (!oldestDateFound || msgDate < oldestDateFound)) {
                oldestDateFound = msgDate;
            }

            let lines;
            if (isContact) {
                const contacts = await resolveContacts(el);
                lines = contacts.map(c => `${meta}${contactLine(c)}`);
            } else {
                const text = messageText(pre);
                if (!text) continue;
                lines = [`${meta}${text}`];
            }
            messagesMap.set(id, { fullText: lines.join('\n'), date: msgDate, pass: passNumber, pos: position++ });
        }

        document.getElementById('ojo-count').innerText = messagesMap.size;
        document.getElementById('ojo-contacts').innerText =
            `${contactsFound} (${contactsWithoutPhone} sin número)`;
        if (oldestDateFound) {
            document.getElementById('ojo-oldest-date').innerText = oldestDateFound.toLocaleDateString();
        }

        // Si mientras se leían contactos se detuvo a mano, no seguir.
        if (!isExtracting) return;

        if (messagesMap.size === lastMessagesTotal) {
            consecutiveSameCount++;
            // WhatsApp a veces pide traer los mensajes viejos desde el celular: se toca y se sigue esperando.
            if (clickLoadOlder()) lastProgressAt = Date.now();
            const quieto = Math.round((Date.now() - lastProgressAt) / 1000);
            if (quieto >= 5) {
                document.getElementById('ojo-status').innerText = `⏳ Esperando que WhatsApp cargue más (${quieto} s)…`;
            }
        } else {
            consecutiveSameCount = 0;
            lastMessagesTotal = messagesMap.size;
            lastProgressAt = Date.now();
            document.getElementById('ojo-status').innerText = '🔄 Subiendo y recopilando mensajes...';
        }

        // Parada 1: Fecha alcanzada
        if (targetFromDate && oldestDateFound && oldestDateFound <= targetFromDate) {
            finishAndDownload(targetFromDate, targetToDate, "¡Fecha alcanzada!");
            return;
        }

        // Parada 2: un minuto sin mensajes nuevos. En chats grandes WhatsApp tarda en traer los viejos.
        if (Date.now() - lastProgressAt >= IDLE_LIMIT_MS) {
            finishAndDownload(targetFromDate, targetToDate, "WhatsApp no cargó más mensajes");
            return;
        }
    }

    async function scrollStep(container) {
        if (!container) return;
        // Si hace un rato que no aparece nada, bajar un poco y volver a subir: WhatsApp carga
        // los mensajes viejos cuando ve que se llega arriba, no si ya se está ahí quieto.
        if (consecutiveSameCount > 0 && consecutiveSameCount % 4 === 0) {
            container.scrollTop = Math.min(800, container.scrollHeight);
            await sleep(300);
        }
        container.scrollTop = 0;
        await sleep(150);
        if (container.scrollTop === 0) container.scrollTop = 40;
        container.scrollTop = 0;
    }

    function finishAndDownload(fromDate, toDate, reason) {
        timer = null;
        isExtracting = false;

        const ordered = [...messagesMap.values()].sort((a, b) => (b.pass - a.pass) || (a.pos - b.pos));
        const kept = ordered.filter(item =>
            !item.date || ((!fromDate || item.date >= fromDate) && (!toDate || item.date <= toDate)));
        const filtered = kept.map(item => item.fullText);
        const dates = kept.map(item => item.date).filter(Boolean);

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
        // Las fechas del nombre son las del primer y el último mensaje bajado, no las pedidas.
        const isoLocal = d => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
        const firstDate = dates.length ? new Date(Math.min(...dates)) : null;
        const lastDate = dates.length ? new Date(Math.max(...dates)) : null;
        const fromStr = firstDate ? isoLocal(firstDate) : 'inicio';
        const toStr = lastDate ? isoLocal(lastDate) : 'hoy';
        const stoppedEarly = fromDate && firstDate && firstDate > fromDate;

        lastFilename = `chat_${finalGroupName}_${filtered.length}msgs_${fromStr}_a_${toStr}.txt`;
        lastExportedText = filtered.join('\n\n');

        // Configurar botón de descarga
        const btnDl = document.getElementById('ojo-btn-download');
        btnDl.innerText = `📥 Guardar Archivo (${filtered.length} msgs)`;
        document.getElementById('ojo-download-ready-box').style.display = 'flex';

        if (stoppedEarly) {
            document.getElementById('ojo-status').innerText =
                `⚠️ ${reason}: llegó hasta el ${fmtDate(firstDate)}, no al ${fmtDate(fromDate)}. ` +
                `Tocá "Seguir bajando" para continuar desde ahí (no se pierde lo ya bajado).`;
            document.getElementById('ojo-status').style.color = '#ffd279';
        } else {
            document.getElementById('ojo-status').innerText = `✔️ ${reason} (${filtered.length} msgs listos)`;
            document.getElementById('ojo-status').style.color = '#25d366';
        }
        document.getElementById('ojo-btn-continue').style.display = stoppedEarly ? 'block' : 'none';

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

        messagesMap.clear();
        contactCache.clear();
        contactsFound = 0;
        contactsWithoutPhone = 0;
        oldestDateFound = null;
        passNumber = 0;
        startLoop();
    };

    // Arranca (o retoma) la bajada. Retomar no borra lo ya juntado.
    function startLoop() {
        document.getElementById('ojo-download-ready-box').style.display = 'none';
        document.getElementById('ojo-preview-box').style.display = 'none';
        document.getElementById('ojo-btn-continue').style.display = 'none';
        consecutiveSameCount = 0;
        lastMessagesTotal = messagesMap.size;
        lastProgressAt = Date.now();
        isExtracting = true;

        const fromVal = document.getElementById('ojo-date-from').value;
        const toVal = document.getElementById('ojo-date-to').value;
        const fromDate = fromVal ? new Date(fromVal + "T00:00:00") : null;
        const toDate = toVal ? new Date(toVal + "T23:59:59") : null;

        document.getElementById('ojo-btn-start').style.display = 'none';
        document.getElementById('ojo-btn-stop').style.display = 'block';
        document.getElementById('ojo-status').innerText = '🔄 Subiendo y recopilando mensajes...';
        document.getElementById('ojo-status').style.color = '#ffd279';

        // Un paso a la vez: abrir tarjetas de contacto lleva tiempo y no se puede pisar con el siguiente.
        timer = true;
        (async () => {
            while (timer) {
                await collectMessages(fromDate, toDate);
                if (!timer) break;
                await scrollStep(getScrollContainer());
                await sleep(750);
            }
        })();
    }

    document.getElementById('ojo-btn-continue').onclick = (e) => {
        e.preventDefault();
        e.stopPropagation();
        if (!getScrollContainer()) {
            alert("No se detectó el chat abierto. Volvé a abrir el mismo grupo y tocá de nuevo.");
            return;
        }
        startLoop();
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
        timer = null;
        isExtracting = false;
        panel.remove();
    };

    // Funciones de emergencia accesibles desde la consola
    // Para probar sin descargar: lee lo que está en pantalla y devuelve las líneas.
    window.ojoLeerPantalla = async () => {
        isExtracting = true;
        await collectMessages(null, null);
        isExtracting = false;
        return [...messagesMap.values()].map(m => m.fullText);
    };
    window.descargarChat = () => executeSave(lastExportedText, lastFilename);
    window.copiarChat = () => copyToClipboard(lastExportedText);
})();
