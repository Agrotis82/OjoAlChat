import io
import os
import re
import importlib
import pandas as pd
import streamlit as st
import parser as parser_module
import extractor as extractor_module
importlib.reload(parser_module)
importlib.reload(extractor_module)
from parser import WhatsAppParser, ChatMessage, extraer_contactos
from extractor import WhatsAppInsightExtractor
from proveedores_ia import PROVEEDORES, SERVICIOS_COMPATIBLES

st.set_page_config(
    page_title="OjoAlChat | OjoAI",
    page_icon="👁️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("👁️ OjoAlChat (OjoAI)")
st.caption("El ojo con Inteligencia Artificial que ve, analiza y encuentra cualquier dato, persona, video o archivo en tus chats.")

def extract_chat_name(filename: str) -> str:
    base = os.path.splitext(os.path.basename(filename))[0]
    cleaned = re.sub(r'^(?:chat_whatsapp_|chat_|whatsapp chat\s*-\s*)', '', base, flags=re.I)
    cleaned = re.sub(r'_\d+msgs_.*$', '', cleaned, flags=re.I)
    cleaned = re.sub(r'-\d{4}-\d{2}-\d{2}.*$', '', cleaned, flags=re.I)
    cleaned = cleaned.replace('_', ' ').strip()
    return cleaned if cleaned else base

# 1. Proveedor de IA, clave y modelo (la clave puede venir de Streamlit Secrets o de variables de entorno)
def clave_guardada(variables):
    for nombre in variables:
        try:
            if hasattr(st, "secrets") and nombre in st.secrets:
                return st.secrets[nombre]
        except Exception:
            pass
        if os.environ.get(nombre):
            return os.environ[nombre]
    return ""

with st.sidebar:
    st.header("⚙️ Configuración")

    provider_id = st.selectbox(
        "Empresa de IA",
        list(PROVEEDORES.keys()),
        format_func=lambda k: PROVEEDORES[k]["nombre"],
        help="OjoAlChat funciona con cualquiera de estas. Cada una cobra (o regala) según su propio plan."
    )
    proveedor = PROVEEDORES[provider_id]
    base_url = None

    if provider_id == "compatible":
        servicio = st.selectbox("Servicio", list(SERVICIOS_COMPATIBLES.keys()) + ["Otro (escribir dirección)"])
        if servicio in SERVICIOS_COMPATIBLES:
            base_url = SERVICIOS_COMPATIBLES[servicio]
        else:
            base_url = st.text_input("Dirección de la API", placeholder="https://…/v1")

    api_key = st.text_input(
        f"API Key de {proveedor['nombre'].split(' (')[0]}",
        value=clave_guardada(proveedor["variables"]),
        type="password",
        help="Se usa solo para esta sesión; no se guarda en ningún lado."
    )
    if provider_id == "compatible" and base_url and "localhost" in base_url and not api_key:
        api_key = "ollama"  # Ollama en la misma computadora no pide clave

    if not api_key:
        st.warning("⚠️ Ingresa una API Key para habilitar la extracción con IA.")
        if proveedor["clave_url"]:
            st.markdown(f"[👉 Obtener una API Key]({proveedor['clave_url']})")

    if provider_id == "gemini":
        model_options = [
            "⚡ Automático (Recomendado: Gemini 3.5 Flash-Lite ➔ 3.5 Flash ➔ 3.8 Flash)",
            "gemini-3.5-flash-lite",
            "gemini-3.5-flash",
            "gemini-3.8-flash",
            "gemini-3.7-flash",
            "gemini-3.6-flash",
        ]
        model_selection = st.selectbox(
            "Modelo de IA",
            model_options,
            index=0,
            help="En modo Automático, OjoAlChat utiliza el modelo más rápido y optimizado para chats (Gemini 3.5 Flash-Lite, ~1.5s por lote). Si Google presenta saturación de demanda, desciende automáticamente a 3.5 Flash o 3.8 Flash sin detener la búsqueda."
        )
        model_choice = "gemini-3.5-flash-lite" if "Automático" in model_selection else model_selection
    elif provider_id == "anthropic":
        model_choice = st.selectbox(
            "Modelo de IA",
            proveedor["modelos"],
            index=0,
            help="Opus es el más capaz; Sonnet y Haiku son más rápidos y más baratos."
        )
    else:
        model_choice = st.text_input(
            "Modelo de IA",
            placeholder="El nombre exacto que figura en la página del servicio",
            help="Por ejemplo, el modelo que tengas habilitado en tu cuenta de OpenAI, o el que descargaste en Ollama."
        ).strip()
    
    st.divider()
    st.subheader("📁 Carga de Chats")
    load_mode = st.radio(
        "Modo de carga",
        ["Subir archivos (.txt)", "Pegar texto copiado"],
        horizontal=True,
        label_visibility="collapsed"
    )

    uploaded_files = []
    pasted_text = ""
    pasted_chat_name = ""

    if load_mode == "Subir archivos (.txt)":
        uploaded_files = st.file_uploader(
            "Sube uno o varios chats (.txt)",
            type=["txt"],
            accept_multiple_files=True,
            help="Exporta tus chats de WhatsApp como archivos .txt y súbelos aquí. ¡Puedes seleccionar varios manteniendo presionada la tecla Ctrl/Cmd!"
        )
    else:
        pasted_chat_name = st.text_input("Nombre del chat/grupo", value="Ventas y proveedores")
        pasted_text = st.text_area(
            "Pega los mensajes aquí (Ctrl+V)",
            height=180,
            placeholder="[29/9/2026, 14:49:10] Juan: Recomiendo a Pedro Plomero 11223344\n[29/9/2026, 14:50:00] María: ¡Gracias!"
        )

    # Acceso rápido si existe archivo local de prueba
    local_path = r"C:\Users\Agos\DocumentosAgos\Datito\chat_whatsapp_vecinasmolineras-2026-09-30desde030206.txt"
    if os.path.exists(local_path) and not uploaded_files and not pasted_text.strip():
        if st.button("📁 Cargar chat de demostración (3.300 msgs)"):
            st.session_state["use_local_default"] = True

    pre_extracted_xlsx = r"C:\Users\Agos\DocumentosAgos\Datito\proveedores_recomendados_whatsapp.xlsx"
    if os.path.exists(pre_extracted_xlsx):
        if st.button("📊 Ver planilla de ejemplo ya extraída"):
            st.session_state["recom_df"] = pd.read_excel(pre_extracted_xlsx)
            st.session_state["use_local_default"] = True

# Lectura y consolidación de mensajes de múltiples chats
loaded_chats_info = []
messages = []
parser = WhatsAppParser()

if uploaded_files:
    for f in uploaded_files:
        chat_name = extract_chat_name(f.name)
        raw_bytes = f.getvalue() if hasattr(f, "getvalue") else f.read()
        text = raw_bytes.decode("utf-8", errors="ignore") if isinstance(raw_bytes, bytes) else str(raw_bytes)
        chat_msgs = parser.parse(text)
        for m in chat_msgs:
            m.source_chat = chat_name
        messages.extend(chat_msgs)
        loaded_chats_info.append({
            "Chat / Grupo": chat_name,
            "Archivo": f.name,
            "Mensajes": len(chat_msgs)
        })
elif pasted_text.strip():
    chat_name = pasted_chat_name.strip() or "Chat Pegado"
    chat_msgs = parser.parse(pasted_text)
    for m in chat_msgs:
        m.source_chat = chat_name
    messages.extend(chat_msgs)
    loaded_chats_info.append({
        "Chat / Grupo": chat_name,
        "Archivo": "Texto pegado directamente",
        "Mensajes": len(chat_msgs)
    })
elif st.session_state.get("use_local_default", False) and os.path.exists(local_path):
    chat_name = "Vecinas Molineras"
    with open(local_path, "r", encoding="utf-8", errors="ignore") as f:
        text = f.read()
    chat_msgs = parser.parse(text)
    for m in chat_msgs:
        m.source_chat = chat_name
    messages.extend(chat_msgs)
    loaded_chats_info.append({
        "Chat / Grupo": chat_name,
        "Archivo": os.path.basename(local_path),
        "Mensajes": len(chat_msgs)
    })

if not messages:
    st.info("👋 **Bienvenido**: Para comenzar, sube uno o varios archivos `.txt` de chats de WhatsApp en la barra lateral izquierda.")
    st.markdown("""
    ### 💡 ¿Cómo analizar múltiples grupos a la vez?
    1. Descarga o exporta los chats que quieras (por ejemplo: *Proveedores*, *Vecinos*, *Seguridad*).
    2. En el botón **'Browse files'** de la barra lateral, puedes **seleccionar varios archivos a la vez** manteniendo presionada la tecla `Ctrl` (o `Cmd` en Mac).
    3. OjoAlChat unificará todos los mensajes y la IA buscará de forma cruzada en todos los grupos.
    
    ### ¿Cómo exportar un chat de WhatsApp?
    * **En la computadora (WhatsApp Web)**: Ejecuta el script extractor en la consola del navegador y haz clic en el botón verde **'📥 DESCARGAR ARCHIVO'**.
    * **En el celular**: Abre el chat o grupo > Menú (3 puntos o info) > Más > **Exportar chat (Sin archivos)**.
    """)
    st.stop()
else:
    # Métricas consolidadas
    senders = list(set(m.sender for m in messages))
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Chats Cargados", len(loaded_chats_info))
    col2.metric("Mensajes Totales", f"{len(messages):,}")
    col3.metric("Participantes", len(senders))
    col4.metric("Rango de Fechas", f"{messages[0].date} ➔ {messages[-1].date}" if messages else "-")

    # Chats bajados con el script viejo: el contacto compartido queda sin número y la IA confunde
    # a la vecina que lo compartió con el proveedor.
    old_format = [
        m for m in messages
        if "[CONTACTO:" not in m.text and re.search(r"^(Mensaje|Guardar contacto|Ver la empresa)$", m.text, re.M)
    ]
    if old_format:
        chats_viejos = sorted(set(m.source_chat for m in old_format))
        st.warning(
            f"⚠️ {len(old_format)} contactos compartidos vienen sin número en: {', '.join(chats_viejos)}. "
            "Estos chats se bajaron con la versión vieja del script: la IA puede tomar a la vecina que compartió "
            "el contacto como si fuera el proveedor. Bajalos de nuevo con el script actual (en el panel tiene que "
            "aparecer 'Contactos compartidos')."
        )

    if len(loaded_chats_info) > 1:
        with st.expander("📁 Detalle de los chats unificados", expanded=False):
            st.dataframe(pd.DataFrame(loaded_chats_info), use_container_width=True, hide_index=True)

    tab_universal, tab_recom, tab_contactos, tab_chat = st.tabs([
        "🔍 Búsqueda Universal (Cualquier Chat o Pregunta)",
        "🛠️ Plantilla: Directorio de Profesionales",
        "📇 Contactos compartidos",
        "📜 Explorador de Mensajes"
    ])

    total_m = len(messages)
    slider_min = max(1, min(50, total_m // 2)) if total_m > 1 else 1
    slider_step = max(1, min(100, total_m // 10)) if total_m > 50 else 1

    # ----------------- TAB 1: BÚSQUEDA UNIVERSAL LIBRE -----------------
    with tab_universal:
        st.subheader("🔍 Ojo Universal: Pregunta o Busca Cualquier Cosa en tus Chats")
        st.write(
            "Escribe en tus propias palabras qué necesitas encontrar o saber. "
            "OjoAlChat responderá directamente tu pregunta en lenguaje natural y creará una planilla con la evidencia y fuentes encontradas."
        )

        st.markdown("**Ideas y casos de uso populares (haz clic para autocompletar):**")
        ex_r1 = st.columns(3)
        if ex_r1[0].button("🔨 Proveedores Detallados"):
            st.session_state["search_query_input"] = (
                "Extraé cada vez que alguien del chat recomienda a un proveedor de servicios para la casa, la familia o eventos. "
                "Una fila por recomendación: si dos personas recomiendan al mismo, van dos filas. "
                "Usá exactamente estas columnas: proveedor_nombre, proveedor_apellido, rubro, telefono_proveedor, recomienda, chat, fecha, motivo, cita_o_fuente.\n"
                "- telefono_proveedor: SOLO el número del proveedor, que aparece en el texto del mensaje o en un contacto compartido. NUNCA el número de quien escribe el mensaje. Si no aparece, vacío.\n"
                "- recomienda: quien escribió el mensaje, tal como aparece en el chat.\n"
                "- rubro: uno de esta lista, escrito igual: Albañil, Carpintero, Cerrajero, Electricista, Gasista matriculado, Mantenimiento general, Pintor, Plomero, Técnico de aire acondicionado, Técnico de calderas, Técnico de electrodomésticos, Fumigador, Herrero, Jardinero, Lavado de autos, Limpiavidrios, Paisajista, Piletero, Techista, Empleada doméstica, Limpieza, Niñera, Paseador de perros, Profesor particular, Veterinario, Animación infantil, Catering, DJ, Fotógrafo, Salón de eventos, Otros."
            )
        if ex_r1[1].button("🏫 Escuela / Padres"):
            st.session_state["search_query_input"] = "Extrae todas las reuniones de padres, eventos escolares, fechas límite, cuotas o pagos informados con fechas y detalles"
        if ex_r1[2].button("🏢 Consorcio / Edificio"):
            st.session_state["search_query_input"] = "Busca todos los reclamos de mantenimiento, humedad, cortes de agua/luz, ruidos molestos y asambleas con fecha y depto"

        ex_r2 = st.columns(3)
        if ex_r2[0].button("💼 Trabajo y Proyectos"):
            st.session_state["search_query_input"] = "Extrae las decisiones clave tomadas, acuerdos alcanzados, links de documentos y tareas asignadas con responsables"
        if ex_r2[1].button("🍖 Asado / Evento"):
            st.session_state["search_query_input"] = "Lista quiénes confirmaron que van, qué comida o bebida se comprometió a llevar cada uno y montos de dinero recaudados"
        if ex_r2[2].button("🛍️ Compra y Venta"):
            st.session_state["search_query_input"] = "Extrae todos los productos ofrecidos a la venta (autos, muebles, electrodomésticos, etc.) con precio y contacto"

        chats_disponibles_u = [info["Chat / Grupo"] for info in loaded_chats_info]
        if len(chats_disponibles_u) > 1:
            chats_a_buscar_u = st.multiselect(
                "📂 Buscar en los siguientes chats:",
                chats_disponibles_u,
                default=chats_disponibles_u,
                key="multiselect_chats_universal",
                help="Puedes buscar de forma cruzada en todos los grupos o desmarcar alguno para buscar en uno solo."
            )
        else:
            chats_a_buscar_u = chats_disponibles_u

        active_pool_u = [m for m in messages if not chats_a_buscar_u or m.source_chat in chats_a_buscar_u]
        pool_u_len = len(active_pool_u)

        default_query = st.session_state.get("search_query_input", "")
        query = st.text_area(
            "¿Qué deseas encontrar o preguntar a los chats?",
            value=default_query,
            placeholder="Ej: '¿Quién dijo que vendía una heladera y cuánto pedía?' o '¿A qué hora dijeron que abre la pileta?' o 'Extrae todos los cumpleaños mencionados'",
            height=90
        )

        col_btn_u, col_slider_u = st.columns([1, 3])
        with col_btn_u:
            btn_universal = st.button("🚀 Buscar con IA", type="primary", disabled=not (bool(api_key) and bool(query.strip())))
        with col_slider_u:
            if pool_u_len > 1:
                sample_size = st.slider(
                    "Cantidad de mensajes recientes a analizar",
                    min_value=max(1, min(50, pool_u_len // 2)),
                    max_value=pool_u_len,
                    value=pool_u_len,
                    step=1,
                    key="slider_universal",
                    help="Por defecto se analiza el 100% de los mensajes de los chats seleccionados."
                )
            else:
                sample_size = pool_u_len

        if btn_universal:
            try:
                selected_slice = active_pool_u[-sample_size:] if sample_size < pool_u_len else active_pool_u
                total_to_process = len(selected_slice)

                prog_bar_u = st.progress(0, text="Iniciando búsqueda inteligente...")
                status_box_u = st.empty()

                def update_progress_u(step, total, pct, count, msg, current_model=""):
                    current_lote = min(step + 1, total) if pct < 100 else total
                    prog_bar_u.progress(min(pct, 100), text=f"Progreso: {pct}% — Lote {current_lote} de {total}")
                    tag_model = f" | 🧠 Modelo IA: `{current_model}`" if current_model else ""
                    if count == 0 and step == 0:
                        status_box_u.info(f"⏳ {msg}{tag_model} | 🔍 Extrayendo datos con IA (el contador se actualizará al completar cada lote)...")
                    else:
                        status_box_u.info(f"⏳ {msg}{tag_model} | Registros detectados hasta ahora: **{count}**")

                extractor = WhatsAppInsightExtractor(api_key=api_key, model=model_choice, provider=provider_id, base_url=base_url)
                result = extractor.extract_dynamic_query_batched(
                    selected_slice,
                    query,
                    chunk_size=80,
                    progress_callback=update_progress_u
                )

                prog_bar_u.empty()
                status_box_u.empty()

                st.session_state["custom_result_full"] = result

                # Detectar modelo(s) utilizados
                used_models = result.get("modelos_usados") or extractor.last_models_used or [model_choice]
                used_models_str = ", ".join([f"`{m}`" for m in used_models])
                if extractor.fallback_occurred or (len(used_models) > 1) or (used_models and used_models[0] != model_choice):
                    model_note = " *(se activó respaldo por saturación momentánea en el modelo inicial)*"
                else:
                    model_note = ""

                st.session_state["custom_model_display"] = f"{used_models_str}{model_note}"

                filas = result.get("filas", [])
                if filas:
                    st.success(f"🎉 ¡Búsqueda completada con **{used_models_str}**{model_note}! Se encontraron datos relevantes y **{len(filas)}** registros.")
                else:
                    st.info(f"Búsqueda completada con **{used_models_str}**{model_note}.")
            except Exception as e:
                st.error(f"Error durante el procesamiento: {e}")

        if "custom_result_full" in st.session_state:
            res_data = st.session_state["custom_result_full"]
            direct_ans = str(res_data.get("respuesta_directa", "")).strip()
            filas = res_data.get("filas", [])
            used_models_info = st.session_state.get("custom_model_display", "")

            descartados = res_data.get("telefonos_descartados", 0)
            if descartados:
                st.caption(f"📵 Se vaciaron {descartados} teléfono(s) que la IA había tomado de quien escribió el mensaje, no del proveedor.")

            errores_lotes = res_data.get("errores_lotes", [])
            if errores_lotes:
                st.caption(f"ℹ️ *Nota técnica: Hubo una interrupción transitoria en {len(errores_lotes)} lote(s) debido a saturación temporal de red, pero se extrajeron los registros del resto de los mensajes exitosamente.*")

            if direct_ans:
                st.markdown("### 💡 Conclusiones Consolidadas de la IA")
                if used_models_info:
                    st.caption(f"🧠 **Procesado con modelo de IA:** {used_models_info}")
                with st.container(border=True):
                    st.markdown(direct_ans)

            if filas:
                st.markdown("### 📊 Tabla Estructurada con Evidencias")
                if used_models_info and not direct_ans:
                    st.caption(f"🧠 **Procesado con modelo de IA:** {used_models_info}")
                df_custom = pd.DataFrame(filas)
                st.dataframe(df_custom, use_container_width=True)

                col_d1, col_d2, col_d3 = st.columns(3)
                with col_d1:
                    buf = io.BytesIO()
                    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
                        df_custom.to_excel(writer, index=False, sheet_name="Resultados_Totales")
                        # Si hay chats de origen variados, agregar pestañas por chat
                        if "chat_origen" in df_custom.columns:
                            chats_in_custom = [c for c in df_custom["chat_origen"].dropna().unique() if str(c).strip()]
                            if len(chats_in_custom) > 1:
                                for c_val in chats_in_custom:
                                    df_sub = df_custom[df_custom["chat_origen"] == c_val]
                                    safe_name = re.sub(r'[\\/*?:\[\]]', '', str(c_val))[:30]
                                    df_sub.to_excel(writer, index=False, sheet_name=safe_name)

                    st.download_button(
                        "📥 Descargar Excel (.xlsx)",
                        data=buf.getvalue(),
                        file_name="busqueda_ojoalchat.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )
                with col_d2:
                    csv_b = df_custom.to_csv(index=False).encode("utf-8-sig")
                    st.download_button("📥 Descargar CSV", data=csv_b, file_name="busqueda_ojoalchat.csv", mime="text/csv")
                with col_d3:
                    tsv_u = df_custom.to_csv(sep="\t", index=False)
                    st.text_area("📋 Copiar y pegar a Excel / Google Sheets", tsv_u, height=70)

    # ----------------- TAB 2: RECOMENDADOS (GOOGLE SHEETS) -----------------
    with tab_recom:
        st.subheader("Planilla Estructurada de Proveedores (Google Sheets)")
        st.write(
            "Extrae profesionales con el formato exacto de tu planilla: "
            "`nombre, apellido, rubro, telefono, barrio, motivo, avisado, notas` (y chat de origen si hay varios)."
        )
        st.info("💡 **Procesamiento inteligente por lotes activado**: OjoAlChat analiza todos los chats en bloques automáticos de 200 mensajes para sortear cualquier límite de salida y acelerar el tiempo de respuesta. Si un profesional aparece en varios chats o mensajes, se unifican sus datos y elogios automáticamente.")

        chats_disponibles = [info["Chat / Grupo"] for info in loaded_chats_info]
        if len(chats_disponibles) > 1:
            chats_a_analizar = st.multiselect(
                "📂 Seleccionar chats a incluir en el análisis:",
                chats_disponibles,
                default=chats_disponibles,
                help="Puedes seleccionar 'Todos' o elegir analizar un solo chat por separado."
            )
        else:
            chats_a_analizar = chats_disponibles

        active_pool_messages = [m for m in messages if not chats_a_analizar or m.source_chat in chats_a_analizar]
        pool_len = len(active_pool_messages)

        col_btn_r, col_slider_r = st.columns([1, 3])
        with col_btn_r:
            start_recom = st.button("🚀 Extraer Proveedores con IA", disabled=not bool(api_key))
        with col_slider_r:
            if pool_len > 1:
                chunk_r = st.slider(
                    "Mensajes a procesar",
                    min_value=max(1, min(50, pool_len // 2)),
                    max_value=pool_len,
                    value=pool_len,
                    step=1,
                    key="recom_slider",
                    help="Por defecto se analiza el 100% de los mensajes de los chats seleccionados."
                )
            else:
                chunk_r = pool_len

        if start_recom:
            try:
                selected_slice = active_pool_messages[-chunk_r:] if chunk_r < pool_len else active_pool_messages
                total_to_process = len(selected_slice)

                prog_bar_r = st.progress(0, text="Iniciando extracción inteligente en lotes...")
                status_box_r = st.empty()

                def update_progress_r(step, total, pct, count, msg, current_model=""):
                    current_lote = min(step + 1, total) if pct < 100 else total
                    prog_bar_r.progress(min(pct, 100), text=f"Progreso: {pct}% — Lote {current_lote} de {total}")
                    tag_model = f" | 🧠 Modelo IA: `{current_model}`" if current_model else ""
                    if count == 0 and step == 0:
                        status_box_r.info(f"⏳ {msg}{tag_model} | 🔍 Extrayendo datos con IA (el contador se actualizará al completar cada lote)...")
                    else:
                        status_box_r.info(f"⏳ {msg}{tag_model} | Menciones detectadas hasta el momento: **{count}**")

                extractor = WhatsAppInsightExtractor(api_key=api_key, model=model_choice, provider=provider_id, base_url=base_url)
                results_raw = extractor.extract_recommendations_batched(
                    selected_slice,
                    chunk_size=80,
                    deduplicate=False,
                    progress_callback=update_progress_r
                )

                prog_bar_r.empty()
                status_box_r.empty()

                used_models = extractor.last_models_used or [model_choice]
                used_models_str = ", ".join([f"`{m}`" for m in used_models])
                if extractor.fallback_occurred or (len(used_models) > 1) or (used_models and used_models[0] != model_choice):
                    model_note = " *(se activó respaldo por saturación momentánea en el modelo inicial)*"
                else:
                    model_note = ""

                st.session_state["recom_model_display"] = f"{used_models_str}{model_note}"
                if extractor.telefonos_descartados:
                    st.caption(f"📵 Se vaciaron {extractor.telefonos_descartados} teléfono(s) que la IA había tomado de quien escribió el mensaje, no del proveedor.")

                if results_raw:
                    st.session_state["raw_recommendations"] = results_raw
                    # Generar df inicial deduplicado para mantener compatibilidad
                    df_init = pd.DataFrame(extractor_module.deduplicate_recommendations(results_raw))
                    st.session_state["recom_df"] = df_init
                    st.success(f"🎉 ¡Extracción completada con **{used_models_str}**{model_note}! Se detectaron **{len(results_raw)}** menciones individuales y **{len(df_init)}** proveedores únicos.")
                else:
                    st.warning(f"No se encontraron recomendaciones en los mensajes analizados (Modelo: {used_models_str}).")
            except Exception as e:
                st.error(f"Error: {e}")

        # Visualización y filtros
        if "raw_recommendations" in st.session_state or "recom_df" in st.session_state:
            raw_data = st.session_state.get("raw_recommendations")
            if not raw_data and "recom_df" in st.session_state:
                raw_data = st.session_state["recom_df"].to_dict(orient="records")

            st.divider()
            recom_model_info = st.session_state.get("recom_model_display", "")
            if recom_model_info:
                st.caption(f"🧠 **Extracción realizada con modelo de IA:** {recom_model_info}")
            st.markdown("### 👁️ Opciones de Vista y Separación de Datos")

            col_v1, col_v2, col_v3 = st.columns([2, 2, 2])

            with col_v1:
                view_mode = st.radio(
                    "Modo de presentación:",
                    [
                        "👥 Proveedores Consolidados (1 por persona/teléfono)",
                        "📋 Menciones Individuales (ver cada recomendación por separado)"
                    ],
                    index=0,
                    help="Elige si quieres agrupar los duplicados o ver cada vez que alguien recomendó a alguien en el chat."
                )

            # Detectar lista de chats presentes
            detected_chats = sorted(list(set(
                str(r.get("chat_origen", "")).strip() 
                for r in raw_data 
                if str(r.get("chat_origen", "")).strip()
            )))
            for c_info in loaded_chats_info:
                cn = c_info["Chat / Grupo"]
                if cn not in detected_chats:
                    detected_chats.append(cn)

            with col_v2:
                chat_filter = st.selectbox(
                    "Filtrar por Chat / Grupo:",
                    ["Todos los chats"] + detected_chats,
                    help="Permite ver únicamente las recomendaciones originadas en un chat específico."
                )

            # Detectar rubros disponibles
            detected_rubros = sorted(list(set(
                str(r.get("rubro", "")).strip()
                for r in raw_data
                if str(r.get("rubro", "")).strip()
            )))

            with col_v3:
                rubro_filter = st.selectbox(
                    "Filtrar por Rubro:",
                    ["Todos los rubros"] + detected_rubros
                )

            # Filtrar y preparar dataset visible
            if "Consolidados" in view_mode:
                if chat_filter != "Todos los chats":
                    pool = [r for r in raw_data if chat_filter.lower() in str(r.get("chat_origen", "")).lower()]
                    active_records = extractor_module.deduplicate_recommendations(pool)
                else:
                    active_records = extractor_module.deduplicate_recommendations(raw_data)
            else:
                if chat_filter != "Todos los chats":
                    active_records = [r for r in raw_data if chat_filter.lower() in str(r.get("chat_origen", "")).lower()]
                else:
                    active_records = list(raw_data)

            if rubro_filter != "Todos los rubros":
                active_records = [r for r in active_records if str(r.get("rubro", "")).strip() == rubro_filter]

            df_display = pd.DataFrame(active_records)
            base_cols = ["nombre", "apellido", "rubro", "telefono", "barrio", "motivo", "avisado", "notas"]
            has_chats_col = any(r.get("chat_origen") for r in active_records) or len(loaded_chats_info) > 1
            display_cols = base_cols + (["chat_origen"] if has_chats_col and "chat_origen" in df_display.columns else [])
            for c in display_cols:
                if c not in df_display.columns:
                    df_display[c] = ""
            df_display = df_display[display_cols]

            st.caption(f"Mostrando **{len(df_display)}** registros — *{view_mode.split('(')[0].strip()}* | Chat: *{chat_filter}*")
            st.data_editor(df_display, num_rows="dynamic", use_container_width=True)

            col_r1, col_r2, col_r3 = st.columns(3)
            with col_r1:
                # Excel con múltiples hojas para tener todas las vistas por separado
                buf_r = io.BytesIO()
                with pd.ExcelWriter(buf_r, engine="openpyxl") as writer:
                    df_display.to_excel(writer, index=False, sheet_name="Vista_Filtrada")
                    # Hoja consolidada completa
                    df_full_cons = pd.DataFrame(extractor_module.deduplicate_recommendations(raw_data))
                    for c in display_cols:
                        if c not in df_full_cons.columns:
                            df_full_cons[c] = ""
                    df_full_cons[display_cols].to_excel(writer, index=False, sheet_name="Consolidado_Total")
                    # Hoja menciones individuales
                    df_full_raw = pd.DataFrame(raw_data)
                    for c in display_cols:
                        if c not in df_full_raw.columns:
                            df_full_raw[c] = ""
                    df_full_raw[display_cols].to_excel(writer, index=False, sheet_name="Menciones_Individuales")
                    # Una hoja por cada chat individual
                    for cn in detected_chats:
                        chat_items = [r for r in raw_data if cn.lower() in str(r.get("chat_origen", "")).lower()]
                        if chat_items:
                            df_c = pd.DataFrame(chat_items)
                            for c in display_cols:
                                if c not in df_c.columns:
                                    df_c[c] = ""
                            safe_name = re.sub(r'[\\/*?:\[\]]', '', cn)[:30]
                            df_c[display_cols].to_excel(writer, index=False, sheet_name=safe_name)

                st.download_button(
                    "📥 Descargar Excel Multi-Hoja (.xlsx)",
                    data=buf_r.getvalue(),
                    file_name="proveedores_recomendados_completo.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    help="Incluye pestañas separadas: Vista Actual, Consolidado Total, Menciones Individuales y una pestaña por cada chat."
                )
            with col_r2:
                st.download_button(
                    "📥 Descargar Vista en CSV",
                    data=df_display.to_csv(index=False).encode("utf-8-sig"),
                    file_name="proveedores_recomendados_vista.csv",
                    mime="text/csv",
                )
            with col_r3:
                df_for_sheets = df_display[[c for c in base_cols if c in df_display.columns]]
                tsv_text = df_for_sheets.to_csv(sep="\t", index=False)
                st.text_area("📋 Copiar y pegar a Google Sheets (vista actual)", tsv_text, height=70)

    # ----------------- TAB: CONTACTOS COMPARTIDOS (SIN IA) -----------------
    with tab_contactos:
        st.subheader("📇 Todas las tarjetas de contacto compartidas")
        st.write(
            "Sale directo de los chats, sin IA: no se pierde ninguna. Cada fila es una tarjeta de contacto, "
            "con quién la compartió y el pedido al que probablemente respondía."
        )
        contactos = extraer_contactos(messages)
        if not contactos:
            st.info(
                "No hay tarjetas de contacto en estos chats. Si en el grupo se compartieron contactos, "
                "bajalo de nuevo con el script actual (en el panel tiene que aparecer 'Contactos compartidos')."
            )
        else:
            df_c = pd.DataFrame(contactos)
            sin_tel = int((df_c["telefono"] == "").sum())
            c1, c2, c3 = st.columns(3)
            c1.metric("Tarjetas compartidas", len(df_c))
            c2.metric("Contactos distintos", df_c["telefono"].replace("", pd.NA).dropna().nunique())
            c3.metric("Sin número", sin_tel)
            st.dataframe(df_c, use_container_width=True, hide_index=True)
            st.download_button(
                "📥 Descargar CSV",
                data=df_c.to_csv(index=False).encode("utf-8-sig"),
                file_name="contactos_compartidos.csv",
                mime="text/csv",
            )
            st.caption("⚠️ La columna 'compartio' tiene los números de los vecinos: no subas este archivo a lugares compartidos.")

    # ----------------- TAB 3: VER CHAT LIMPIO -----------------
    with tab_chat:
        st.subheader("Historial de Mensajes Limpio")
        
        col_fc1, col_fc2 = st.columns([1, 2])
        with col_fc1:
            chat_names_list = ["Todos los chats"] + [info["Chat / Grupo"] for info in loaded_chats_info]
            selected_chat = st.selectbox("Filtrar por grupo/chat", chat_names_list)
        with col_fc2:
            search_q = st.text_input("Filtrar mensajes por texto o participante", "")

        filtered_msgs = messages
        if selected_chat != "Todos los chats":
            filtered_msgs = [m for m in filtered_msgs if m.source_chat == selected_chat]
        if search_q.strip():
            q_lower = search_q.lower()
            filtered_msgs = [m for m in filtered_msgs if q_lower in m.text.lower() or q_lower in m.sender.lower()]

        st.write(f"Mostrando {min(len(filtered_msgs), 150)} de {len(filtered_msgs)} mensajes encontrados:")
        preview_text = "\n\n".join([m.to_formatted_str() for m in filtered_msgs[:150]])
        st.text_area("Mensajes", preview_text, height=450)
