# 🔬 App de Reportes de Medición de Partículas Multicuarto (ISO 14644) - BCS

Esta aplicación en Python construida con **Streamlit** procesa archivos Excel con mediciones de contaminantes ambientales para **6 cuartos simultáneamente (Cuarto 1 a Cuarto 6)** y genera automáticamente los reportes oficiales individuales y globales con formato BCS Automotive Interface Solutions.

## 📋 Estructura de Datos y Asignación de Cuartos

La aplicación lee secuencialmente los datos de la tabla Excel y llena automáticamente desde **Cuarto 1 hasta Cuarto 6**:

- **Cuarto 1**: Filas 1 a 40 (20 puntos x 2 tomas).
- **Cuarto 2**: Filas 41 a 80.
- **Cuarto 3**: Filas 81 a 120.
- **Cuarto 4**: Filas 121 a 160.
- **Cuarto 5**: Filas 161 a 200.
- **Cuarto 6**: Filas 201 a 240.

> [!NOTE]
> Si el archivo Excel contiene menos datos de los requeridos para llenar hasta el Cuarto 6, las muestras faltantes se dejarán vacías automáticamente.

---

## ⚙️ Límites Predeterminados (ISO Class 8)

De acuerdo con la norma **ISO 14644-1 (Clase ISO 8)**, los límites máximos por $m^3$ son:

| Canal | Límite Máximo Permitido |
| :--- | :--- |
| **0.5 µm** | `3,520,000` partículas / $m^3$ |
| **1.0 µm** | `832,000` partículas / $m^3$ |
| **5.0 µm** | `29,300` partículas / $m^3$ |

---

## 🚀 Despliegue en Streamlit Cloud

1. Sube los archivos a tu repositorio de **GitHub**.
2. Ingresa a [share.streamlit.io](https://share.streamlit.io/).
3. Selecciona tu repositorio y define `app.py` como **Main file path**.
4. ¡Listo! La app se ejecutará online.
