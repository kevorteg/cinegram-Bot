# 📖 CineGram Wiki

Bienvenido a la Wiki oficial de **CineGram**. Aquí encontrarás documentación detallada sobre cómo funciona el bot internamente.

---

## 🛠️ Guía de Solución de Problemas (Troubleshooting)

### 1. El bot no contesta
- **Causa**: Probablemente el proceso de Python se detuvo.
- **Solución**: Revisa la terminal. Si ves un error, cópialo. Asegúrate de tener internet.

### 2. "TMDB Error" o no encuentra películas
- **Causa**: API Key inválida o TMDB está bloqueado en tu red.
- **Solución**: Verifica tu `TMDB_API_KEY` en el archivo `.env`. Prueba reiniciar el router si tienes IP dinámica.

### 3. La IA no funciona (Deep Search falla)
- **Causa**: Ollama no está corriendo.
- **Solución**: Abre una terminal y escribe `ollama serve`. El bot hace un "Health Check" al inicio para avisarte de esto.

### 4. Las imágenes salen negras
- **Causa**: Error descargando la imagen de TMDB.
- **Solución**: El bot tiene un timeout de 10 segundos. Si tu internet es lento, podría fallar. El bot usa un placeholder negro para no romper el flujo.

---

## 🧠 Explicación del Flujo de Deep Search

CineGram usa un sistema de 3 capas para identificar películas:

1.  **Filtrado Regex (Rápido)**:
    - Usa `guessit` para separar "Movie.2024.mp4" en Nombre y Año.
    - Si funciona y TMDB lo encuentra, termina aquí.

2.  **Limpieza de Spam (Intermedio)**:
    - Si el nombre tiene palabras como "CUEVANA", "LATINO", "1080p", las elimina agresivamente.

3.  **Inferencia Artificial (Lento pero Preciso)**:
    - Si nada funciona, le envía el nombre del archivo y tu descripción a **Ollama**.
    - El prompt del sistema le dice: *"Actúa como un experto en cine. Extrae el título real de este texto basura..."*.
    - La IA devuelve un JSON limpio: `{"title": "The Matrix", "year": "1999"}`.

---

## 🎨 Sistema de Pósters (Smart Crop)

Para evitar cortar cabezas en los pósters verticales cuando se pasan a formato horizontal (Youtube/Telegram):

1.  Tomamos la imagen original.
2.  Creamos un fondo de 1920x1080.
3.  Estiramos la imagen original para llenar todo el fondo, la desenfocamos (Blur 30px) y la oscurecemos.
4.  Pegamos la imagen original (sin estirar) en el centro.
5.  Añadimos el texto y logotipos encima.

Esto garantiza 100% de legibilidad y estética.
