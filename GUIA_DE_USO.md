# 📖 Guía de Uso: Cómo Descargar Chats de WhatsApp y Analizarlos con OjoAlChat

Esta guía explica paso a paso cómo descargar el historial completo de cualquier grupo o chat de WhatsApp (incluso desde la computadora, donde WhatsApp no incluye esa opción de fábrica) y cómo procesarlo con **OjoAlChat**.

---

## Método 1: Desde la Computadora (WhatsApp Web) con el Script

Dado que WhatsApp Web no tiene botón oficial de exportar, usamos el script automático que va haciendo scroll hacia arriba y recopila los mensajes por ti.

### Paso a paso:

1. **Abre WhatsApp Web**:
   * Entra a [web.whatsapp.com](https://web.whatsapp.com) en tu navegador (Google Chrome, Microsoft Edge, Brave, etc.).
   * Haz clic sobre el chat o grupo del que deseas extraer la información.

2. **Abre la Consola de Desarrollador**:
   * Presiona la tecla **`F12`** en tu teclado (o haz clic derecho en cualquier parte vacía de la pantalla y elige **"Inspeccionar"**).
   * En el panel que se abrirá (a la derecha o abajo), haz clic en la pestaña **Consola** (o *Console*).

3. **Permitir pegar código (Solo la primera vez)**:
   * Por seguridad, los navegadores modernos suelen bloquear el pegado en la consola hasta que tú lo autorices.
   * Si al intentar pegar no te deja, escribe en la consola:
     ```text
     permitir pegar
     ```
     *(o en inglés: `allow pasting`)* y presiona **Enter**.

4. **Copiar y ejecutar el script**:
   * Abre el archivo `descargar_chat_whatsapp_web.js` y copia todo su contenido.
   * Pégalo en la consola de WhatsApp Web y presiona **Enter**.

5. **Panel flotante de descarga multi-chat**:
   * Verás aparecer un panel flotante arriba a la derecha de la pantalla:
     * **Detecta automáticamente el grupo actual** y nombra el archivo en consecuencia.
     * Puedes configurar un rango de fechas o dejarlo desde el inicio hasta hoy.
     * Al terminar o pulsar detener, aparecerá un botón verde grande: **`[📥 DESCARGAR ARCHIVO (X msgs)]`** que puedes presionar directamente para guardar el archivo `.txt` de forma inmediata (evitando bloqueos automáticos de Chrome/Edge).
     * También incluye un botón **`[📋 Copiar mensajes al portapapeles]`** como alternativa rápida.
     * **Multi-chat en la misma sesión**: Sin recargar la página, puedes hacer clic en otro grupo de WhatsApp en tu lista de chats, el panel actualizará el nombre automáticamente y podrás descargar ese otro grupo.

---

## Método 2: Desde el Celular (Exportación nativa de WhatsApp)

Si prefieres hacerlo desde tu teléfono móvil sin usar la consola:

### En Android:
1. Abre el grupo o conversación.
2. Toca los **tres puntos verticales** arriba a la derecha.
3. Selecciona **Más** > **Exportar chat**.
4. Elige **"Sin archivos multimedia"**.
5. Envíate el archivo `.txt` por correo o guárdalo en tu Google Drive.

### En iPhone (iOS):
1. Abre el grupo o conversación.
2. Toca el **nombre del grupo** arriba de todo (en la barra superior).
3. Desliza hacia abajo hasta el final de la pantalla.
4. Toca **Exportar chat** > **"Sin archivos"**.
5. Guárdalo en la app "Archivos" o envíatelo por correo a tu PC.

---

## ¿Cómo analizar uno o varios chats con OjoAlChat?

Una vez que tienes tus archivos `.txt`:

1. Entra a la aplicación web de **OjoAlChat**.
2. En la barra lateral izquierda, en **"Sube uno o varios chats (.txt)"**, haz clic en **Browse files**.
   * **Análisis Multi-Chat**: Puedes mantener presionada la tecla `Ctrl` (o `Cmd` en Mac) y seleccionar **varios archivos `.txt` a la vez** (ej: *Ventas y Proveedores*, *Vecinas Molineras*, *Seguridad*).
3. OjoAlChat consolidará todos los mensajes, identificando el chat de procedencia de cada uno.
4. Puedes:
   * **Búsqueda Universal**: Hacer preguntas transversales a todos los chats (*"comida y viandas"*, *"alquileres"*, *"profesores particulares"*, *"electricistas y plomeros"*).
   * **Planilla de Proveedores**: Generar la planilla de recomendados con las 8 columnas oficiales para Google Sheets (y columna de chat de procedencia).
   * **Visor Limpio**: Filtrar el historial por grupo específico o participante.
5. Descarga los resultados consolidados en **Excel (.xlsx)**, **CSV** o copia directamente al portapapeles para pegar en tu Google Sheet.
