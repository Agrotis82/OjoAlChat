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
from parser import WhatsAppParser, ChatMessage
from extractor import WhatsAppInsightExtractor

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

# 1. Api Key Configuration (Local or Streamlit Secrets)
api_key_default = ""
try:
    if hasattr(st, "secrets") and "GEMINI_API_KEY" in st.secrets:
        api_key_default = st.secrets["GEMINI_API_KEY"]
except Exception:
    pass

if not api_key_default:
    api_key_default = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or ""

with st.sidebar:
    st.header("⚙️ Configuración")
    
    api_key = st.text_input(
        "API Key de Gemini",
        value=api_key_default,
        type="password",
        help="Obtén tu API key gratuita en https://aistudio.google.com/apikey"
    )
    
    if not api_key:
        st.warning("⚠️ Ingresa una API Key para habilitar la extracción con IA.")
        st.markdown("[👉 Obtener API Key gratis en Google AI Studio](https://aistudio.google.com/apikey)")
    
    model_choice = st.selectbox(
        "Modelo de IA",
        ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash", "gemini-3.8-flash"],
        index=0,
        help="gemini-2.5-flash es el modelo más estable y recomendado con la mayor disponibilidad en Google."
    )
    
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

    # Acceso rápido si existe archivo local
    local_path = r"C:\Users\Agos\DocumentosAgos\Datito\chat_whatsapp_vecinasmolineras-2026-09-30desde030206.txt"
    if os.path.exists(local_path) and not uploaded_files and not pasted_text.strip():
        if st.button("Cargar chat de ejemplo (Haras Santa María)"):
            st.session_state["use_local_default"] = True

    pre_extracted_xlsx = r"C:\Users\Agos\DocumentosAgos\Datito\proveedores_recomendados_whatsapp.xlsx"
    if os.path.exists(pre_extracted_xlsx):
        if st.button("📊 Ver los 168 recomendados ya extraídos"):
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

    if len(loaded_chats_info) > 1:
        with st.expander("📁 Detalle de los chats unificados", expanded=False):
            st.dataframe(pd.DataFrame(loaded_chats_info), use_container_width=True, hide_index=True)

    tab_universal, tab_recom, tab_chat = st.tabs([
        "🔍 Búsqueda Universal (Cualquier Consulta)",
        "👥 Planilla de Recomendados (Google Sheets)",
        "📜 Ver Mensajes Limpios"
    ])

    total_m = len(messages)
    slider_min = max(1, min(50, total_m // 2)) if total_m > 1 else 1
    slider_step = max(1, min(100, total_m // 10)) if total_m > 50 else 1

    # ----------------- TAB 1: BÚSQUEDA UNIVERSAL LIBRE -----------------
    with tab_universal:
        st.subheader("Búsqueda de Cualquier Tipo de Información")
        st.write("Escribe con tus propias palabras qué necesitas encontrar en el chat. La IA creará la tabla adecuada automáticamente.")

        st.markdown("**Ejemplos rápidos para inspirarte (haz clic para probar):**")
        ex_cols = st.columns(4)
        if ex_cols[0].button("🍕 Comida y Gastronomía"):
            st.session_state["search_query_input"] = "Extrae todas las personas o comercios que venden comida casera, viandas, postres o delivery, indicando qué ofrecen, contacto y precios si hay"
        if ex_cols[1].button("🏡 Alquileres de Casas"):
            st.session_state["search_query_input"] = "Busca todos los que ofrecen o buscan casas o quintas en alquiler, indicando lote, características y precio mencionado"
        if ex_cols[2].button("⚠️ Seguridad y Reclamos"):
            st.session_state["search_query_input"] = "Extrae todos los incidentes o reclamos de seguridad, corte de luz o problemas comunitarios con fecha y lote"
        if ex_cols[3].button("📚 Profesores y Clases"):
            st.session_state["search_query_input"] = "Extrae profesores o personas que ofrecen clases particulares (inglés, tenis, música, etc.) con sus contactos"

        default_query = st.session_state.get("search_query_input", "")
        query = st.text_area(
            "¿Qué deseas extraer de los chats?",
            value=default_query,
            placeholder="Ej: 'Extrae todos los contactos de electricistas y plomeros con los comentarios de quién los recomendó y en qué fecha'",
            height=90
        )

        col_btn_u, col_slider_u = st.columns([1, 3])
        with col_btn_u:
            btn_universal = st.button("🚀 Buscar y Extraer con IA", type="primary", disabled=not (bool(api_key) and bool(query.strip())))
        with col_slider_u:
            if total_m > 1:
                sample_size = st.slider(
                    "Cantidad de mensajes recientes a analizar",
                    min_value=slider_min,
                    max_value=total_m,
                    value=total_m,
                    step=slider_step,
                    key="slider_universal",
                    help="Por defecto se analiza el 100% de los mensajes cargados usando procesamiento inteligente en lotes."
                )
            else:
                sample_size = total_m

        if btn_universal:
            try:
                selected_slice = messages[-sample_size:] if sample_size < len(messages) else messages
                total_to_process = len(selected_slice)
                
                prog_bar_u = st.progress(0, text="Iniciando búsqueda inteligente...")
                status_box_u = st.empty()

                def update_progress_u(curr, total, count, msg):
                    pct = int((curr / total) * 100)
                    prog_bar_u.progress(min(pct, 100), text=f"Lote {curr} de {total} ({pct}%)")
                    status_box_u.info(f"⏳ {msg} | Registros encontrados hasta ahora: **{count}**")

                extractor = WhatsAppInsightExtractor(api_key=api_key, model=model_choice)
                result = extractor.extract_dynamic_query_batched(
                    selected_slice,
                    query,
                    chunk_size=800,
                    progress_callback=update_progress_u
                )
                
                prog_bar_u.empty()
                status_box_u.empty()

                filas = result.get("filas", [])
                if filas:
                    df_custom = pd.DataFrame(filas)
                    st.session_state["custom_results_df"] = df_custom
                    st.success(f"¡Se encontraron {len(df_custom)} registros relevantes en total!")
                else:
                    st.warning("No se encontraron registros que respondan a la consulta en este rango de mensajes.")
            except Exception as e:
                st.error(f"Error durante el procesamiento: {e}")

        if "custom_results_df" in st.session_state:
            df_custom = st.session_state["custom_results_df"]
            st.dataframe(df_custom, use_container_width=True)

            col_d1, col_d2 = st.columns(2)
            with col_d1:
                buf = io.BytesIO()
                with pd.ExcelWriter(buf, engine="openpyxl") as writer:
                    df_custom.to_excel(writer, index=False, sheet_name="Resultados")
                st.download_button(
                    "📥 Descargar Resultados en Excel (.xlsx)",
                    data=buf.getvalue(),
                    file_name="extraccion_whatsapp_personalizada.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            with col_d2:
                csv_b = df_custom.to_csv(index=False).encode("utf-8-sig")
                st.download_button("📥 Descargar Resultados en CSV", data=csv_b, file_name="extraccion_whatsapp_personalizada.csv", mime="text/csv")

    # ----------------- TAB 2: RECOMENDADOS (GOOGLE SHEETS) -----------------
    with tab_recom:
        st.subheader("Planilla Estructurada de Proveedores (Google Sheets)")
        st.write(
            "Extrae profesionales con el formato exacto de tu planilla: "
            "`nombre, apellido, rubro, telefono, barrio, motivo, avisado, notas` (y chat de origen si hay varios)."
        )
        st.info("💡 **Procesamiento inteligente por lotes activado**: OjoAlChat analiza todos los chats en bloques automáticos de 700 mensajes para sortear el límite de respuesta de Gemini. Si un profesional aparece en varios chats o mensajes, se unifican sus datos y elogios automáticamente.")

        col_btn_r, col_slider_r = st.columns([1, 3])
        with col_btn_r:
            start_recom = st.button("🚀 Extraer Proveedores con IA", disabled=not bool(api_key))
        with col_slider_r:
            if total_m > 1:
                chunk_r = st.slider(
                    "Mensajes a procesar",
                    min_value=slider_min,
                    max_value=total_m,
                    value=total_m,
                    step=slider_step,
                    key="recom_slider",
                    help="Por defecto se analiza el 100% de los mensajes cargados sin recortar ninguno."
                )
            else:
                chunk_r = total_m

        if start_recom:
            try:
                selected_slice = messages[-chunk_r:] if chunk_r < len(messages) else messages
                total_to_process = len(selected_slice)

                prog_bar_r = st.progress(0, text="Iniciando extracción inteligente en lotes...")
                status_box_r = st.empty()

                def update_progress_r(curr, total, count, msg):
                    pct = int((curr / total) * 100)
                    prog_bar_r.progress(min(pct, 100), text=f"Lote {curr} de {total} ({pct}%)")
                    status_box_r.info(f"⏳ {msg} | Proveedores únicos detectados hasta el momento: **{count}**")

                extractor = WhatsAppInsightExtractor(api_key=api_key, model=model_choice)
                results = extractor.extract_recommendations_batched(
                    selected_slice,
                    chunk_size=700,
                    progress_callback=update_progress_r
                )

                prog_bar_r.empty()
                status_box_r.empty()

                if results:
                    df_r = pd.DataFrame(results)
                    base_cols = ["nombre", "apellido", "rubro", "telefono", "barrio", "motivo", "avisado", "notas"]
                    has_chats = any(r.get("chat_origen") for r in results) or len(loaded_chats_info) > 1
                    cols = base_cols + (["chat_origen"] if has_chats and "chat_origen" in df_r.columns else [])
                    for c in cols:
                        if c not in df_r.columns:
                            df_r[c] = ""
                    df_r = df_r[cols]
                    st.session_state["recom_df"] = df_r
                    st.success(f"🎉 ¡Extracción completada! Se extrajeron **{len(df_r)}** proveedores recomendados únicos.")
                else:
                    st.warning("No se encontraron recomendaciones en los mensajes analizados.")
            except Exception as e:
                st.error(f"Error: {e}")

        if "recom_df" in st.session_state:
            df_r = st.session_state["recom_df"]
            st.data_editor(df_r, num_rows="dynamic", use_container_width=True)

            col_r1, col_r2, col_r3 = st.columns(3)
            with col_r1:
                buf_r = io.BytesIO()
                with pd.ExcelWriter(buf_r, engine="openpyxl") as writer:
                    df_r.to_excel(writer, index=False, sheet_name="Recomendados")
                st.download_button(
                    "📥 Descargar Excel (.xlsx)",
                    data=buf_r.getvalue(),
                    file_name="proveedores_recomendados.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            with col_r2:
                st.download_button(
                    "📥 Descargar CSV",
                    data=df_r.to_csv(index=False).encode("utf-8-sig"),
                    file_name="proveedores_recomendados.csv",
                    mime="text/csv",
                )
            with col_r3:
                base_cols = ["nombre", "apellido", "rubro", "telefono", "barrio", "motivo", "avisado", "notas"]
                df_for_sheets = df_r[[c for c in base_cols if c in df_r.columns]]
                tsv_text = df_for_sheets.to_csv(sep="\t", index=False)
                st.text_area("📋 Copiar y pegar a Google Sheets (8 columnas oficiales)", tsv_text, height=70)

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
