# 👁️ OjoAlChat (OjoAI)

> **Ojo al Chat:** La IA que ve, escucha y encuentra todo lo que pasa en tus grupos de mensajería (textos, fotos, documentos, enlaces y videos).

---

## 🚀 Despliegue en Streamlit Community Cloud (Gratuito)

Cualquier persona puede usar **OjoAlChat** desde su navegador sin instalar nada:

### Paso 1: Subir a GitHub
1. Crea un nuevo repositorio en [github.com/new](https://github.com/new) con el nombre `OjoAlChat` (puedes dejarlo público o privado).
2. Vincula y sube este código con los comandos:
   ```bash
   git remote add origin https://github.com/TU_USUARIO/OjoAlChat.git
   git branch -M main
   git push -u origin main
   ```

### Paso 2: Desplegar en Streamlit Cloud
1. Entra a [share.streamlit.io](https://share.streamlit.io) e inicia sesión con tu cuenta de GitHub.
2. Haz clic en **"New app"**.
3. Selecciona tu repositorio `OjoAlChat`, rama `main` y en *Main file path* pon `app.py`.
4. Haz clic en **Deploy!**

### Paso 3: Clave de IA compartida (Opcional)
Para que los usuarios que entren a la web no tengan que colocar una API key:
1. En el panel de Streamlit Cloud ve a **App settings > Secrets**.
2. Añade:
   ```toml
   GEMINI_API_KEY = "tu_clave_de_gemini"
   ```
   OjoAlChat también funciona con otras empresas de IA (se elige en la barra lateral). Cargá solo la clave de la que uses:
   ```toml
   ANTHROPIC_API_KEY = "tu_clave_de_claude"
   OPENAI_API_KEY = "tu_clave_de_openai"
   OJO_API_KEY = "tu_clave_de_deepseek_groq_u_openrouter"
   ```
3. Guarda los cambios. ¡Tu web estará lista con un link público para compartir!
