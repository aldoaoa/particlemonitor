import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import plotly.graph_objects as go
import json
from datetime import date

from utils import (
    process_excel_data,
    generate_full_html_report,
    ISO_LIMITS_M3,
    DEFAULT_LIMITS
)
from sample_generator import generate_sample_excel_bytes

st.set_page_config(
    page_title="Reporte Cuarto Limpio ISO 14644 - BCS",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS styling for Streamlit
st.markdown("""
<style>
    .main-header {
        font-family: 'Inter', sans-serif;
        color: #E2001A;
        font-weight: 800;
    }
    .stButton>button {
        background-color: #E2001A;
        color: white;
        font-weight: 600;
        border-radius: 6px;
        border: none;
    }
    .stButton>button:hover {
        background-color: #b80015;
        color: white;
    }
    .metric-card {
        background-color: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 12px;
        text-align: center;
    }
    .status-badge-pass {
        background-color: #dcfce7;
        color: #166534;
        padding: 4px 10px;
        border-radius: 12px;
        font-weight: bold;
        font-size: 0.8rem;
    }
    .status-badge-fail {
        background-color: #fee2e2;
        color: #991b1b;
        padding: 4px 10px;
        border-radius: 12px;
        font-weight: bold;
        font-size: 0.8rem;
    }
</style>
""", unsafe_allow_html=True)

# Sidebar setup
st.sidebar.image("https://upload.wikimedia.org/wikipedia/commons/thumb/0/07/BCS_Automotive_Interface_Solutions_Logo.svg/512px-BCS_Automotive_Interface_Solutions_Logo.svg.png", use_container_width=True, onerror="ignore")
st.sidebar.title("🔬 Monitoreo Cuarto Limpio")
st.sidebar.markdown("---")

# Sample file download button in sidebar
sample_bytes = generate_sample_excel_bytes()
st.sidebar.download_button(
    label="📥 Descargar Excel de Ejemplo",
    data=sample_bytes,
    file_name="mediciones_cuarto_limpio_ejemplo.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    help="Descarga un archivo Excel de prueba estructurado correctamente."
)

st.sidebar.markdown("### 📁 Carga de Archivo Excel")
uploaded_file = st.sidebar.file_uploader(
    "Selecciona el archivo Excel con las mediciones",
    type=["xlsx", "xls"],
    help="Debe incluir columnas: Time, Temp, RH, CH1 Size, CH2 Size, CH3 Size, CntsCumM3 CH1, CntsCumM3 CH2, CntsCumM3 CH3"
)

mapping_mode = st.sidebar.radio(
    "Mapeo de Lecturas en Excel",
    options=["interleaved", "sequential"],
    format_func=lambda x: "Intercalado (Pt1 T1, Pt1 T2, Pt2 T1...)" if x == "interleaved" else "Secuencial (Pt1..20 T1, Pt1..20 T2)",
    help="Define cómo están ordenadas las filas del Excel."
)

st.sidebar.markdown("---")
st.sidebar.markdown("### ⚙️ Parámetros e ISO 14644")

iso_class = st.sidebar.selectbox(
    "Clase ISO de Cuarto Limpio",
    options=["ISO 5", "ISO 1", "ISO 2", "ISO 3", "ISO 4", "ISO 6", "ISO 7", "ISO 8", "ISO 9"],
    index=0
)

# Populate limits according to selected ISO class or defaults
selected_iso_limits = ISO_LIMITS_M3.get(iso_class, ISO_LIMITS_M3["ISO 5"])

c05_limit = st.sidebar.number_input(
    "Límite Máx. CH1 (p. ej. 0.3/0.5 µm)",
    value=int(selected_iso_limits.get("0.5", DEFAULT_LIMITS["c05"])),
    step=1000
)

c1_limit = st.sidebar.number_input(
    "Límite Máx. CH2 (p. ej. 1.0 µm)",
    value=int(selected_iso_limits.get("1.0", DEFAULT_LIMITS["c1"])),
    step=1000
)

c5_limit = st.sidebar.number_input(
    "Límite Máx. CH3 (p. ej. 5.0 µm)",
    value=int(selected_iso_limits.get("5.0", DEFAULT_LIMITS["c5"])),
    step=100
)

custom_limits = {
    "c05": c05_limit,
    "c1": c1_limit,
    "c5": c5_limit
}

st.sidebar.markdown("---")
st.sidebar.markdown("### 📝 Datos del Documento")

fecha_input = st.sidebar.date_input("Fecha de Medición", date(2025, 7, 21)).strftime("%Y-%m-%d")
auditor_input = st.sidebar.text_input("Nombre del Auditor", "Armando Reyes")
area_input = st.sidebar.text_input("Área de Medición", "Cuarto 2")
equipo_input = st.sidebar.text_input("Equipo Usado", "Medidor de Partículas RION KR-12A")
area_size_input = st.sidebar.text_input("Superficie Total", "1662.81 m²")

# Load data from uploaded file or sample generator
if uploaded_file is not None:
    try:
        report_data, meta = process_excel_data(uploaded_file, mapping_mode=mapping_mode)
        st.success(f"✅ Archivo '{uploaded_file.name}' procesado con éxito ({meta['num_rows_read']} filas leídas).")
    except Exception as e:
        st.error(f"❌ Error al procesar el archivo Excel: {e}")
        report_data, meta = process_excel_data(generate_sample_excel_bytes(), mapping_mode=mapping_mode)
else:
    st.info("ℹ️ Mostrando datos de ejemplo. Puedes cargar tu archivo Excel en la barra lateral.")
    report_data, meta = process_excel_data(generate_sample_excel_bytes(), mapping_mode=mapping_mode)

# Metadata dictionary for report rendering
doc_metadata = {
    "fecha": fecha_input,
    "auditor": auditor_input,
    "area": area_input,
    "equipo": equipo_input,
    "temp": meta.get("avg_temp", 21.15),
    "rh": meta.get("avg_rh", 48.32),
    "ch1_name": f"{meta.get('ch1_size', '0.5')} µm",
    "ch2_name": f"{meta.get('ch2_size', '1.0')} µm",
    "ch3_name": f"{meta.get('ch3_size', '5.0')} µm",
    "area_size": area_size_input
}

# Main Layout Header
col_header, col_logo = st.columns([4, 1])
with col_header:
    st.title("Reporte de Medición de Contaminantes")
    st.caption("Sistema de Control de Calidad Ambiental y Salas Blancas (ISO 14644)")
with col_logo:
    st.markdown("<h3 style='color:#E2001A; text-align:right;'>BCS</h3>", unsafe_allow_html=True)

st.markdown("---")

# Navigation Tabs
tab_report, tab_analytics, tab_guide = st.tabs([
    "📄 Reporte Oficial HTML / PDF",
    "📊 Analytics y Gráficos Interactivos",
    "ℹ️ Guía ISO 14644"
])

# Tab 1: Render Interactive HTML Report Component
with tab_report:
    st.subheader("Vista Previa del Reporte Oficial (Formato BCS)")
    
    html_content = generate_full_html_report(doc_metadata, report_data, limits=custom_limits)
    
    col_dl1, col_dl2 = st.columns([1, 4])
    with col_dl1:
        st.download_button(
            label="💾 Descargar Reporte HTML (Offline)",
            data=html_content,
            file_name=f"Reporte_Particulas_{area_input}_{fecha_input}.html",
            mime="text/html",
            help="Descarga el archivo HTML completo. Puedes abrirlo en cualquier navegador web e imprimir a PDF sin internet."
        )
    
    # Embedded HTML Component
    components.html(html_content, height=1400, scrolling=True)

# Tab 2: Native Streamlit & Plotly Data Analysis
with tab_analytics:
    st.subheader("Métricas Generales y Evaluación ISO")

    # Calculate channel statistics
    def calc_stats(ch_key, limit):
        t1 = report_data[ch_key]["t1"]
        t2 = report_data[ch_key]["t2"]
        avg_t1 = round(sum(t1) / len(t1)) if t1 else 0
        avg_t2 = round(sum(t2) / len(t2)) if t2 else 0
        avg_gen = round((avg_t1 + avg_t2) / 2)
        exceeded = avg_gen > limit or any(v > limit for v in t1) or any(v > limit for v in t2)
        return avg_t1, avg_t2, avg_gen, exceeded

    avg1_c05, avg2_c05, gen_c05, ex_c05 = calc_stats("c05", custom_limits["c05"])
    avg1_c1, avg2_c1, gen_c1, ex_c1    = calc_stats("c1", custom_limits["c1"])
    avg1_c5, avg2_c5, gen_c5, ex_c5    = calc_stats("c5", custom_limits["c5"])

    kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
    kpi1.metric("Temperatura Prom.", f"{doc_metadata['temp']} °C")
    kpi2.metric("Humedad Prom.", f"{doc_metadata['rh']} %")
    kpi3.metric(f"Canal {doc_metadata['ch1_name']}", f"{gen_c05:,} part/m³", delta="EXCEDE" if ex_c05 else "CUMPLE", delta_color="inverse" if ex_c05 else "normal")
    kpi4.metric(f"Canal {doc_metadata['ch2_name']}", f"{gen_c1:,} part/m³", delta="EXCEDE" if ex_c1 else "CUMPLE", delta_color="inverse" if ex_c1 else "normal")
    kpi5.metric(f"Canal {doc_metadata['ch3_name']}", f"{gen_c5:,} part/m³", delta="EXCEDE" if ex_c5 else "CUMPLE", delta_color="inverse" if ex_c5 else "normal")

    st.markdown("---")
    st.subheader("Gráficos de Concentración por Punto de Medición")

    points_labels = [f"Punto {i+1}" for i in range(20)]

    def create_plotly_chart(ch_key, ch_label, limit):
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=points_labels, y=report_data[ch_key]["t1"],
            mode='lines+markers', name='Toma 1',
            line=dict(color='#0284c7', width=2)
        ))
        fig.add_trace(go.Scatter(
            x=points_labels, y=report_data[ch_key]["t2"],
            mode='lines+markers', name='Toma 2',
            line=dict(color='#0d9488', width=2)
        ))
        fig.add_trace(go.Scatter(
            x=points_labels, y=[limit]*20,
            mode='lines', name=f'Límite ISO ({limit:,})',
            line=dict(color='#ef4444', width=2, dash='dash')
        ))
        fig.update_layout(
            title=f"Concentración en Canal {ch_label} (Límite Máx: {limit:,} partículas/m³)",
            xaxis_title="Punto de Muestra",
            yaxis_title="Partículas / m³",
            hovermode="x unified",
            margin=dict(l=20, r=20, t=40, b=20),
            height=320
        )
        return fig

    st.plotly_chart(create_plotly_chart("c05", doc_metadata["ch1_name"], custom_limits["c05"]), use_container_width=True)
    st.plotly_chart(create_plotly_chart("c1", doc_metadata["ch2_name"], custom_limits["c1"]), use_container_width=True)
    st.plotly_chart(create_plotly_chart("c5", doc_metadata["ch3_name"], custom_limits["c5"]), use_container_width=True)

    st.markdown("---")
    st.subheader("Tabla Completa de Puntos de Medición")

    df_points = pd.DataFrame({
        "Punto": range(1, 21),
        f"{doc_metadata['ch1_name']} (Toma 1)": report_data["c05"]["t1"],
        f"{doc_metadata['ch1_name']} (Toma 2)": report_data["c05"]["t2"],
        f"{doc_metadata['ch2_name']} (Toma 1)": report_data["c1"]["t1"],
        f"{doc_metadata['ch2_name']} (Toma 2)": report_data["c1"]["t2"],
        f"{doc_metadata['ch3_name']} (Toma 1)": report_data["c5"]["t1"],
        f"{doc_metadata['ch3_name']} (Toma 2)": report_data["c5"]["t2"],
    })

    st.dataframe(df_points, use_container_width=True)

# Tab 3: ISO Guide & Documentation
with tab_guide:
    st.subheader("Normativa ISO 14644-1: Clasificación de Contaminación por Partículas")
    st.markdown("""
    La norma **ISO 14644-1** especifica las clases de limpieza del aire en términos de concentración de partículas suspendidas por metro cúbico ($m^3$).
    
    ### Tabla de Límites Máximos Permitidos ($partículas / m^3$)
    """)

    df_iso_table = pd.DataFrame.from_dict(ISO_LIMITS_M3, orient='index')
    df_iso_table.columns = ["0.1 µm", "0.2 µm", "0.3 µm", "0.5 µm", "1.0 µm", "5.0 µm"]
    st.table(df_iso_table.style.format(lambda v: f"{v:,}" if v > 0 else "-"))

    st.markdown("""
    ---
    ### 🚀 Despliegue en Streamlit Cloud
    1. Sube este repositorio a **GitHub**.
    2. Conecta tu cuenta en [Streamlit Cloud](https://streamlit.io/cloud).
    3. Selecciona el repositorio y define `app.py` como el punto de entrada.
    4. ¡Listo! La app se ejecutará automáticamente online.
    """)
