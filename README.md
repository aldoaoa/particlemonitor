# 🔬 App de Reportes de Medición de Partículas en Cuarto Limpio (ISO 14644) - BCS

Esta aplicación en Python construida con **Streamlit** procesa archivos Excel con mediciones de contaminantes ambientales y genera automáticamente el reporte oficial de dos páginas con formato BCS Automotive Interface Solutions, gráficos interactivos de comparación de límites ISO y plano de planta con pines interactivos.

## 📋 Estructura del Archivo Excel Requerido

El archivo Excel de entrada debe contener las siguientes columnas (el orden puede variar):

| Columna | Descripción | Ejemplo |
| :--- | :--- | :--- |
| `Time` | Marca de tiempo de la toma | `2025-07-21 08:30:00` |
| `Temp` | Temperatura ambiental en °C | `21.15` |
| `RH` | Humedad relativa (%) | `48.32` |
| `CH1 Size` | Tamaño de partícula del Canal 1 (micrones) | `0.3` o `0.5` |
| `CH2 Size` | Tamaño de partícula del Canal 2 (micrones) | `1.0` |
| `CH3 Size` | Tamaño de partícula del Canal 3 (micrones) | `5.0` |
| `CntsCumM3 CH1` | Conteo acumulado por $m^3$ para Canal 1 | `986090` |
| `CntsCumM3 CH2` | Conteo acumulado por $m^3$ para Canal 2 | `112541` |
| `CntsCumM3 CH3` | Conteo acumulado por $m^3$ para Canal 3 | `2947` |

---

## 🚀 Despliegue en Streamlit Cloud

1. **Subir el código a GitHub**:
   - Crea un nuevo repositorio en GitHub.
   - Sube todos los archivos de esta carpeta (`app.py`, `utils.py`, `sample_generator.py`, `requirements.txt`, `.streamlit/config.toml`).

2. **Desplegar en Streamlit Cloud**:
   - Ingresa a [share.streamlit.io](https://share.streamlit.io/).
   - Inicia sesión con GitHub.
   - Haz clic en **"New app"**.
   - Selecciona tu repositorio y la rama `main`.
   - Especifica `app.py` como **Main file path**.
   - Haz clic en **"Deploy!"**.

---

## 💻 Ejecución Local

1. Instala las dependencias:
   ```bash
   pip install -r requirements.txt
   ```

2. Ejecuta la aplicación:
   ```bash
   streamlit run app.py
   ```

---

## 🛠️ Características Principales

- **Evaluación ISO 14644-1 Automática**: Soporta Clases ISO 1 a ISO 9 con resaltado rojo en celdas y gráficos cuando se superan los límites permitidos.
- **Reporte Oficial BCS de 2 Páginas**:
  - **Página 1**: Encabezado oficial con logo BCS SVG, metadatos, tabla de 20 puntos con Toma 1 y Toma 2, resumen de promedios por canal y gráficos de líneas.
  - **Página 2**: Plano de planta interactivo con 20 pines arrastables (azul: cumple / rojo con pulso: excede), contador dinámico y carga de plano personalizado.
- **Exportación Versátil**: Imprime o guarda directamente a **PDF** mediante el botón de la barra de control o descarga el archivo HTML *standalone* ejecutable sin conexión a internet.
- **Plantilla de Ejemplo**: Incluye un generador de archivos Excel de muestra descargable con 1 solo clic dentro de la app.
