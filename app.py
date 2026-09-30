import io
import os
import pandas as pd
import streamlit as st
from parser import WhatsAppParser
from extractor import WhatsAppInsightExtractor

st.set_page_config(
    page_title="OjoAlChat | OjoAI",
    page_icon="👁️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("👁️ OjoAlChat (OjoAI)")
st.caption("El ojo con Inteligencia Artificial que ve, analiza y encuentra cualquier dato, persona, video o archivo en tus chats.")

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
        ["gemini-3.8-flash", "gemini-3.5-flash-lite"],
        index=0,
    )
    
    st.divider()
    st.subheader("📁 Archivo de Chat")
    uploaded_file = st.file_uploader("Sube el chat (.txt)", type=["txt"], help="Exporta tu chat de WhatsApp como archivo .txt y súbelo aquí.")

    # Acceso rápido si existe archivo local
    local_path = r"C:\Users\Agos\DocumentosAgos\Datito\chat_whatsapp_vecinasmolineras-2026-09-30desde030206.txt"
    if os.path.exists(local_path) and uploaded_file is None:
        if st.button("Cargar chat de ejemplo (Haras Santa María)"):
            st.session_state["use_local_default"] = True

    pre_extracted_xlsx = r"C:\Users\Agos\DocumentosAgos\Datito\proveedores_recomendados_whatsapp.xlsx"
    if os.path.exists(pre_extracted_xlsx):
        if st.button("📊 Ver los 168 recomendados ya extraídos"):
            st.session_state["recom_df"] = pd.read_excel(pre_extracted_xlsx)
            st.session_state["use_local_default"] = True

# Lectura de contenido
raw_text = None
if uploaded_file is not None:
    raw_text = uploaded_file.read().decode("utf-8", errors="ignore")
elif st.session_state.get("use_local_default", False) and os.path.exists(local_path):
    with open(local_path, "r", encoding="utf-8", errors="ignore") as f:
        raw_text = f.read()

if not raw_text:
    st.info("👋 **Bienvenido**: Para comenzar, sube un archivo `.txt` de chat de WhatsApp en la barra lateral izquierda.")
    st.markdown("""
    ### ¿Cómo exportar un chat de WhatsApp?
    * **En el celular**: Abre el chat o grupo > Menú (3 puntos o info) > Más > **Exportar chat (Sin archivos)**.
    * **En la computadora (WhatsApp Web)**: Si utilizas el script extractor en consola, obtendrás el archivo `.txt` directamente.
    """)
    st.stop()

# Parseo de mensajes
parser = WhatsAppParser()
messages = parser.parse(raw_text)

if not messages:
    st.error("No se pudieron detectar mensajes válidos en el archivo. Asegúrate de que sea un archivo de texto exportado de WhatsApp.")
    st.stop()

# Métricas
senders = list(set(m.sender for m in messages))
col1, col2, col3 = st.columns(3)
col1.metric("Mensajes Procesados", f"{len(messages):,}")
col2.metric("Participantes", len(senders))
col3.metric("Rango de Fechas", f"{messages[0].date} ➔ {messages[-1].date}")

tab_universal, tab_recom, tab_chat = st.tabs([
    "🔍 Búsqueda Universal (Cualquier Consulta)",
    "👥 Planilla de Recomendados (Google Sheets)",
    "📜 Ver Mensajes Limpios"
])

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
        "¿Qué deseas extraer del chat?",
        value=default_query,
        placeholder="Ej: 'Extrae todos los contactos de electricistas y plomeros con los comentarios de quién los recomendó y en qué fecha'",
        height=90
    )

    col_btn_u, col_slider_u = st.columns([1, 3])
    with col_btn_u:
        btn_universal = st.button("🚀 Buscar y Extraer con IA", type="primary", disabled=not (bool(api_key) and bool(query.strip())))
    with col_slider_u:
        sample_size = st.slider("Cantidad de mensajes recientes a analizar", min_value=100, max_value=len(messages), value=min(len(messages), 3000), step=100)

    if btn_universal:
        try:
            with st.spinner("Analizando conversación con Gemini y generando estructura..."):
                extractor = WhatsAppInsightExtractor(api_key=api_key, model=model_choice)
                selected_slice = messages[-sample_size:] if sample_size < len(messages) else messages
                formatted_text = "\n".join([m.to_formatted_str() for m in selected_slice])
                
                result = extractor.extract_dynamic_query(formatted_text, query)
                filas = result.get("filas", [])
                
                if filas:
                    df_custom = pd.DataFrame(filas)
                    st.session_state["custom_results_df"] = df_custom
                    st.success(f"¡Se encontraron {len(df_custom)} registros relevantes!")
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
        "`nombre, apellido, rubro, telefono, barrio, motivo, avisado, notas`."
    )

    col_btn_r, col_slider_r = st.columns([1, 3])
    with col_btn_r:
        start_recom = st.button("🚀 Extraer Proveedores con IA", disabled=not bool(api_key))
    with col_slider_r:
        chunk_r = st.slider("Mensajes a procesar", min_value=100, max_value=len(messages), value=min(len(messages), 3000), step=100, key="recom_slider")

    if start_recom:
        try:
            with st.spinner("Extrayendo proveedores..."):
                extractor = WhatsAppInsightExtractor(api_key=api_key, model=model_choice)
                selected_slice = messages[-chunk_r:] if chunk_r < len(messages) else messages
                formatted_text = "\n".join([m.to_formatted_str() for m in selected_slice])
                results = extractor.extract_recommendations(formatted_text)
                if results:
                    df_r = pd.DataFrame(results)
                    cols = ["nombre", "apellido", "rubro", "telefono", "barrio", "motivo", "avisado", "notas"]
                    for c in cols:
                        if c not in df_r.columns:
                            df_r[c] = ""
                    df_r = df_r[cols]
                    st.session_state["recom_df"] = df_r
                    st.success(f"¡Se extrajeron {len(df_r)} proveedores!")
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
            tsv_text = df_r.to_csv(sep="\t", index=False)
            st.text_area("📋 Copiar y pegar a Google Sheets (TSV)", tsv_text, height=70)

# ----------------- TAB 3: VER CHAT LIMPIO -----------------
with tab_chat:
    st.subheader("Historial de Mensajes Limpio")
    search_q = st.text_input("Filtrar mensajes por texto o participante", "")
    filtered_msgs = [m for m in messages if search_q.lower() in m.text.lower() or search_q.lower() in m.sender.lower()]
    st.write(f"Mostrando {min(len(filtered_msgs), 150)} de {len(filtered_msgs)} mensajes encontrados:")
    preview_text = "\n\n".join([m.to_formatted_str() for m in filtered_msgs[:150]])
    st.text_area("Mensajes", preview_text, height=450)
