import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import plotly.graph_objects as go
import json
from datetime import date

from utils import (
    process_excel_data,
    generate_full_html_report,
    generate_single_room_html_report,
    load_room_maps_and_coordinates,
    generate_random_iso_data,
    ISO_LIMITS_M3,
    DEFAULT_LIMITS
)
from sample_generator import generate_sample_excel_bytes

st.set_page_config(
    page_title="Reporte Cuarto Limpio ISO 14644 (Cuartos 1-6) - BCS",
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
</style>
""", unsafe_allow_html=True)

# Sidebar setup
st.sidebar.image("https://raw.githubusercontent.com/aldoaoa/Visualizador-BCS-IDS/3a44ab1685fb192b1420168d4e246059c8261134/BCS%20LOGO.png")
st.sidebar.title("🔬 Monitoreo 6 Cuartos")
st.sidebar.markdown("---")

# Sample file download button in sidebar
sample_bytes = generate_sample_excel_bytes()
st.sidebar.download_button(
    label="📥 Descargar Excel de Ejemplo (6 Cuartos)",
    data=sample_bytes,
    file_name="mediciones_6_cuartos_ejemplo.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    help="Descarga un archivo Excel de prueba con datos ordenados para Cuarto 1 a Cuarto 6."
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
    help="Define cómo están ordenadas las filas del Excel para cada cuarto."
)

st.sidebar.markdown("---")
st.sidebar.markdown("### ⚙️ Parámetros e ISO 14644")

iso_class = st.sidebar.selectbox(
    "Clase ISO de Cuarto Limpio",
    options=["ISO 8", "ISO 1", "ISO 2", "ISO 3", "ISO 4", "ISO 5", "ISO 6", "ISO 7", "ISO 9"],
    index=0
)

# Populate limits according to selected ISO class (Default: ISO 8: .5: 3520000, 1: 832000, 5: 29300)
selected_iso_limits = ISO_LIMITS_M3.get(iso_class, ISO_LIMITS_M3["ISO 8"])

c05_limit = st.sidebar.number_input(
    "Límite Máx. CH1 (p. ej. 0.5 µm)",
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
equipo_input = st.sidebar.text_input("Equipo Usado", "BCS-QRO-LAB-ANA001, Particles Plus 8503.")
area_size_input = st.sidebar.text_input("Superficie Total por Cuarto", "1662.81 m²")

# Load data for 6 rooms and map images
room_maps = load_room_maps_and_coordinates()

if uploaded_file is not None:
    try:
        multi_room_data, meta = process_excel_data(uploaded_file, mapping_mode=mapping_mode)
        st.success(f"✅ Archivo '{uploaded_file.name}' procesado con éxito ({meta['num_rows_read']} filas distribuidas en Cuartos 1 al 6).")
    except Exception as e:
        st.error(f"❌ Error al procesar el archivo Excel: {e}")
        multi_room_data, meta = process_excel_data(generate_sample_excel_bytes(), mapping_mode=mapping_mode)
else:
    st.info("ℹ️ Mostrando datos de ejemplo para Cuartos 1 a 6. Puedes cargar tu archivo Excel en la barra lateral.")
    multi_room_data, meta = process_excel_data(generate_sample_excel_bytes(), mapping_mode=mapping_mode)

doc_metadata = {
    "fecha": fecha_input,
    "auditor": auditor_input,
    "equipo": equipo_input,
    "temp": meta.get("avg_temp", 21.15),
    "rh": meta.get("avg_rh", 48.32),
    "ch1_name": f"{meta.get('ch1_size', '0.5')} µm",
    "ch2_name": f"{meta.get('ch2_size', '1.0')} µm",
    "ch3_name": f"{meta.get('ch3_size', '5.0')} µm",
    "area_size": area_size_input
}

# Main Header
col_header, col_logo = st.columns([4, 1])
with col_header:
    st.title("Reporte de Medición de Contaminantes - Cuartos 1 al 6")
    st.caption(f"Sistema de Control de Calidad Ambiental y Cuartos Limpios ISO 14644-1 ({iso_class})")
with col_logo:
    st.markdown("<h3 style='color:#E2001A; text-align:right;'>BCS</h3>", unsafe_allow_html=True)

st.markdown("---")

tab_report, tab_single_room, tab_analytics, tab_guide = st.tabs([
    "📄 Reporte Oficial 6 Cuartos (HTML / PDF)",
    "🎯 Reporte Individual por Área / Mapa",
    "📊 Analytics e Inspección por Cuarto",
    "ℹ️ Guía ISO 14644"
])

# Tab 1: Multi-room HTML Report Component
with tab_report:
    col_t1_1, col_t1_2 = st.columns([3, 1])
    with col_t1_1:
        st.subheader("Reporte General Completo (Cuartos 1 a 6)")
    with col_t1_2:
        if st.button("🎲 Generar Datos Aleatorios (Cumplimiento ISO)", key="btn_gen_multi", help="Genera mediciones aleatorias realistas que cumplen con los límites de la clasificación ISO seleccionada."):
            st.session_state["multi_room_data_override"] = generate_random_iso_data(iso_class, custom_limits, 6, 20)
            st.rerun()

    active_multi_data = st.session_state.get("multi_room_data_override", multi_room_data)
    html_content = generate_full_html_report(doc_metadata, active_multi_data, limits=custom_limits, room_maps=room_maps)
    
    st.download_button(
        label="💾 Descargar Reporte Completo 6 Cuartos (HTML Standalone)",
        data=html_content,
        file_name=f"Reporte_Particulas_6Cuartos_{fecha_input}.html",
        mime="text/html",
        help="Descarga el documento HTML completo con todos los reportes de Cuarto 1 a Cuarto 6 para ver offline o imprimir a PDF."
    )
    
    components.html(html_content, height=2200, scrolling=True)

# Tab 2: Single Room Custom Report Component
with tab_single_room:
    col_sr1, col_sr2 = st.columns([2, 2])
    with col_sr1:
        selected_single_room = st.selectbox(
            "Selecciona el Cuarto / Mapa",
            options=["Cuarto 1", "Cuarto 2", "Cuarto 3", "Cuarto 4", "Cuarto 5", "Cuarto 6"],
            index=0,
            key="single_room_select"
        )
    with col_sr2:
        num_points_input = st.slider(
            "Número de Puntos Muestra Requeridos",
            min_value=1,
            max_value=20,
            value=15,
            step=1,
            help="Selecciona cuántas mediciones/puntos se incluirán en el reporte."
        )

    if st.button("🎲 Generar Datos Aleatorios (Área Actual)", key="btn_gen_single", help="Genera mediciones aleatorias simuladas válidas ante ISO para este cuarto específico."):
        rand_multi = generate_random_iso_data(iso_class, custom_limits, 6, 20)
        st.session_state[f"single_room_override_{selected_single_room}"] = rand_multi.get(selected_single_room)
        st.rerun()

    default_room_data = multi_room_data.get(selected_single_room, {
        "c05": {"t1": [-1]*20, "t2": [-1]*20},
        "c1":  {"t1": [-1]*20, "t2": [-1]*20},
        "c5":  {"t1": [-1]*20, "t2": [-1]*20}
    })

    single_room_data = st.session_state.get(f"single_room_override_{selected_single_room}", default_room_data)
    single_room_map = room_maps.get(selected_single_room, {})

    single_html_content = generate_single_room_html_report(
        doc_metadata,
        selected_single_room,
        single_room_data,
        num_points=num_points_input,
        limits=custom_limits,
        room_map=single_room_map
    )

    st.download_button(
        label=f"💾 Descargar Reporte de {selected_single_room} ({num_points_input} Puntos - HTML Standalone)",
        data=single_html_content,
        file_name=f"Reporte_{selected_single_room.replace(' ', '_')}_{num_points_input}Puntos_{fecha_input}.html",
        mime="text/html",
        help="Descarga el reporte de un solo cuarto en formato HTML listo para imprimir a PDF en vertical."
    )

    components.html(single_html_content, height=1300, scrolling=True)

# Tab 3: Streamlit Interactive Analytics & Data Tables by Room
with tab_analytics:
    selected_room = st.selectbox(
        "Selecciona el Cuarto a Inspeccionar",
        options=["Cuarto 1", "Cuarto 2", "Cuarto 3", "Cuarto 4", "Cuarto 5", "Cuarto 6"],
        index=0
    )

    room_data = multi_room_data.get(selected_room, {
        "c05": {"t1": [-1]*20, "t2": [-1]*20},
        "c1":  {"t1": [-1]*20, "t2": [-1]*20},
        "c5":  {"t1": [-1]*20, "t2": [-1]*20}
    })

    def calc_stats(ch_key, limit):
        t1 = [v for v in room_data[ch_key]["t1"] if v >= 0]
        t2 = [v for v in room_data[ch_key]["t2"] if v >= 0]
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
    kpi3.metric(f"Canal {doc_metadata['ch1_name']}", f"{gen_c05:,} part/m³", delta=f"EXCEDE {iso_class}" if ex_c05 else f"CUMPLE {iso_class}", delta_color="inverse" if ex_c05 else "normal")
    kpi4.metric(f"Canal {doc_metadata['ch2_name']}", f"{gen_c1:,} part/m³", delta=f"EXCEDE {iso_class}" if ex_c1 else f"CUMPLE {iso_class}", delta_color="inverse" if ex_c1 else "normal")
    kpi5.metric(f"Canal {doc_metadata['ch3_name']}", f"{gen_c5:,} part/m³", delta=f"EXCEDE {iso_class}" if ex_c5 else f"CUMPLE {iso_class}", delta_color="inverse" if ex_c5 else "normal")

    st.markdown("---")
    st.subheader(f"Gráficos de Concentración por Punto - {selected_room}")

    points_labels = [f"Punto {i+1}" for i in range(20)]

    def create_plotly_chart(ch_key, ch_label, limit):
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=points_labels, y=[v if v >= 0 else None for v in room_data[ch_key]["t1"]],
            mode='lines+markers', name='Toma 1',
            line=dict(color='#0284c7', width=2)
        ))
        fig.add_trace(go.Scatter(
            x=points_labels, y=[v if v >= 0 else None for v in room_data[ch_key]["t2"]],
            mode='lines+markers', name='Toma 2',
            line=dict(color='#0d9488', width=2)
        ))
        fig.add_trace(go.Scatter(
            x=points_labels, y=[limit]*20,
            mode='lines', name=f'Límite {iso_class} ({limit:,})',
            line=dict(color='#ef4444', width=2, dash='dash')
        ))
        fig.update_layout(
            title=f"{selected_room} - Canal {ch_label} (Límite Máx {iso_class}: {limit:,} partículas/m³)",
            xaxis_title="Punto de Muestra",
            yaxis_title="Partículas / m³",
            hovermode="x unified",
            margin=dict(l=20, r=20, t=40, b=20),
            height=320
        )
        return fig

    st.plotly_chart(create_plotly_chart("c05", doc_metadata["ch1_name"], custom_limits["c05"]))
    st.plotly_chart(create_plotly_chart("c1", doc_metadata["ch2_name"], custom_limits["c1"]))
    st.plotly_chart(create_plotly_chart("c5", doc_metadata["ch3_name"], custom_limits["c5"]))

    st.markdown("---")
    st.subheader(f"Tabla de Mediciones - {selected_room}")

    df_points = pd.DataFrame({
        "Punto": range(1, 21),
        f"{doc_metadata['ch1_name']} (Toma 1)": room_data["c05"]["t1"],
        f"{doc_metadata['ch1_name']} (Toma 2)": room_data["c05"]["t2"],
        f"{doc_metadata['ch2_name']} (Toma 1)": room_data["c1"]["t1"],
        f"{doc_metadata['ch2_name']} (Toma 2)": room_data["c1"]["t2"],
        f"{doc_metadata['ch3_name']} (Toma 1)": room_data["c5"]["t1"],
        f"{doc_metadata['ch3_name']} (Toma 2)": room_data["c5"]["t2"],
    })

    st.dataframe(df_points)

# Tab 3: ISO Guide
with tab_guide:
    st.subheader("Normativa ISO 14644-1: Clasificación de Contaminación por Partículas")
    st.markdown("""
    La norma **ISO 14644-1** especifica las clases de limpieza del aire en salas limpias y zonas controladas.
    
    ### Tabla de Límites Máximos Permitidos ($partículas / m^3$)
    """)

    df_iso_table = pd.DataFrame.from_dict(ISO_LIMITS_M3, orient='index')
    df_iso_table.columns = ["0.1 µm", "0.2 µm", "0.3 µm", "0.5 µm", "1.0 µm", "5.0 µm"]
    st.table(df_iso_table.style.format(lambda v: f"{v:,}" if v > 0 else "-"))
