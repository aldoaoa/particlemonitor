import pandas as pd
import numpy as np
import json
import re

# Standard ISO 14644-1:2015 limits in particles per m3
# For ISO 5 (Standard Cleanroom): 0.5um: 3,520,000 | 1um: 832,000 | 5um: 29,300
ISO_LIMITS_M3 = {
    "ISO 1": {"0.1": 10, "0.2": 2, "0.3": 0, "0.5": 0, "1.0": 0, "5.0": 0},
    "ISO 2": {"0.1": 100, "0.2": 24, "0.3": 10, "0.5": 4, "1.0": 0, "5.0": 0},
    "ISO 3": {"0.1": 1000, "0.2": 237, "0.3": 102, "0.5": 35, "1.0": 8, "5.0": 0},
    "ISO 4": {"0.1": 10000, "0.2": 2370, "0.3": 1020, "0.5": 352, "1.0": 83, "5.0": 29},
    "ISO 5": {"0.1": 100000, "0.2": 23700, "0.3": 10200, "0.5": 3520000, "1.0": 832000, "5.0": 29300},
    "ISO 6": {"0.1": 1000000, "0.2": 237000, "0.3": 102000, "0.5": 35200000, "1.0": 8320000, "5.0": 293000},
    "ISO 7": {"0.5": 352000000, "1.0": 83200000, "5.0": 2930000},
    "ISO 8": {"0.5": 3520000000, "1.0": 832000000, "5.0": 29300000},
    "ISO 9": {"0.5": 35200000000, "1.0": 8320000000, "5.0": 293000000}
}

DEFAULT_LIMITS = {
    "c05": 3520000,
    "c1": 832000,
    "c5": 29300
}

def clean_column_names(df):
    """Normalize dataframe column names."""
    df.columns = df.columns.astype(str).str.strip()
    return df

def find_column(df, possible_names):
    """Find a matching column name flexibly."""
    cols = df.columns
    for p in possible_names:
        for c in cols:
            if p.lower() in c.lower():
                return c
    return None

def process_excel_data(file_source, mapping_mode="interleaved"):
    """
    Reads Excel file and extracts measurement data into report structure.
    Expected columns: Time, Temp, RH, CH1 Size, CH2 Size, CH3 Size, CntsCumM3 CH1, CntsCumM3 CH2, CntsCumM3 CH3
    """
    if isinstance(file_source, pd.DataFrame):
        df = file_source.copy()
    else:
        df = pd.read_excel(file_source)

    df = clean_column_names(df)

    col_time = find_column(df, ["time", "fecha", "hora", "date"])
    col_temp = find_column(df, ["temp", "temperatura"])
    col_rh   = find_column(df, ["rh", "humedad", "humidity"])
    
    col_ch1_size = find_column(df, ["ch1 size", "tamaño ch1", "size ch1", "ch1_size"])
    col_ch2_size = find_column(df, ["ch2 size", "tamaño ch2", "size ch2", "ch2_size"])
    col_ch3_size = find_column(df, ["ch3 size", "tamaño ch3", "size ch3", "ch3_size"])

    col_cnt1 = find_column(df, ["cntscumm3 ch1", "ch1 cnt", "cnt ch1", "cntscumm3_ch1", "ch1"])
    col_cnt2 = find_column(df, ["cntscumm3 ch2", "ch2 cnt", "cnt ch2", "cntscumm3_ch2", "ch2"])
    col_cnt3 = find_column(df, ["cntscumm3 ch3", "ch3 cnt", "cnt ch3", "cntscumm3_ch3", "ch3"])

    # Fallbacks if columns are not found directly by name
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    if not col_cnt1 and len(numeric_cols) >= 1:
        col_cnt1 = numeric_cols[0]
    if not col_cnt2 and len(numeric_cols) >= 2:
        col_cnt2 = numeric_cols[1]
    if not col_cnt3 and len(numeric_cols) >= 3:
        col_cnt3 = numeric_cols[2]

    avg_temp = float(df[col_temp].mean()) if col_temp and col_temp in df else 21.15
    avg_rh   = float(df[col_rh].mean()) if col_rh and col_rh in df else 48.32
    
    ch1_size_val = str(df[col_ch1_size].iloc[0]) if col_ch1_size and col_ch1_size in df and not pd.isna(df[col_ch1_size].iloc[0]) else "0.5"
    ch2_size_val = str(df[col_ch2_size].iloc[0]) if col_ch2_size and col_ch2_size in df and not pd.isna(df[col_ch2_size].iloc[0]) else "1.0"
    ch3_size_val = str(df[col_ch3_size].iloc[0]) if col_ch3_size and col_ch3_size in df and not pd.isna(df[col_ch3_size].iloc[0]) else "5.0"

    # Extract series values
    v_cnt1 = pd.to_numeric(df[col_cnt1], errors='coerce').fillna(0).tolist() if col_cnt1 else [0]
    v_cnt2 = pd.to_numeric(df[col_cnt2], errors='coerce').fillna(0).tolist() if col_cnt2 else [0]
    v_cnt3 = pd.to_numeric(df[col_cnt3], errors='coerce').fillna(0).tolist() if col_cnt3 else [0]

    num_rows = len(v_cnt1)

    # Prepare 20 points x 2 takes (40 values per channel)
    report_data = {
        "c05": {"t1": [0]*20, "t2": [0]*20},
        "c1":  {"t1": [0]*20, "t2": [0]*20},
        "c5":  {"t1": [0]*20, "t2": [0]*20}
    }

    channels = [("c05", v_cnt1), ("c1", v_cnt2), ("c5", v_cnt3)]

    for key, vals in channels:
        t1_arr = [0]*20
        t2_arr = [0]*20
        
        if mapping_mode == "interleaved":
            # P1T1, P1T2, P2T1, P2T2, ...
            for p in range(20):
                idx1 = p * 2
                idx2 = p * 2 + 1
                if idx1 < len(vals):
                    t1_arr[p] = int(round(vals[idx1]))
                if idx2 < len(vals):
                    t2_arr[p] = int(round(vals[idx2]))
                elif idx1 < len(vals):
                    t2_arr[p] = int(round(vals[idx1]))
        else:
            # Sequential: P1..P20 T1, then P1..P20 T2
            for p in range(20):
                if p < len(vals):
                    t1_arr[p] = int(round(vals[p]))
                if p + 20 < len(vals):
                    t2_arr[p] = int(round(vals[p + 20]))
                elif p < len(vals):
                    t2_arr[p] = int(round(vals[p]))

        report_data[key]["t1"] = t1_arr
        report_data[key]["t2"] = t2_arr

    meta = {
        "avg_temp": round(avg_temp, 2),
        "avg_rh": round(avg_rh, 2),
        "ch1_size": ch1_size_val,
        "ch2_size": ch2_size_val,
        "ch3_size": ch3_size_val,
        "num_rows_read": num_rows
    }

    return report_data, meta

def generate_full_html_report(metadata, report_data, limits=None):
    """
    Generates complete HTML report string with embedded report_data and metadata.
    """
    if limits is None:
        limits = DEFAULT_LIMITS

    json_report_data = json.dumps(report_data)
    json_limits = json.dumps(limits)

    fecha = metadata.get("fecha", "2025-07-21")
    auditor = metadata.get("auditor", "Armando Reyes")
    area = metadata.get("area", "Cuarto 2")
    equipo = metadata.get("equipo", "Medidor de Partículas RION KR-12A")
    temp = str(metadata.get("temp", "21.15"))
    rh = str(metadata.get("rh", "48.32"))
    ch1_name = metadata.get("ch1_name", "0.5 µm")
    ch2_name = metadata.get("ch2_name", "1 µm")
    ch3_name = metadata.get("ch3_name", "5 µm")
    area_size = metadata.get("area_size", "1662.81 m²")

    html_template = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Reporte de Medición de Partículas - BCS</title>
    <!-- Tailwind CSS CDN -->
    <script src="https://cdn.tailwindcss.com"></script>
    <!-- Chart.js CDN -->
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <!-- FontAwesome Icons -->
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
        
        body {{
            font-family: 'Inter', sans-serif;
            background-color: #f3f4f6;
            color: #1f2937;
            -webkit-print-color-adjust: exact !important;
            print-color-adjust: exact !important;
        }}

        .bcs-red {{ color: #E2001A; }}
        .bg-bcs-red {{ background-color: #E2001A; }}
        .border-bcs-red {{ border-color: #E2001A; }}

        .cell-input {{
            width: 100%;
            padding: 2px 4px;
            font-size: 0.72rem;
            text-align: right;
            border: 1px solid #d1d5db;
            border-radius: 3px;
            transition: all 0.15s ease;
            font-variant-numeric: tabular-nums;
        }}

        .cell-input:focus {{
            outline: none;
            border-color: #2563eb;
            box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.2);
            background-color: #eff6ff;
        }}

        .cell-input.out-of-spec {{
            background-color: #fef2f2 !important;
            color: #dc2626 !important;
            font-weight: 700;
            border-color: #ef4444 !important;
        }}

        .cell-input.in-spec {{
            background-color: #f0fdf4;
            color: #166534;
        }}

        .page-container {{
            width: 100%;
            max-width: 1400px;
            margin: 0 auto;
            background: #ffffff;
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.1);
        }}

        @media print {{
            body {{
                background: #ffffff;
                padding: 0;
                margin: 0;
            }}
            .no-print {{
                display: none !important;
            }}
            .page-break {{
                page-break-before: always;
                break-before: page;
            }}
            .page-container {{
                box-shadow: none;
                max-width: 100% !important;
                width: 100% !important;
                padding: 0 !important;
                margin: 0 !important;
            }}
            .chart-wrapper {{
                height: 180px !important;
            }}
            @page {{
                size: landscape;
                margin: 8mm;
            }}
        }}

        .map-pin {{
            position: absolute;
            width: 26px;
            height: 26px;
            border-radius: 50%;
            color: white;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 0.75rem;
            font-weight: 700;
            cursor: move;
            user-select: none;
            box-shadow: 0 2px 5px rgba(0,0,0,0.3);
            transform: translate(-50%, -50%);
            transition: background-color 0.3s ease, transform 0.1s ease;
        }}
        .map-pin:hover {{
            transform: translate(-50%, -50%) scale(1.2);
            z-index: 50;
        }}
        .map-pin.pass {{
            background-color: #0284c7;
            border: 2px solid #ffffff;
        }}
        .map-pin.fail {{
            background-color: #dc2626;
            border: 2px solid #ffffff;
            animation: pulse-fail 1.5s infinite;
        }}

        @keyframes pulse-fail {{
            0% {{ box-shadow: 0 0 0 0 rgba(220, 38, 38, 0.7); }}
            70% {{ box-shadow: 0 0 0 10px rgba(220, 38, 38, 0); }}
            100% {{ box-shadow: 0 0 0 0 rgba(220, 38, 38, 0); }}
        }}
    </style>
</head>
<body class="p-2 sm:p-6">

    <!-- Control Action Bar -->
    <div class="no-print max-w-[1400px] mx-auto mb-4 bg-white p-4 rounded-xl shadow-md border border-gray-200 flex flex-wrap items-center justify-between gap-3">
        <div class="flex items-center space-x-3">
            <div class="p-2 bg-red-50 rounded-lg border border-red-100">
                <i class="fa-solid fa-microscope text-red-600 text-xl"></i>
            </div>
            <div>
                <h1 class="font-bold text-gray-800 text-lg leading-tight">Reporte de Medición de Partículas</h1>
                <p class="text-xs text-gray-500">Monitoreo ambiental y evaluación de límites ISO 14644</p>
            </div>
        </div>

        <div class="flex flex-wrap items-center gap-2">
            <button onclick="fillSampleData()" class="px-3 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold rounded-lg transition flex items-center gap-2">
                <i class="fa-solid fa-wand-magic-sparkles"></i> Datos Ejemplo
            </button>
            <button onclick="clearData()" class="px-3 py-2 bg-slate-100 hover:bg-red-50 hover:text-red-600 text-slate-700 text-xs font-semibold rounded-lg transition flex items-center gap-2">
                <i class="fa-solid fa-trash-can"></i> Limpiar
            </button>
            <button onclick="exportJSON()" class="px-3 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold rounded-lg transition flex items-center gap-2">
                <i class="fa-solid fa-download"></i> Exportar
            </button>
            <label class="px-3 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold rounded-lg cursor-pointer transition flex items-center gap-2">
                <i class="fa-solid fa-upload"></i> Importar
                <input type="file" id="importFile" accept=".json" class="hidden" onchange="importJSON(event)">
            </label>
            <button onclick="window.print()" class="px-4 py-2 bg-red-600 hover:bg-red-700 text-white text-xs font-bold rounded-lg shadow-sm transition flex items-center gap-2">
                <i class="fa-solid fa-file-pdf text-sm"></i> Imprimir / Exportar a PDF
            </button>
        </div>
    </div>

    <!-- MAIN PAGE 1 CONTAINER -->
    <div class="page-container p-4 sm:p-6 rounded-xl mb-8">
        
        <!-- Header Brand & Document Info -->
        <div class="grid grid-cols-12 gap-4 pb-4 border-b-2 border-gray-800 items-stretch">
            <div class="col-span-12 md:col-span-3 flex flex-col justify-center items-start">
                <div class="flex items-center gap-2">
                    <svg class="h-10 w-auto" viewBox="0 0 520 120" fill="none" xmlns="http://www.w3.org/2000/svg">
                        <circle cx="50" cy="60" r="45" stroke="#E2001A" stroke-width="16" fill="none"/>
                        <circle cx="50" cy="60" r="22" fill="#E2001A"/>
                        <line x1="95" y1="60" x2="165" y2="60" stroke="#E2001A" stroke-width="14"/>
                        <circle cx="170" cy="60" r="45" stroke="#E2001A" stroke-width="16" fill="none"/>
                        <circle cx="170" cy="60" r="22" fill="#E2001A"/>
                        <line x1="215" y1="60" x2="285" y2="60" stroke="#E2001A" stroke-width="14"/>
                        <path d="M 285 30 C 330 30, 330 60, 285 60 C 240 60, 240 90, 285 90 C 330 90, 330 90, 330 90" stroke="#E2001A" stroke-width="16" fill="none" stroke-linecap="round"/>
                        <text x="350" y="45" font-family="Arial, sans-serif" font-weight="900" font-size="28" fill="#716f6f" letter-spacing="1">AUTOMOTIVE</text>
                        <text x="350" y="75" font-family="Arial, sans-serif" font-weight="900" font-size="28" fill="#716f6f" letter-spacing="1">INTERFACE</text>
                        <text x="350" y="105" font-family="Arial, sans-serif" font-weight="900" font-size="28" fill="#716f6f" letter-spacing="1">SOLUTIONS</text>
                    </svg>
                </div>
            </div>

            <div class="col-span-12 md:col-span-6 text-center flex flex-col justify-center">
                <h2 class="text-xl sm:text-2xl font-black text-gray-900 tracking-tight uppercase">
                    REPORTE DE MEDICIÓN DE PARTÍCULAS
                </h2>
                <p class="text-xs text-gray-500 font-semibold tracking-wider mt-0.5">SISTEMA DE CONTROL DE CALIDAD AMBIENTAL Y SALAS BLANCAS</p>
            </div>

            <div class="col-span-12 md:col-span-3 text-[10px] border border-gray-400 rounded p-1.5 bg-gray-50 flex flex-col justify-between">
                <div class="flex justify-between border-b border-gray-300 pb-0.5">
                    <span class="font-bold text-gray-600">Código de Formato:</span>
                    <span class="font-mono text-gray-800">FOR-CAL-042</span>
                </div>
                <div class="flex justify-between border-b border-gray-300 py-0.5">
                    <span class="font-bold text-gray-600">Revisión:</span>
                    <span class="font-mono text-gray-800">03</span>
                </div>
                <div class="flex justify-between border-b border-gray-300 py-0.5">
                    <span class="font-bold text-gray-600">Emisión:</span>
                    <span class="font-mono text-gray-800">Enero 2025</span>
                </div>
                <div class="flex justify-between pt-0.5">
                    <span class="font-bold text-gray-600">Página:</span>
                    <span class="font-mono text-gray-800">1 de 2</span>
                </div>
            </div>
        </div>

        <!-- General Parameters Grid -->
        <div class="grid grid-cols-12 gap-3 my-4 text-xs">
            <div class="col-span-12 md:col-span-6 grid grid-cols-3 gap-2 bg-gray-50 p-2.5 rounded-lg border border-gray-200">
                <label class="font-semibold text-gray-700 flex flex-col">
                    <span>Fecha de Medición:</span>
                    <input type="date" id="fechaMedicion" class="mt-1 p-1 bg-white border border-gray-300 rounded font-normal text-xs text-gray-800" value="{fecha}">
                </label>
                <label class="font-semibold text-gray-700 flex flex-col">
                    <span>Nombre del Auditor:</span>
                    <input type="text" id="nombreAuditor" class="mt-1 p-1 bg-white border border-gray-300 rounded font-normal text-xs text-gray-800" value="{auditor}">
                </label>
                <label class="font-semibold text-gray-700 flex flex-col">
                    <span>Área de Medición:</span>
                    <input type="text" id="areaMedicion" class="mt-1 p-1 bg-white border border-gray-300 rounded font-normal text-xs text-gray-800" value="{area}">
                </label>
            </div>

            <div class="col-span-12 md:col-span-6 grid grid-cols-3 gap-2 bg-gray-50 p-2.5 rounded-lg border border-gray-200">
                <label class="font-semibold text-gray-700 flex flex-col">
                    <span>Equipo Usado:</span>
                    <input type="text" id="equipoUsado" class="mt-1 p-1 bg-white border border-gray-300 rounded font-normal text-xs text-gray-800" value="{equipo}">
                </label>
                <label class="font-semibold text-gray-700 flex flex-col">
                    <span>Temperatura (°C):</span>
                    <input type="text" id="temperatura" class="mt-1 p-1 bg-white border border-gray-300 rounded font-normal text-xs text-gray-800" value="{temp}">
                </label>
                <label class="font-semibold text-gray-700 flex flex-col">
                    <span>Humedad (%):</span>
                    <input type="text" id="humedad" class="mt-1 p-1 bg-white border border-gray-300 rounded font-normal text-xs text-gray-800" value="{rh}">
                </label>
            </div>
        </div>

        <div class="bg-gray-800 text-white font-bold text-center py-1 rounded-t text-xs uppercase tracking-wider">
            Resultado del Punto de Medición (Partículas / m³)
        </div>

        <!-- 20 Point Table -->
        <div class="overflow-x-auto border border-gray-300 rounded-b mb-4">
            <table class="w-full text-[11px] border-collapse bg-white" id="measurementTable">
                <thead>
                    <tr class="bg-gray-100 text-gray-700 text-center border-b border-gray-300">
                        <th class="p-1 border-r border-gray-300 w-28 text-left pl-2">Muestra de Concentración por M³</th>
                        <th class="p-1 border-r border-gray-300 w-12 bg-gray-200 font-bold">Toma</th>
                        <th class="p-1 border-r border-gray-300 font-bold w-[4.2%] text-center">1</th>
                        <th class="p-1 border-r border-gray-300 font-bold w-[4.2%] text-center">2</th>
                        <th class="p-1 border-r border-gray-300 font-bold w-[4.2%] text-center">3</th>
                        <th class="p-1 border-r border-gray-300 font-bold w-[4.2%] text-center">4</th>
                        <th class="p-1 border-r border-gray-300 font-bold w-[4.2%] text-center">5</th>
                        <th class="p-1 border-r border-gray-300 font-bold w-[4.2%] text-center">6</th>
                        <th class="p-1 border-r border-gray-300 font-bold w-[4.2%] text-center">7</th>
                        <th class="p-1 border-r border-gray-300 font-bold w-[4.2%] text-center">8</th>
                        <th class="p-1 border-r border-gray-300 font-bold w-[4.2%] text-center">9</th>
                        <th class="p-1 border-r border-gray-300 font-bold w-[4.2%] text-center">10</th>
                        <th class="p-1 border-r border-gray-300 font-bold w-[4.2%] text-center">11</th>
                        <th class="p-1 border-r border-gray-300 font-bold w-[4.2%] text-center">12</th>
                        <th class="p-1 border-r border-gray-300 font-bold w-[4.2%] text-center">13</th>
                        <th class="p-1 border-r border-gray-300 font-bold w-[4.2%] text-center">14</th>
                        <th class="p-1 border-r border-gray-300 font-bold w-[4.2%] text-center">15</th>
                        <th class="p-1 border-r border-gray-300 font-bold w-[4.2%] text-center">16</th>
                        <th class="p-1 border-r border-gray-300 font-bold w-[4.2%] text-center">17</th>
                        <th class="p-1 border-r border-gray-300 font-bold w-[4.2%] text-center">18</th>
                        <th class="p-1 border-r border-gray-300 font-bold w-[4.2%] text-center">19</th>
                        <th class="p-1 border-r border-gray-300 font-bold w-[4.2%] text-center">20</th>
                    </tr>
                </thead>
                <tbody id="tableBody">
                </tbody>
            </table>
        </div>

        <!-- Summary Table -->
        <div class="mb-6">
            <div class="text-xs font-bold text-gray-700 uppercase mb-1 flex items-center gap-1.5">
                <i class="fa-solid fa-calculator text-red-600"></i> Resumen de Promedios Generales por Canal
            </div>
            <div class="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs" id="summaryContainer">
            </div>
        </div>

        <!-- Graphs -->
        <div class="space-y-4">
            <div class="border border-gray-300 rounded-lg p-2.5 bg-white shadow-sm">
                <div class="flex justify-between items-center mb-1 px-1">
                    <span class="font-bold text-xs text-gray-800" id="title-c05">Canal: {ch1_name}</span>
                    <span id="badge-05" class="px-2 py-0.5 text-[10px] font-bold rounded-full bg-green-100 text-green-800">CUMPLE ISO</span>
                </div>
                <div class="relative w-full h-40 sm:h-48 chart-wrapper">
                    <canvas id="chart05"></canvas>
                </div>
            </div>

            <div class="border border-gray-300 rounded-lg p-2.5 bg-white shadow-sm">
                <div class="flex justify-between items-center mb-1 px-1">
                    <span class="font-bold text-xs text-gray-800" id="title-c1">Canal: {ch2_name}</span>
                    <span id="badge-1" class="px-2 py-0.5 text-[10px] font-bold rounded-full bg-green-100 text-green-800">CUMPLE ISO</span>
                </div>
                <div class="relative w-full h-40 sm:h-48 chart-wrapper">
                    <canvas id="chart1"></canvas>
                </div>
            </div>

            <div class="border border-gray-300 rounded-lg p-2.5 bg-white shadow-sm">
                <div class="flex justify-between items-center mb-1 px-1">
                    <span class="font-bold text-xs text-gray-800" id="title-c5">Canal: {ch3_name}</span>
                    <span id="badge-5" class="px-2 py-0.5 text-[10px] font-bold rounded-full bg-green-100 text-green-800">CUMPLE ISO</span>
                </div>
                <div class="relative w-full h-40 sm:h-48 chart-wrapper">
                    <canvas id="chart5"></canvas>
                </div>
            </div>
        </div>

    </div>

    <div class="page-break"></div>

    <!-- MAIN PAGE 2 CONTAINER -->
    <div class="page-container p-4 sm:p-6 rounded-xl">
        <div class="flex justify-between items-center border-b-2 border-gray-800 pb-3 mb-4">
            <div>
                <h2 class="text-xl font-black text-gray-900 tracking-tight uppercase">
                    PLANO DE UBICACIÓN Y DISTRIBUCIÓN DE PUNTOS
                </h2>
                <p class="text-xs text-gray-500 font-semibold">Mapeo de Sensores en Planta y Monitoreo Físico</p>
            </div>
            <div class="text-right text-xs">
                <span class="font-bold text-gray-600">Página:</span>
                <span class="font-mono text-gray-800">2 de 2</span>
            </div>
        </div>

        <div class="grid grid-cols-12 gap-6 items-start">
            <div class="col-span-12 lg:col-span-4 bg-gray-50 p-4 rounded-xl border border-gray-200">
                <div class="mb-4">
                    <label class="block text-xs font-bold text-gray-500 uppercase">Área Registrada</label>
                    <input type="text" id="mapAreaTitle" class="text-lg font-black text-gray-800 bg-transparent border-b border-gray-400 w-full focus:outline-none" value="{area}">
                </div>
                <div class="mb-4">
                    <label class="block text-xs font-bold text-gray-500 uppercase">Superficie Total</label>
                    <input type="text" id="mapAreaSize" class="text-md font-bold text-gray-700 bg-transparent border-b border-gray-400 w-full focus:outline-none" value="{area_size}">
                </div>

                <div class="border-t border-gray-300 pt-4 mt-4">
                    <h4 class="font-bold text-xs uppercase text-gray-700 mb-3">Simbología y Estado</h4>
                    
                    <div class="space-y-2 text-xs">
                        <div class="flex items-center gap-2 font-medium text-gray-700">
                            <span class="w-4 h-4 rounded-full bg-blue-600 border border-white shadow-sm inline-block"></span>
                            <span>Puntos de verificación totales (20)</span>
                        </div>
                        <div class="flex items-center gap-2 font-medium text-gray-700">
                            <span class="w-4 h-4 rounded-full bg-sky-600 border border-white shadow-sm inline-block"></span>
                            <span id="passCountText">Dentro de parámetros: 20</span>
                        </div>
                        <div class="flex items-center gap-2 font-medium text-gray-700">
                            <span class="w-4 h-4 rounded-full bg-red-600 border border-white shadow-sm inline-block"></span>
                            <span id="failCountText">Fuera de parámetros: 0</span>
                        </div>
                    </div>
                </div>

                <div class="mt-6 pt-4 border-t border-gray-300 no-print">
                    <label class="block text-xs font-bold text-gray-700 mb-1">Cargar Imagen de Plano Personalizado:</label>
                    <input type="file" id="blueprintUpload" accept="image/*" onchange="uploadBlueprint(event)" class="text-xs text-gray-500 file:mr-2 file:py-1.5 file:px-3 file:rounded-md file:border-0 file:text-xs file:font-semibold file:bg-red-50 file:text-red-700 hover:file:bg-red-100">
                    <p class="text-[10px] text-gray-400 mt-1">Puedes arrastrar las marcas con el ratón para posicionarlas en el plano.</p>
                </div>
            </div>

            <div class="col-span-12 lg:col-span-8">
                <div id="mapContainer" class="relative w-full aspect-[4/3] bg-gray-100 border-2 border-gray-400 rounded-lg overflow-hidden shadow-inner flex items-center justify-center">
                    
                    <svg id="defaultBlueprint" class="w-full h-full opacity-60" viewBox="0 0 800 600" xmlns="http://www.w3.org/2000/svg">
                        <rect width="800" height="600" fill="#f8fafc"/>
                        <defs>
                            <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
                                <path d="M 40 0 L 0 0 0 40" fill="none" stroke="#e2e8f0" stroke-width="1"/>
                            </pattern>
                        </defs>
                        <rect width="800" height="600" fill="url(#grid)" />
                        <rect x="40" y="40" width="720" height="520" fill="none" stroke="#334155" stroke-width="4"/>
                        <rect x="60" y="60" width="180" height="160" fill="#e0f2fe" stroke="#475569" stroke-width="2"/>
                        <text x="70" y="85" font-family="sans-serif" font-size="12" font-weight="bold" fill="#334155">REWORK AREA</text>

                        <rect x="260" y="60" width="220" height="120" fill="#f1f5f9" stroke="#475569" stroke-width="2"/>
                        <text x="270" y="85" font-family="sans-serif" font-size="12" font-weight="bold" fill="#334155">CHARGE PORT LINE</text>

                        <rect x="500" y="60" width="240" height="180" fill="#f1f5f9" stroke="#475569" stroke-width="2"/>
                        <text x="510" y="85" font-family="sans-serif" font-size="12" font-weight="bold" fill="#334155">ENERGY CHARGE</text>

                        <rect x="60" y="240" width="200" height="200" fill="#f1f5f9" stroke="#475569" stroke-width="2"/>
                        <text x="70" y="265" font-family="sans-serif" font-size="12" font-weight="bold" fill="#334155">X-RAY INSPECTION</text>

                        <rect x="280" y="220" width="200" height="220" fill="#f1f5f9" stroke="#475569" stroke-width="2"/>
                        <text x="290" y="245" font-family="sans-serif" font-size="12" font-weight="bold" fill="#334155">PIN STITCH 1 & 2</text>

                        <rect x="500" y="260" width="240" height="280" fill="#f1f5f9" stroke="#475569" stroke-width="2"/>
                        <text x="510" y="285" font-family="sans-serif" font-size="12" font-weight="bold" fill="#334155">FINAL ASSEMBLY</text>
                    </svg>

                    <img id="customBlueprintImg" class="absolute inset-0 w-full h-full object-contain hidden" alt="Plano de Ubicación">

                    <div id="pinsLayer" class="absolute inset-0 w-full h-full pointer-events-auto">
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        const LIMITS = {json_limits};

        const defaultPinCoords = [
            {{ x: 12, y: 52 }}, {{ x: 26, y: 22 }}, {{ x: 10, y: 18 }}, {{ x: 22, y: 12 }},
            {{ x: 38, y: 15 }}, {{ x: 88, y: 18 }}, {{ x: 78, y: 28 }}, {{ x: 52, y: 26 }},
            {{ x: 42, y: 44 }}, {{ x: 16, y: 58 }}, {{ x: 40, y: 68 }}, {{ x: 38, y: 84 }},
            {{ x: 62, y: 88 }}, {{ x: 72, y: 72 }}, {{ x: 52, y: 58 }}, {{ x: 74, y: 58 }},
            {{ x: 70, y: 44 }}, {{ x: 86, y: 44 }}, {{ x: 88, y: 74 }}, {{ x: 82, y: 86 }}
        ];

        let reportData = {json_report_data};

        let chart05Instance = null;
        let chart1Instance = null;
        let chart5Instance = null;

        const initialValues = JSON.parse(JSON.stringify(reportData));

        window.onload = function() {{
            buildTableRows();
            fillInputsFromData();
            initCharts();
            renderMapPins();
        }};

        function buildTableRows() {{
            const tbody = document.getElementById('tableBody');
            tbody.innerHTML = '';

            const channels = [
                {{ key: 'c05', label: '{ch1_name} (Max ' + LIMITS.c05.toLocaleString() + ')', limit: LIMITS.c05 }},
                {{ key: 'c1',  label: '{ch2_name} (Max ' + LIMITS.c1.toLocaleString() + ')',  limit: LIMITS.c1 }},
                {{ key: 'c5',  label: '{ch3_name} (Max ' + LIMITS.c5.toLocaleString() + ')',   limit: LIMITS.c5 }}
            ];

            channels.forEach(ch => {{
                for (let t = 1; t <= 2; t++) {{
                    const tr = document.createElement('tr');
                    tr.className = "border-b border-gray-200 hover:bg-gray-50";

                    if (t === 1) {{
                        const tdLabel = document.createElement('td');
                        tdLabel.rowSpan = 2;
                        tdLabel.className = "p-1.5 border-r border-gray-300 font-bold bg-gray-50 text-gray-800 text-[11px]";
                        tdLabel.innerText = ch.label;
                        tr.appendChild(tdLabel);
                    }}

                    const tdTake = document.createElement('td');
                    tdTake.className = "p-1 border-r border-gray-300 font-bold text-center bg-gray-100 text-gray-700";
                    tdTake.innerText = t;
                    tr.appendChild(tdTake);

                    for (let p = 0; p < 20; p++) {{
                        const tdInput = document.createElement('td');
                        tdInput.className = "p-0.5 border-r border-gray-200 text-center";
                        
                        const input = document.createElement('input');
                        input.type = "text";
                        input.className = "cell-input";
                        input.dataset.channel = ch.key;
                        input.dataset.take = `t${{t}}`;
                        input.dataset.point = p;
                        input.dataset.limit = ch.limit;

                        input.oninput = function() {{
                            formatInputAndCalculate(this);
                        }};

                        tdInput.appendChild(input);
                        tr.appendChild(tdInput);
                    }}

                    tbody.appendChild(tr);
                }}
            }});
        }}

        function formatInputAndCalculate(inputEl) {{
            let valStr = inputEl.value.replace(/,/g, '').trim();
            let num = parseInt(valStr, 10);

            const chKey = inputEl.dataset.channel;
            const takeKey = inputEl.dataset.take;
            const pIdx = parseInt(inputEl.dataset.point, 10);
            const limit = parseInt(inputEl.dataset.limit, 10);

            if (!isNaN(num)) {{
                reportData[chKey][takeKey][pIdx] = num;
                inputEl.value = num.toLocaleString('en-US');

                if (num > limit) {{
                    inputEl.classList.add('out-of-spec');
                    inputEl.classList.remove('in-spec');
                }} else {{
                    inputEl.classList.remove('out-of-spec');
                    inputEl.classList.add('in-spec');
                }}
            }} else {{
                reportData[chKey][takeKey][pIdx] = 0;
                inputEl.classList.remove('out-of-spec', 'in-spec');
            }}

            recalculateAll();
        }}

        function fillInputsFromData() {{
            const inputs = document.querySelectorAll('.cell-input');
            inputs.forEach(input => {{
                const chKey = input.dataset.channel;
                const takeKey = input.dataset.take;
                const pIdx = parseInt(input.dataset.point, 10);
                const limit = parseInt(input.dataset.limit, 10);

                const val = reportData[chKey][takeKey][pIdx];
                if (val !== undefined && val !== null) {{
                    input.value = val > 0 ? val.toLocaleString('en-US') : (val === 0 ? '0' : '');
                    if (val > limit) {{
                        input.classList.add('out-of-spec');
                        input.classList.remove('in-spec');
                    }} else if (val >= 0) {{
                        input.classList.remove('out-of-spec');
                        input.classList.add('in-spec');
                    }}
                }}
            }});

            recalculateAll();
        }}

        function fillSampleData() {{
            reportData = JSON.parse(JSON.stringify(initialValues));
            fillInputsFromData();
        }}

        function clearData() {{
            const inputs = document.querySelectorAll('.cell-input');
            inputs.forEach(input => {{
                input.value = '';
                input.classList.remove('out-of-spec', 'in-spec');
            }});

            reportData = {{
                c05: {{ t1: Array(20).fill(0), t2: Array(20).fill(0) }},
                c1:  {{ t1: Array(20).fill(0), t2: Array(20).fill(0) }},
                c5:  {{ t1: Array(20).fill(0), t2: Array(20).fill(0) }}
            }};

            recalculateAll();
        }}

        function recalculateAll() {{
            updateSummaryCards();
            updateCharts();
            updateMapPinStatuses();
        }}

        function getChannelAvg(chKey) {{
            const t1 = reportData[chKey].t1;
            const t2 = reportData[chKey].t2;

            const sumT1 = t1.reduce((a, b) => a + b, 0);
            const sumT2 = t2.reduce((a, b) => a + b, 0);

            const countT1 = t1.filter(v => v > 0).length || 1;
            const countT2 = t2.filter(v => v > 0).length || 1;

            const avgT1 = Math.round(sumT1 / countT1);
            const avgT2 = Math.round(sumT2 / countT2);
            const avgGlobal = Math.round((avgT1 + avgT2) / 2);

            return {{ avgT1, avgT2, avgGlobal }};
        }}

        function updateSummaryCards() {{
            const container = document.getElementById('summaryContainer');
            container.innerHTML = '';

            const channels = [
                {{ key: 'c05', name: '{ch1_name}', limitName: 'Max ' + LIMITS.c05.toLocaleString(), limit: LIMITS.c05 }},
                {{ key: 'c1',  name: '{ch2_name}', limitName: 'Max ' + LIMITS.c1.toLocaleString(),  limit: LIMITS.c1 }},
                {{ key: 'c5',  name: '{ch3_name}', limitName: 'Max ' + LIMITS.c5.toLocaleString(),   limit: LIMITS.c5 }}
            ];

            channels.forEach(ch => {{
                const {{ avgT1, avgT2, avgGlobal }} = getChannelAvg(ch.key);
                const isExceeded = avgGlobal > ch.limit || reportData[ch.key].t1.some(v => v > ch.limit) || reportData[ch.key].t2.some(v => v > ch.limit);

                const badgeEl = document.getElementById(`badge-${{ch.key === 'c05' ? '05' : ch.key === 'c1' ? '1' : '5'}}`);
                if (badgeEl) {{
                    if (isExceeded) {{
                        badgeEl.innerText = "EXCEDE LÍMITE ISO";
                        badgeEl.className = "px-2 py-0.5 text-[10px] font-bold rounded-full bg-red-100 text-red-800";
                    }} else {{
                        badgeEl.innerText = "CUMPLE ISO";
                        badgeEl.className = "px-2 py-0.5 text-[10px] font-bold rounded-full bg-green-100 text-green-800";
                    }}
                }}

                const cardHtml = `
                    <div class="border ${{isExceeded ? 'border-red-300 bg-red-50' : 'border-gray-200 bg-gray-50'}} rounded-lg p-2.5 flex items-center justify-between">
                        <div class="font-bold text-gray-800 border-r border-gray-300 pr-3">
                            <span class="block text-sm font-extrabold ${{isExceeded ? 'text-red-700' : 'text-gray-900'}}">${{ch.name}}</span>
                            <span class="text-[10px] text-gray-500 font-normal">(${{ch.limitName}})</span>
                        </div>

                        <div class="grid grid-cols-2 gap-x-3 text-center text-[10px]">
                            <div>
                                <span class="block text-gray-500 font-semibold">Prom Toma 1</span>
                                <span class="font-mono font-bold text-gray-800">${{avgT1.toLocaleString()}}</span>
                            </div>
                            <div>
                                <span class="block text-gray-500 font-semibold">Prom Toma 2</span>
                                <span class="font-mono font-bold text-gray-800">${{avgT2.toLocaleString()}}</span>
                            </div>
                        </div>

                        <div class="border-l border-gray-300 pl-3 text-right">
                            <span class="block text-[10px] text-gray-500 font-bold uppercase">Prom. General</span>
                            <span class="font-mono font-extrabold text-xs ${{isExceeded ? 'text-red-600' : 'text-blue-700'}}">${{avgGlobal.toLocaleString()}}</span>
                        </div>
                    </div>
                `;

                container.insertAdjacentHTML('beforeend', cardHtml);
            }});
        }}

        function initCharts() {{
            const labels = Array.from({{length: 20}}, (_, i) => `${{i + 1}}`);

            const createConfig = (chKey, limit, title) => {{
                return {{
                    type: 'line',
                    data: {{
                        labels: labels,
                        datasets: [
                            {{
                                label: 'Toma 1',
                                data: reportData[chKey].t1,
                                borderColor: '#0284c7',
                                backgroundColor: 'rgba(2, 132, 199, 0.1)',
                                borderWidth: 2,
                                pointRadius: 3,
                                pointHoverRadius: 5,
                                tension: 0.2
                            }},
                            {{
                                label: 'Toma 2',
                                data: reportData[chKey].t2,
                                borderColor: '#0d9488',
                                backgroundColor: 'rgba(13, 148, 136, 0.1)',
                                borderWidth: 2,
                                pointRadius: 3,
                                pointHoverRadius: 5,
                                tension: 0.2
                            }},
                            {{
                                label: `Límite ISO (${{limit.toLocaleString()}})`,
                                data: Array(20).fill(limit),
                                borderColor: '#ef4444',
                                borderWidth: 1.5,
                                borderDash: [4, 4],
                                pointRadius: 0,
                                fill: false
                            }}
                        ]
                    }},
                    options: {{
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {{
                            legend: {{
                                display: true,
                                position: 'top',
                                labels: {{ boxWidth: 12, fontSize: 10, padding: 8 }}
                            }},
                            tooltip: {{
                                callbacks: {{
                                    label: function(context) {{
                                        return `${{context.dataset.label}}: ${{context.raw.toLocaleString()}} part/m³`;
                                    }}
                                }}
                            }}
                        }},
                        scales: {{
                            x: {{
                                grid: {{ display: true, color: '#f1f5f9' }},
                                ticks: {{ font: {{ size: 9 }} }}
                            }},
                            y: {{
                                grid: {{ color: '#e2e8f0' }},
                                ticks: {{
                                    font: {{ size: 9 }},
                                    callback: function(value) {{ return value.toLocaleString(); }}
                                }}
                            }}
                        }}
                    }}
                }};
            }};

            const ctx05 = document.getElementById('chart05').getContext('2d');
            chart05Instance = new Chart(ctx05, createConfig('c05', LIMITS.c05, '{ch1_name}'));

            const ctx1 = document.getElementById('chart1').getContext('2d');
            chart1Instance = new Chart(ctx1, createConfig('c1', LIMITS.c1, '{ch2_name}'));

            const ctx5 = document.getElementById('chart5').getContext('2d');
            chart5Instance = new Chart(ctx5, createConfig('c5', LIMITS.c5, '{ch3_name}'));
        }}

        function updateCharts() {{
            if (!chart05Instance) return;

            chart05Instance.data.datasets[0].data = reportData.c05.t1;
            chart05Instance.data.datasets[1].data = reportData.c05.t2;
            chart05Instance.update();

            chart1Instance.data.datasets[0].data = reportData.c1.t1;
            chart1Instance.data.datasets[1].data = reportData.c1.t2;
            chart1Instance.update();

            chart5Instance.data.datasets[0].data = reportData.c5.t1;
            chart5Instance.data.datasets[1].data = reportData.c5.t2;
            chart5Instance.update();
        }}

        function renderMapPins() {{
            const pinsLayer = document.getElementById('pinsLayer');
            pinsLayer.innerHTML = '';

            defaultPinCoords.forEach((coord, i) => {{
                const pIdx = i;
                const pin = document.createElement('div');
                pin.className = 'map-pin pass';
                pin.id = `pin-${{pIdx + 1}}`;
                pin.innerText = pIdx + 1;
                pin.style.left = `${{coord.x}}%`;
                pin.style.top = `${{coord.y}}%`;

                makeDraggable(pin);
                pinsLayer.appendChild(pin);
            }});

            updateMapPinStatuses();
        }}

        function updateMapPinStatuses() {{
            let failCount = 0;
            let passCount = 0;

            for (let p = 0; p < 20; p++) {{
                const pin = document.getElementById(`pin-${{p + 1}}`);
                if (!pin) continue;

                const c05Exceed = reportData.c05.t1[p] > LIMITS.c05 || reportData.c05.t2[p] > LIMITS.c05;
                const c1Exceed  = reportData.c1.t1[p]  > LIMITS.c1  || reportData.c1.t2[p]  > LIMITS.c1;
                const c5Exceed  = reportData.c5.t1[p]  > LIMITS.c5  || reportData.c5.t2[p]  > LIMITS.c5;

                if (c05Exceed || c1Exceed || c5Exceed) {{
                    pin.className = 'map-pin fail';
                    failCount++;
                }} else {{
                    pin.className = 'map-pin pass';
                    passCount++;
                }}
            }}

            document.getElementById('passCountText').innerText = `Dentro de parámetros: ${{passCount}}`;
            document.getElementById('failCountText').innerText = `Fuera de parámetros: ${{failCount}}`;
        }}

        function makeDraggable(element) {{
            let isDragging = false;
            let container = document.getElementById('mapContainer');

            element.addEventListener('mousedown', startDrag);
            element.addEventListener('touchstart', startDrag, {{ passive: false }});

            function startDrag(e) {{
                isDragging = true;
                e.preventDefault();

                document.addEventListener('mousemove', onMove);
                document.addEventListener('touchmove', onMove, {{ passive: false }});
                document.addEventListener('mouseup', stopDrag);
                document.addEventListener('touchend', stopDrag);
            }}

            function onMove(e) {{
                if (!isDragging) return;
                e.preventDefault();

                let rect = container.getBoundingClientRect();
                let clientX = e.clientX || (e.touches && e.touches[0].clientX);
                let clientY = e.clientY || (e.touches && e.touches[0].clientY);

                let x = ((clientX - rect.left) / rect.width) * 100;
                let y = ((clientY - rect.top) / rect.height) * 100;

                x = Math.max(2, Math.min(98, x));
                y = Math.max(2, Math.min(98, y));

                element.style.left = `${{x}}%`;
                element.style.top = `${{y}}%`;
            }}

            function stopDrag() {{
                isDragging = false;
                document.removeEventListener('mousemove', onMove);
                document.removeEventListener('touchmove', onMove);
                document.removeEventListener('mouseup', stopDrag);
                document.removeEventListener('touchend', stopDrag);
            }}
        }}

        function uploadBlueprint(event) {{
            const file = event.target.files[0];
            if (file) {{
                const reader = new FileReader();
                reader.onload = function(e) {{
                    const img = document.getElementById('customBlueprintImg');
                    const svg = document.getElementById('defaultBlueprint');
                    img.src = e.target.result;
                    img.classList.remove('hidden');
                    svg.classList.add('hidden');
                }};
                reader.readAsDataURL(file);
            }}
        }}

        function exportJSON() {{
            const meta = {{
                fecha: document.getElementById('fechaMedicion').value,
                auditor: document.getElementById('nombreAuditor').value,
                area: document.getElementById('areaMedicion').value,
                equipo: document.getElementById('equipoUsado').value,
                temperatura: document.getElementById('temperatura').value,
                humedad: document.getElementById('humedad').value,
                data: reportData
            }};

            const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(meta, null, 2));
            const downloadAnchor = document.createElement('a');
            downloadAnchor.setAttribute("href", dataStr);
            downloadAnchor.setAttribute("download", `Reporte_Particulas_${{meta.area}}_${{meta.fecha}}.json`);
            document.body.appendChild(downloadAnchor);
            downloadAnchor.click();
            downloadAnchor.remove();
        }}

        function importJSON(event) {{
            const file = event.target.files[0];
            if (file) {{
                const reader = new FileReader();
                reader.onload = function(e) {{
                    try {{
                        const imported = JSON.parse(e.target.result);
                        if (imported.fecha) document.getElementById('fechaMedicion').value = imported.fecha;
                        if (imported.auditor) document.getElementById('nombreAuditor').value = imported.auditor;
                        if (imported.area) document.getElementById('areaMedicion').value = imported.area;
                        if (imported.equipo) document.getElementById('equipoUsado').value = imported.equipo;
                        if (imported.temperatura) document.getElementById('temperatura').value = imported.temperatura;
                        if (imported.humedad) document.getElementById('humedad').value = imported.humedad;

                        if (imported.data) {{
                            reportData = imported.data;
                            fillInputsFromData();
                        }}
                    }} catch (err) {{
                        alert("El archivo no tiene un formato JSON válido.");
                    }}
                }};
                reader.readAsText(file);
            }}
        }}
    </script>
</body>
</html>"""
    return html_template
