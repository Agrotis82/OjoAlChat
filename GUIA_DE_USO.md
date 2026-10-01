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

5. **Panel flotante de descarga**:
   * Verás aparecer un recuadro oscuro arriba a la derecha de la pantalla:
     ```text
     ┌──────────────────────────────────────────────┐
     │ Extractor de WhatsApp                        │
     │ Mensajes recopilados: 254                    │
     │ [ Detener y Descargar .txt ]   [ Cancelar ]  │
     └──────────────────────────────────────────────┘
     ```
   * El chat irá subiendo solo en el historial mientras el contador aumenta.
   * Cuando consideres que ya cargó suficiente historial (o llegue al inicio del grupo), haz clic en el botón verde **"Detener y Descargar .txt"**.
   * Se descargará automáticamente un archivo con el formato: `chat_whatsapp_AAAA-MM-DD.txt` en tu carpeta de *Descargas*.

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

## ¿Cómo analizar el chat descargado con OjoAlChat?

Una vez que tienes tu archivo `.txt`, puedes usar **OjoAlChat**:

1. Entra a la aplicación web de **OjoAlChat**.
2. En la barra lateral izquierda, sube el archivo `.txt`.
3. Escribe cualquier búsqueda en lenguaje natural (ej: *"recomienden plomeros"*, *"precios de alquileres"*, *"reclamos de luz"* o *"personas que vendan comida"*).
4. La IA generará la tabla automáticamente y podrás descargar los resultados en **Excel** o **CSV**.
