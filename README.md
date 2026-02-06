# 🎬 CineGram Bot

**El bot definitivo para publicación automatizada de películas en Telegram.**

CineGram es un asistente autónomo que procesa archivos de video, identifica qué película son (incluso si el nombre está mal escrito), obtiene su información oficial, traduce la sinopsis y genera pósters profesionales.

![Python](https://img.shields.io/badge/Python-3.14-blue?style=flat-square&logo=python)
![Telegram](https://img.shields.io/badge/Telegram-Bot-blue?style=flat-square&logo=telegram)
![Status](https://img.shields.io/badge/Estado-Estable-success?style=flat-square)

---

## 🚀 Características Principales

### 🧠 1. CineGram AI (Deep Search)
El bot cuenta con un cerebro propio (Ollama local) que entra en acción cuando la búsqueda normal falla.
- **Detector de Spam**: Limpia nombres como *"Pelicula.Completa.Latino.HD.2024.mp4"* para encontrar *"Matrix"*.
- **Corrector de Errores**: Entiende cosas como *"Abengers Enfgame"* y busca *"Avengers: Endgame"*.
- **Red de Seguridad (Fallback)**: Si no encuentra nada a la primera, lee la "Descripción" del video para intentar entender de qué película se trata.

### 🎨 2. Pósters Inteligentes (Smart Posters)
Olvídate de las cabezas recortadas.
- **Fondo Borroso**: Usa una técnica de diseño profesional donde el póster se muestra completo en el centro, y el fondo se rellena con una versión borrosa y oscura de la misma imagen.
- **Formato Cine**: Genera imágenes en 1920x1080 listas para canales de alta calidad.

### 👻 3. Modo Fantasma (Ghost Mode)
Mantiene tu canal y chat limpios.
- **Auto-Eliminación**: Después de publicar la película en el canal, el bot borra automáticamente el archivo de video que enviaste al chat privado.
- **Mensajes Temporales**: Los mensajes de estado ("Buscando...", "Generando portada...") se autodestruyen para no ensuciar la conversación.

### 🛡️ 4. Estabilidad a Prueba de Fallos
- **Reintentos Inteligentes**: Si TMDB falla, el bot reintenta varias veces antes de rendirse.
- **Protección de Spam**: Detecta y rechaza nombres genéricos como "Video.mp4" a menos que tengan una descripción clara.
- **Salud del Sistema**: Verifica que la IA esté activa antes de empezar.

---

## 📖 Instrucciones de Uso

### Instalación
1. Clona el repositorio.
2. Crea tu archivo `.env` con las claves (ver `.env.example`).
3. Instala `requirements.txt`.
4. Instala **Ollama** y descárgate un modelo liviano (ej. `llama3` o `mistral`).

### Cómo publicar una película
1. **Envía el video** al bot en privado.
2. (Opcional) Ponle un **caption** (descripción) si el nombre del archivo es muy malo.
3. El bot hará todo el trabajo: busca, crea póster y publica en el canal.

### Comandos Manuales
- `/search [Nombre]` - Busca una película manualmente para ver sus datos.
- **Corrección Manual**: Si el bot se equivoca y dice "No encontré nada", respóndele a ese mensaje con el nombre correcto (ej. *"Matrix 1999"*) y lo intentará de nuevo.

---

## 📂 Estructura del Proyecto

- `cinegram/handlers/`: Lógica de respuestas (Videos, Comandos).
- `cinegram/services/`: Cerebro del bot (TMDB, IA, Generador de Imágenes).
- `cinegram/utils/`: Herramientas de ayuda.

---

*Creado con ❤️ para automatizar lo aburrido.*
