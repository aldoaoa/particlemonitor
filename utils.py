import pandas as pd
import numpy as np
import json
import re
import io
import os
import base64
import csv
import struct
import random

# Standard ISO 14644-1 limits in particles per m3
# ISO 8: 0.5um: 3,520,000 | 1.0um: 832,000 | 5.0um: 29,300
ISO_LIMITS_M3 = {
    "ISO 1": {"0.1": 10, "0.2": 2, "0.3": 0, "0.5": 0, "1.0": 0, "5.0": 0},
    "ISO 2": {"0.1": 100, "0.2": 24, "0.3": 10, "0.5": 4, "1.0": 0, "5.0": 0},
    "ISO 3": {"0.1": 1000, "0.2": 237, "0.3": 102, "0.5": 35, "1.0": 8, "5.0": 0},
    "ISO 4": {"0.1": 10000, "0.2": 2370, "0.3": 1020, "0.5": 352, "1.0": 83, "5.0": 29},
    "ISO 5": {"0.1": 100000, "0.2": 23700, "0.3": 10200, "0.5": 3520, "1.0": 832, "5.0": 29},
    "ISO 6": {"0.1": 1000000, "0.2": 237000, "0.3": 102000, "0.5": 35200, "1.0": 8320, "5.0": 293},
    "ISO 7": {"0.5": 352000, "1.0": 83200, "5.0": 2930},
    "ISO 8": {"0.5": 3520000, "1.0": 832000, "5.0": 29300},
    "ISO 9": {"0.5": 35200000, "1.0": 8320000, "5.0": 293000}
}

DEFAULT_LIMITS = {
    "c05": 3520000,
    "c1": 832000,
    "c5": 29300
}

def generate_random_iso_data(iso_class="ISO 8", limits=None, num_rooms=6, points_per_room=20):
    """
    Generates realistic, acceptable particle measurement data tailored to the specified ISO class limits.
    All generated values are strictly compliant with ISO maximum thresholds and feature natural sensor variance.
    """
    if limits is None:
        limits = ISO_LIMITS_M3.get(iso_class, ISO_LIMITS_M3["ISO 8"])

    lim_c05 = int(limits.get("0.5", limits.get("c05", 3520000)))
    lim_c1  = int(limits.get("1.0", limits.get("c1", 832000)))
    lim_c5  = int(limits.get("5.0", limits.get("c5", 29300)))

    multi_room_data = {}

    for r in range(1, num_rooms + 1):
        room_name = f"Cuarto {r}"
        
        # Base concentration level for this room (15% to 40% of max limit)
        base_c05 = lim_c05 * random.uniform(0.15, 0.40) if lim_c05 > 0 else 0
        base_c1  = min(lim_c1 * random.uniform(0.15, 0.35) if lim_c1 > 0 else 0, base_c05 * 0.25)
        base_c5  = min(lim_c5 * random.uniform(0.08, 0.30) if lim_c5 > 0 else 0, base_c1 * 0.15)

        t1_c05, t2_c05 = [], []
        t1_c1,  t2_c1  = [], []
        t1_c5,  t2_c5  = [], []

        for p in range(20):
            if p < points_per_room:
                pt_factor = random.uniform(0.80, 1.20)
                
                v05_1 = int(round(base_c05 * pt_factor * random.uniform(0.95, 1.05)))
                v05_2 = int(round(base_c05 * pt_factor * random.uniform(0.95, 1.05)))

                v1_1  = int(round(base_c1 * pt_factor * random.uniform(0.92, 1.08)))
                v1_2  = int(round(base_c1 * pt_factor * random.uniform(0.92, 1.08)))

                v5_1  = int(round(base_c5 * pt_factor * random.uniform(0.85, 1.15)))
                v5_2  = int(round(base_c5 * pt_factor * random.uniform(0.85, 1.15)))

                # Strictly cap below max ISO limits
                v05_1 = min(max(0, v05_1), max(0, lim_c05 - 1)) if lim_c05 > 0 else 0
                v05_2 = min(max(0, v05_2), max(0, lim_c05 - 1)) if lim_c05 > 0 else 0

                v1_1  = min(max(0, v1_1), max(0, lim_c1 - 1)) if lim_c1 > 0 else 0
                v1_2  = min(max(0, v1_2), max(0, lim_c1 - 1)) if lim_c1 > 0 else 0

                v5_1  = min(max(0, v5_1), max(0, lim_c5 - 1)) if lim_c5 > 0 else 0
                v5_2  = min(max(0, v5_2), max(0, lim_c5 - 1)) if lim_c5 > 0 else 0
            else:
                v05_1, v05_2 = -1, -1
                v1_1,  v1_2  = -1, -1
                v5_1,  v5_2  = -1, -1

            t1_c05.append(v05_1)
            t2_c05.append(v05_2)
            t1_c1.append(v1_1)
            t2_c1.append(v1_2)
            t1_c5.append(v5_1)
            t2_c5.append(v5_2)

        multi_room_data[room_name] = {
            "c05": {"t1": t1_c05, "t2": t2_c05},
            "c1":  {"t1": t1_c1,  "t2": t2_c1},
            "c5":  {"t1": t1_c5,  "t2": t2_c5}
        }

    return multi_room_data

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

def load_room_maps_and_coordinates(project_dir=None):
    """
    Loads PNG maps (cuarto1.png .. cuarto6.png) and coordinates_cleanroom.csv from img/ folder.
    Converts image pixel coordinates (X, Y) into percentage coordinates relative to image width and height.
    """
    if project_dir is None:
        project_dir = os.path.dirname(os.path.abspath(__file__))
    
    img_dir = os.path.join(project_dir, "img")
    csv_path = os.path.join(img_dir, "coordenadas_cleanroom.csv")
    
    coords_by_room = {f"Cuarto {r}": [] for r in range(1, 7)}
    
    if os.path.exists(csv_path):
        try:
            with open(csv_path, mode="r", encoding="utf-8-sig") as f:
                reader = csv.reader(f)
                lines = list(reader)
                for row in lines[2:]:
                    if not row or len(row) < 13:
                        continue
                    pt_num_str = row[0].strip()
                    if not pt_num_str.isdigit():
                        continue
                    
                    pt_num = int(pt_num_str)
                    
                    for r in range(1, 7):
                        x_col = (r - 1) * 2 + 1
                        y_col = (r - 1) * 2 + 2
                        x_val = row[x_col].strip() if x_col < len(row) else ""
                        y_val = row[y_col].strip() if y_col < len(row) else ""
                        
                        if x_val != "" and y_val != "":
                            try:
                                coords_by_room[f"Cuarto {r}"].append({
                                    "point": pt_num,
                                    "x": float(x_val),
                                    "y": float(y_val)
                                })
                            except ValueError:
                                pass
        except Exception as e:
            print(f"Error reading coordinates CSV: {e}")

    room_maps = {}
    
    for r in range(1, 7):
        room_name = f"Cuarto {r}"
        img_path = os.path.join(img_dir, f"cuarto{r}.png")
        
        b64_str = ""
        w, h = 800, 600
        
        if os.path.exists(img_path):
            try:
                with open(img_path, "rb") as img_file:
                    img_bytes = img_file.read()
                    b64_str = base64.b64encode(img_bytes).decode("utf-8")
                    
                    if img_bytes.startswith(b'\x89PNG\r\n\x1a\n') and len(img_bytes) >= 24:
                        w, h = struct.unpack(">II", img_bytes[16:24])
            except Exception as e:
                print(f"Error loading image {img_path}: {e}")
        
        pin_coords = []
        raw_coords = coords_by_room.get(room_name, [])
        for c in raw_coords:
            x_pct = round((c["x"] / w) * 100, 2)
            y_pct = round((c["y"] / h) * 100, 2)
            pin_coords.append({
                "point": c["point"],
                "x_pct": x_pct,
                "y_pct": y_pct,
                "x_px": c["x"],
                "y_px": c["y"]
            })
            
        room_maps[room_name] = {
            "image_b64": b64_str,
            "width": w,
            "height": h,
            "pins": pin_coords
        }
        
    return room_maps


def process_excel_data(file_source, mapping_mode="interleaved"):
    """
    Reads Excel file and extracts measurement data for 6 rooms (Cuarto 1 to Cuarto 6).
    Expected columns: Time, Temp, RH, CH1 Size, CH2 Size, CH3 Size, CntsCumM3 CH1, CntsCumM3 CH2, CntsCumM3 CH3
    Each room uses up to 40 rows (20 points x 2 takes). Unmeasured missing points are set to -1 (blank).
    """
    if isinstance(file_source, pd.DataFrame):
        df = file_source.copy()
    elif isinstance(file_source, bytes):
        df = pd.read_excel(io.BytesIO(file_source))
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

    v_cnt1_all = pd.to_numeric(df[col_cnt1], errors='coerce').fillna(-1).tolist() if col_cnt1 else []
    v_cnt2_all = pd.to_numeric(df[col_cnt2], errors='coerce').fillna(-1).tolist() if col_cnt2 else []
    v_cnt3_all = pd.to_numeric(df[col_cnt3], errors='coerce').fillna(-1).tolist() if col_cnt3 else []

    num_total_rows = len(v_cnt1_all)

    multi_room_data = {}
    
    for r in range(1, 7):
        room_name = f"Cuarto {r}"
        start_idx = (r - 1) * 40
        end_idx = r * 40

        v_cnt1 = v_cnt1_all[start_idx:end_idx] if start_idx < len(v_cnt1_all) else []
        v_cnt2 = v_cnt2_all[start_idx:end_idx] if start_idx < len(v_cnt2_all) else []
        v_cnt3 = v_cnt3_all[start_idx:end_idx] if start_idx < len(v_cnt3_all) else []

        room_data = {
            "c05": {"t1": [-1]*20, "t2": [-1]*20},
            "c1":  {"t1": [-1]*20, "t2": [-1]*20},
            "c5":  {"t1": [-1]*20, "t2": [-1]*20}
        }

        channels = [("c05", v_cnt1), ("c1", v_cnt2), ("c5", v_cnt3)]

        for key, vals in channels:
            t1_arr = [-1]*20
            t2_arr = [-1]*20

            if mapping_mode == "interleaved":
                for p in range(20):
                    idx1 = p * 2
                    idx2 = p * 2 + 1
                    if idx1 < len(vals):
                        v1 = vals[idx1]
                        t1_arr[p] = int(round(v1)) if v1 >= 0 else -1
                    if idx2 < len(vals):
                        v2 = vals[idx2]
                        t2_arr[p] = int(round(v2)) if v2 >= 0 else -1
                    elif idx1 < len(vals):
                        v1 = vals[idx1]
                        t2_arr[p] = int(round(v1)) if v1 >= 0 else -1
            else:
                for p in range(20):
                    if p < len(vals):
                        v1 = vals[p]
                        t1_arr[p] = int(round(v1)) if v1 >= 0 else -1
                    if p + 20 < len(vals):
                        v2 = vals[p + 20]
                        t2_arr[p] = int(round(v2)) if v2 >= 0 else -1
                    elif p < len(vals):
                        v1 = vals[p]
                        t2_arr[p] = int(round(v1)) if v1 >= 0 else -1

            room_data[key]["t1"] = t1_arr
            room_data[key]["t2"] = t2_arr

        multi_room_data[room_name] = room_data

    meta = {
        "avg_temp": round(avg_temp, 2),
        "avg_rh": round(avg_rh, 2),
        "ch1_size": ch1_size_val,
        "ch2_size": ch2_size_val,
        "ch3_size": ch3_size_val,
        "num_rows_read": num_total_rows
    }

    return multi_room_data, meta


def generate_full_html_report(metadata, multi_room_data, limits=None, room_maps=None):
    """
    Generates complete HTML report string optimized for Portrait PDF export (Vertical).
    Guarantees no internal clipping or truncation across page breaks.
    """
    if limits is None:
        limits = DEFAULT_LIMITS
        
    if room_maps is None:
        room_maps = load_room_maps_and_coordinates()

    json_multi_room = json.dumps(multi_room_data)
    json_limits = json.dumps(limits)
    json_room_maps = json.dumps(room_maps)

    fecha = str(metadata.get("fecha", "2025-07-21"))
    auditor = str(metadata.get("auditor", "Armando Reyes"))
    equipo = str(metadata.get("equipo", "BCS-QRO-LAB-ANA001, Particles Plus 8503."))
    temp = str(metadata.get("temp", "21.15"))
    rh = str(metadata.get("rh", "48.32"))
    ch1_name = str(metadata.get("ch1_name", "0.5 µm"))
    ch2_name = str(metadata.get("ch2_name", "1.0 µm"))
    ch3_name = str(metadata.get("ch3_name", "5.0 µm"))
    area_size = str(metadata.get("area_size", "1662.81 m²"))

    html_template = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Reporte de Medición de Partículas (Cuartos 1-6) - BCS</title>
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
            padding: 1px 2px;
            font-size: 0.65rem;
            text-align: right;
            border: 1px solid #d1d5db;
            border-radius: 2px;
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
            max-width: 1200px;
            margin: 0 auto 1.5rem auto;
            background: #ffffff;
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.1);
        }}

        /* STRICT PORTRAIT PRINTING & ZERO-TRUNCATION CSS */
        @media print {{
            body {{
                background: #ffffff !important;
                padding: 0 !important;
                margin: 0 !important;
            }}
            .no-print {{
                display: none !important;
            }}
            .page-break {{
                page-break-before: always !important;
                break-before: page !important;
            }}
            .page-container {{
                box-shadow: none !important;
                max-width: 100% !important;
                width: 100% !important;
                padding: 0 !important;
                margin: 0 0 10px 0 !important;
                page-break-inside: avoid !important;
                break-inside: avoid !important;
            }}
            .chart-wrapper {{
                height: 135px !important;
            }}
            tr, table, tbody, td, th, .chart-wrapper, .map-pin, img, .summary-card-block {{
                page-break-inside: avoid !important;
                break-inside: avoid !important;
            }}
            @page {{
                size: letter portrait;
                margin: 6mm 5mm;
            }}
        }}

        .map-pin {{
            position: absolute;
            width: 22px;
            height: 22px;
            border-radius: 50%;
            color: white;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 0.65rem;
            font-weight: 700;
            cursor: move;
            user-select: none;
            box-shadow: 0 2px 5px rgba(0,0,0,0.3);
            transform: translate(-50%, -50%);
            transition: background-color 0.3s ease, transform 0.1s ease;
        }}
        .map-pin:hover {{
            transform: translate(-50%, -50%) scale(1.25);
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
<body class="p-2 sm:p-4">

    <!-- Action Bar -->
    <div class="no-print max-w-[1200px] mx-auto mb-4 bg-white p-4 rounded-xl shadow-md border border-gray-200 flex flex-wrap items-center justify-between gap-3">
        <div class="flex items-center space-x-3">
            <div class="p-2 bg-red-50 rounded-lg border border-red-100">
                <i class="fa-solid fa-microscope text-red-600 text-xl"></i>
            </div>
            <div>
                <h1 class="font-bold text-gray-800 text-lg leading-tight">Reporte Multicuarto (Cuartos 1 a 6)</h1>
                <p class="text-xs text-gray-500">Monitoreo Ambiental Completo - Norma ISO 14644-1 (ISO 8) - PDF Vertical</p>
            </div>
        </div>

        <!-- Room Selector Bar (Screen Mode) -->
        <div class="flex items-center gap-1.5 bg-gray-100 p-1 rounded-lg border border-gray-300">
            <span class="text-xs font-bold text-gray-600 px-2">Ver Cuarto:</span>
            <button onclick="switchRoom('all')" id="btn-room-all" class="px-2.5 py-1 text-xs font-bold rounded bg-red-600 text-white shadow-sm">Todos (Impresión Vertical)</button>
            <button onclick="switchRoom('Cuarto 1')" id="btn-room-1" class="px-2.5 py-1 text-xs font-bold rounded bg-white text-gray-700 border hover:bg-gray-200">Cuarto 1</button>
            <button onclick="switchRoom('Cuarto 2')" id="btn-room-2" class="px-2.5 py-1 text-xs font-bold rounded bg-white text-gray-700 border hover:bg-gray-200">Cuarto 2</button>
            <button onclick="switchRoom('Cuarto 3')" id="btn-room-3" class="px-2.5 py-1 text-xs font-bold rounded bg-white text-gray-700 border hover:bg-gray-200">Cuarto 3</button>
            <button onclick="switchRoom('Cuarto 4')" id="btn-room-4" class="px-2.5 py-1 text-xs font-bold rounded bg-white text-gray-700 border hover:bg-gray-200">Cuarto 4</button>
            <button onclick="switchRoom('Cuarto 5')" id="btn-room-5" class="px-2.5 py-1 text-xs font-bold rounded bg-white text-gray-700 border hover:bg-gray-200">Cuarto 5</button>
            <button onclick="switchRoom('Cuarto 6')" id="btn-room-6" class="px-2.5 py-1 text-xs font-bold rounded bg-white text-gray-700 border hover:bg-gray-200">Cuarto 6</button>
        </div>

        <div class="flex flex-wrap items-center gap-2">
            <button onclick="fillRandomCompliantData()" class="px-3 py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold rounded-lg shadow-sm transition flex items-center gap-2">
                <i class="fa-solid fa-dice text-sm"></i> Generar Datos Aleatorios Válidos (ISO)
            </button>
            <button onclick="window.print()" class="px-4 py-2 bg-red-600 hover:bg-red-700 text-white text-xs font-bold rounded-lg shadow-sm transition flex items-center gap-2">
                <i class="fa-solid fa-file-pdf text-sm"></i> Imprimir / Exportar PDF Vertical
            </button>
        </div>
    </div>

    <!-- MAIN CONTAINER FOR ROOMS 1 TO 6 -->
    <div id="roomsContainer">
        <!-- Rendered dynamically via JavaScript -->
    </div>

    <script>
        const LIMITS = {json_limits};
        let multiRoomData = {json_multi_room};

        function fillRandomCompliantData() {{
            for (let r = 1; r <= 6; r++) {{
                const roomName = `Cuarto ${{r}}`;
                const lim05 = LIMITS.c05 || 3520000;
                const lim1  = LIMITS.c1  || 832000;
                const lim5  = LIMITS.c5  || 29300;

                const base05 = lim05 * (0.15 + Math.random() * 0.25);
                const base1  = Math.min(lim1 * (0.15 + Math.random() * 0.20), base05 * 0.25);
                const base5  = Math.min(lim5 * (0.08 + Math.random() * 0.20), base1 * 0.15);

                for (let p = 0; p < 20; p++) {{
                    const ptFactor = 0.80 + Math.random() * 0.40;
                    
                    const v05_1 = Math.round(base05 * ptFactor * (0.95 + Math.random() * 0.10));
                    const v05_2 = Math.round(base05 * ptFactor * (0.95 + Math.random() * 0.10));

                    const v1_1  = Math.round(base1 * ptFactor * (0.92 + Math.random() * 0.16));
                    const v1_2  = Math.round(base1 * ptFactor * (0.92 + Math.random() * 0.16));

                    const v5_1  = Math.round(base5 * ptFactor * (0.85 + Math.random() * 0.30));
                    const v5_2  = Math.round(base5 * ptFactor * (0.85 + Math.random() * 0.30));

                    multiRoomData[roomName].c05.t1[p] = Math.min(v05_1, lim05 > 0 ? lim05 - 1 : 0);
                    multiRoomData[roomName].c05.t2[p] = Math.min(v05_2, lim05 > 0 ? lim05 - 1 : 0);

                    multiRoomData[roomName].c1.t1[p]  = Math.min(v1_1, lim1 > 0 ? lim1 - 1 : 0);
                    multiRoomData[roomName].c1.t2[p]  = Math.min(v1_2, lim1 > 0 ? lim1 - 1 : 0);

                    multiRoomData[roomName].c5.t1[p]  = Math.min(v5_1, lim5 > 0 ? lim5 - 1 : 0);
                    multiRoomData[roomName].c5.t2[p]  = Math.min(v5_2, lim5 > 0 ? lim5 - 1 : 0);
                }}
                fillRoomInputs(roomName, r);
            }}
        }}
        const roomMaps = {json_room_maps};
        let chartInstances = {{}};

        const docMeta = {{
            fecha: "{fecha}",
            auditor: "{auditor}",
            equipo: "{equipo}",
            temp: "{temp}",
            rh: "{rh}",
            ch1_name: "{ch1_name}",
            ch2_name: "{ch2_name}",
            ch3_name: "{ch3_name}",
            area_size: "{area_size}"
        }};

        const defaultPinCoords = [
            {{ x: 12, y: 52 }}, {{ x: 26, y: 22 }}, {{ x: 10, y: 18 }}, {{ x: 22, y: 12 }},
            {{ x: 38, y: 15 }}, {{ x: 88, y: 18 }}, {{ x: 78, y: 28 }}, {{ x: 52, y: 26 }},
            {{ x: 42, y: 44 }}, {{ x: 16, y: 58 }}, {{ x: 40, y: 68 }}, {{ x: 38, y: 84 }},
            {{ x: 62, y: 88 }}, {{ x: 72, y: 72 }}, {{ x: 52, y: 58 }}, {{ x: 74, y: 58 }},
            {{ x: 70, y: 44 }}, {{ x: 86, y: 44 }}, {{ x: 88, y: 74 }}, {{ x: 82, y: 86 }}
        ];

        window.onload = function() {{
            renderAllRooms();
        }};

        function renderAllRooms() {{
            const container = document.getElementById('roomsContainer');
            container.innerHTML = '';

            for (let r = 1; r <= 6; r++) {{
                const roomName = `Cuarto ${{r}}`;
                const roomHtml = createRoomSectionHtml(roomName, r);
                container.insertAdjacentHTML('beforeend', roomHtml);
            }}

            for (let r = 1; r <= 6; r++) {{
                const roomName = `Cuarto ${{r}}`;
                buildRoomTableRows(roomName, r);
                fillRoomInputs(roomName, r);
                initRoomCharts(roomName, r);
                renderRoomMapPins(roomName, r);
            }}
        }}

        function createRoomSectionHtml(roomName, roomIdx) {{
            const mapData = roomMaps[roomName] || {{}};
            const hasImage = mapData.image_b64 ? true : false;
            
            const mapVisualHtml = hasImage ? `
                <div class="relative w-full overflow-hidden border-2 border-gray-400 rounded-lg shadow-inner flex items-center justify-center bg-gray-100" style="aspect-ratio: ${{mapData.width}} / ${{mapData.height}};">
                    <img src="data:image/png;base64,${{mapData.image_b64}}" class="w-full h-full object-contain block pointer-events-none select-none" draggable="false" alt="Plano ${{roomName}}">
                    <div id="pinsLayer-${{roomIdx}}" class="absolute inset-0 w-full h-full pointer-events-auto"></div>
                </div>
            ` : `
                <div class="relative w-full aspect-[4/3] bg-gray-100 border-2 border-gray-400 rounded-lg overflow-hidden shadow-inner flex items-center justify-center">
                    <svg class="w-full h-full opacity-60" viewBox="0 0 800 600" xmlns="http://www.w3.org/2000/svg">
                        <rect width="800" height="600" fill="#f8fafc"/>
                        <defs>
                            <pattern id="grid-${{roomIdx}}" width="40" height="40" patternUnits="userSpaceOnUse">
                                <path d="M 40 0 L 0 0 0 40" fill="none" stroke="#e2e8f0" stroke-width="1"/>
                            </pattern>
                        </defs>
                        <rect width="800" height="600" fill="url(#grid-${{roomIdx}})" />
                        <rect x="40" y="40" width="720" height="520" fill="none" stroke="#334155" stroke-width="4"/>
                        <rect x="60" y="60" width="180" height="160" fill="#e0f2fe" stroke="#475569" stroke-width="2"/>
                        <text x="70" y="85" font-family="sans-serif" font-size="12" font-weight="bold" fill="#334155">${{roomName.toUpperCase()}} LINE</text>
                    </svg>
                    <div id="pinsLayer-${{roomIdx}}" class="absolute inset-0 w-full h-full pointer-events-auto"></div>
                </div>
            `;

            return `
            <div class="room-block" id="block-${{roomName.replace(' ', '-')}}">
                <!-- PAGE 1: DATA & CHARTS (PORTRAIT FIT) -->
                <div class="page-container p-3 sm:p-5 rounded-xl">
                    <div class="grid grid-cols-12 gap-3 pb-3 border-b-2 border-gray-800 items-stretch">
                        <div class="col-span-12 md:col-span-3 flex flex-col justify-center items-start">
                            <img src="https://raw.githubusercontent.com/aldoaoa/Visualizador-BCS-IDS/3a44ab1685fb192b1420168d4e246059c8261134/BCS%20LOGO.png" alt="BCS Logo" class="h-10 w-auto object-contain">
                        </div>
                        <div class="col-span-12 md:col-span-6 text-center flex flex-col justify-center">
                            <h2 class="text-lg font-black text-gray-900 tracking-tight uppercase">
                                REPORTE DE MEDICIÓN DE PARTÍCULAS - ${{roomName.toUpperCase()}}
                            </h2>
                            <p class="text-[10px] text-gray-500 font-semibold tracking-wider">SISTEMA DE CONTROL DE CALIDAD AMBIENTAL - CUARTO LIMPIO ISO 8</p>
                        </div>
                        <div class="col-span-12 md:col-span-3 text-[9px] border border-gray-400 rounded p-1 bg-gray-50 flex flex-col justify-between">
                            <div class="flex justify-between border-b border-gray-300 pb-0.5">
                                <span class="font-bold text-gray-600">Código Formato:</span>
                                <span class="font-mono text-gray-800">B_020_4_002_QRO_SP</span>
                            </div>
                            <div class="flex justify-between border-b border-gray-300 py-0.5">
                                <span class="font-bold text-gray-600">Revisión:</span>
                                <span class="font-mono text-gray-800">A</span>
                            </div>
                            <div class="flex justify-between pt-0.5">
                                <span class="font-bold text-gray-600">Página:</span>
                                <span class="font-mono text-gray-800">${{(roomIdx - 1)*2 + 1}} de 12</span>
                            </div>
                        </div>
                    </div>

                    <!-- General Parameters Grid -->
                    <div class="grid grid-cols-12 gap-2 my-2 text-[10px]">
                        <div class="col-span-12 md:col-span-6 grid grid-cols-3 gap-1 bg-gray-50 p-1.5 rounded border border-gray-200">
                            <div class="font-semibold text-gray-700">Fecha: <span class="font-normal text-gray-900">${{docMeta.fecha}}</span></div>
                            <div class="font-semibold text-gray-700">Auditor: <span class="font-normal text-gray-900">${{docMeta.auditor}}</span></div>
                            <div class="font-semibold text-gray-700">Área: <span class="font-bold text-blue-700">${{roomName}}</span></div>
                        </div>
                        <div class="col-span-12 md:col-span-6 grid grid-cols-3 gap-1 bg-gray-50 p-1.5 rounded border border-gray-200">
                            <div class="font-semibold text-gray-700">Equipo: <span class="font-normal text-gray-900">${{docMeta.equipo}}</span></div>
                            <div class="font-semibold text-gray-700">Temp: <span class="font-normal text-gray-900">${{docMeta.temp}} °C</span></div>
                            <div class="font-semibold text-gray-700">Humedad: <span class="font-normal text-gray-900">${{docMeta.rh}} %</span></div>
                        </div>
                    </div>

                    <div class="bg-gray-800 text-white font-bold text-center py-0.5 rounded-t text-[10px] uppercase">
                        Medición de Concentración de Partículas por M³ - ${{roomName}}
                    </div>

                    <div class="overflow-x-auto border border-gray-300 rounded-b mb-2">
                        <table class="w-full text-[10px] border-collapse bg-white" id="table-${{roomIdx}}">
                            <thead>
                                <tr class="bg-gray-100 text-gray-700 text-center border-b border-gray-300">
                                    <th class="p-0.5 border-r border-gray-300 w-24 text-left pl-1">Muestra por M³</th>
                                    <th class="p-0.5 border-r border-gray-300 w-8 bg-gray-200 font-bold">Toma</th>
                                    ${{Array.from({{length:20}}, (_, i) => `<th class="p-0.5 border-r border-gray-300 font-bold w-[4.3%] text-center">${{i+1}}</th>`).join('')}}
                                </tr>
                            </thead>
                            <tbody id="tbody-${{roomIdx}}"></tbody>
                        </table>
                    </div>

                    <!-- Summary Cards -->
                    <div class="mb-3 summary-card-block">
                        <div class="grid grid-cols-1 md:grid-cols-3 gap-2 text-[10px]" id="summary-${{roomIdx}}"></div>
                    </div>

                    <!-- Charts -->
                    <div class="space-y-2">
                        <div class="border border-gray-300 rounded-lg p-1.5 bg-white shadow-sm">
                            <div class="flex justify-between items-center mb-0.5 px-1">
                                <span class="font-bold text-[10px] text-gray-800">Canal: ${{docMeta.ch1_name}} (Límite Máx ISO 8: ${{LIMITS.c05.toLocaleString()}} part/m³)</span>
                                <span id="badge-05-${{roomIdx}}" class="px-1.5 py-0.5 text-[9px] font-bold rounded-full bg-green-100 text-green-800">CUMPLE ISO</span>
                            </div>
                            <div class="relative w-full h-32 chart-wrapper"><canvas id="chart05-${{roomIdx}}"></canvas></div>
                        </div>

                        <div class="border border-gray-300 rounded-lg p-1.5 bg-white shadow-sm">
                            <div class="flex justify-between items-center mb-0.5 px-1">
                                <span class="font-bold text-[10px] text-gray-800">Canal: ${{docMeta.ch2_name}} (Límite Máx ISO 8: ${{LIMITS.c1.toLocaleString()}} part/m³)</span>
                                <span id="badge-1-${{roomIdx}}" class="px-1.5 py-0.5 text-[9px] font-bold rounded-full bg-green-100 text-green-800">CUMPLE ISO</span>
                            </div>
                            <div class="relative w-full h-32 chart-wrapper"><canvas id="chart1-${{roomIdx}}"></canvas></div>
                        </div>

                        <div class="border border-gray-300 rounded-lg p-1.5 bg-white shadow-sm">
                            <div class="flex justify-between items-center mb-0.5 px-1">
                                <span class="font-bold text-[10px] text-gray-800">Canal: ${{docMeta.ch3_name}} (Límite Máx ISO 8: ${{LIMITS.c5.toLocaleString()}} part/m³)</span>
                                <span id="badge-5-${{roomIdx}}" class="px-1.5 py-0.5 text-[9px] font-bold rounded-full bg-green-100 text-green-800">CUMPLE ISO</span>
                            </div>
                            <div class="relative w-full h-32 chart-wrapper"><canvas id="chart5-${{roomIdx}}"></canvas></div>
                        </div>
                    </div>
                </div>

                <div class="page-break"></div>

                <!-- PAGE 2: MAP & LOCATION PLAN (PORTRAIT FIT) -->
                <div class="page-container p-3 sm:p-5 rounded-xl mb-6">
                    <div class="flex justify-between items-center border-b-2 border-gray-800 pb-2 mb-3">
                        <div>
                            <h2 class="text-lg font-black text-gray-900 tracking-tight uppercase">
                                PLANO DE UBICACIÓN Y DISTRIBUCIÓN - ${{roomName.toUpperCase()}}
                            </h2>
                            <p class="text-[10px] text-gray-500 font-semibold">Mapeo Físico de Puntos de Muestreo en Planta</p>
                        </div>
                        <div class="text-right text-[10px]">
                            <span class="font-bold text-gray-600">Página:</span>
                            <span class="font-mono text-gray-800">${{roomIdx*2}} de 12</span>
                        </div>
                    </div>

                    <div class="grid grid-cols-12 gap-4 items-start">
                        <div class="col-span-12 bg-gray-50 p-3 rounded-xl border border-gray-200">
                            <div class="grid grid-cols-3 gap-3 mb-2">
                                <div>
                                    <label class="block text-[9px] font-bold text-gray-500 uppercase">Área Registrada</label>
                                    <div class="text-sm font-black text-gray-800">${{roomName}}</div>
                                </div>
                                <div>
                                    <label class="block text-[9px] font-bold text-gray-500 uppercase">Superficie Total</label>
                                    <div class="text-sm font-bold text-gray-700">${{docMeta.area_size}}</div>
                                </div>
                                <div>
                                    <label class="block text-[9px] font-bold text-gray-500 uppercase">Simbología y Estado</label>
                                    <div class="flex items-center gap-3 text-[10px] font-semibold">
                                        <span id="passCountText-${{roomIdx}}" class="text-sky-700">Dentro: 20</span>
                                        <span id="failCountText-${{roomIdx}}" class="text-red-700">Fuera: 0</span>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <div class="col-span-12">
                            ${{mapVisualHtml}}
                        </div>
                    </div>
                </div>

                <div class="page-break"></div>
            </div>
            `;
        }}

        function buildRoomTableRows(roomName, roomIdx) {{
            const tbody = document.getElementById(`tbody-${{roomIdx}}`);
            if (!tbody) return;
            tbody.innerHTML = '';

            const channels = [
                {{ key: 'c05', label: docMeta.ch1_name + ' (Max ' + LIMITS.c05.toLocaleString() + ')', limit: LIMITS.c05 }},
                {{ key: 'c1',  label: docMeta.ch2_name + ' (Max ' + LIMITS.c1.toLocaleString() + ')',  limit: LIMITS.c1 }},
                {{ key: 'c5',  label: docMeta.ch3_name + ' (Max ' + LIMITS.c5.toLocaleString() + ')',   limit: LIMITS.c5 }}
            ];

            channels.forEach(ch => {{
                for (let t = 1; t <= 2; t++) {{
                    const tr = document.createElement('tr');
                    tr.className = "border-b border-gray-200 hover:bg-gray-50";

                    if (t === 1) {{
                        const tdLabel = document.createElement('td');
                        tdLabel.rowSpan = 2;
                        tdLabel.className = "p-0.5 border-r border-gray-300 font-bold bg-gray-50 text-gray-800 text-[9px]";
                        tdLabel.innerText = ch.label;
                        tr.appendChild(tdLabel);
                    }}

                    const tdTake = document.createElement('td');
                    tdTake.className = "p-0.5 border-r border-gray-300 font-bold text-center bg-gray-100 text-gray-700 text-[9px]";
                    tdTake.innerText = t;
                    tr.appendChild(tdTake);

                    for (let p = 0; p < 20; p++) {{
                        const tdInput = document.createElement('td');
                        tdInput.className = "p-0.5 border-r border-gray-200 text-center";
                        
                        const input = document.createElement('input');
                        input.type = "text";
                        input.className = "cell-input";
                        input.dataset.room = roomName;
                        input.dataset.channel = ch.key;
                        input.dataset.take = `t${{t}}`;
                        input.dataset.point = p;
                        input.dataset.limit = ch.limit;
                        input.dataset.roomidx = roomIdx;

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

        function fillRoomInputs(roomName, roomIdx) {{
            const roomData = multiRoomData[roomName];
            if (!roomData) return;

            const inputs = document.querySelectorAll(`#tbody-${{roomIdx}} .cell-input`);
            inputs.forEach(input => {{
                const chKey = input.dataset.channel;
                const takeKey = input.dataset.take;
                const pIdx = parseInt(input.dataset.point, 10);
                const limit = parseInt(input.dataset.limit, 10);

                const val = roomData[chKey][takeKey][pIdx];
                if (val !== undefined && val !== null && val >= 0) {{
                    input.value = val.toLocaleString('en-US');
                    if (val > limit) {{
                        input.classList.add('out-of-spec');
                        input.classList.remove('in-spec');
                    }} else {{
                        input.classList.remove('out-of-spec');
                        input.classList.add('in-spec');
                    }}
                }} else {{
                    input.value = '';
                    input.classList.remove('out-of-spec', 'in-spec');
                }}
            }});

            recalculateRoom(roomName, roomIdx);
        }}

        function formatInputAndCalculate(inputEl) {{
            let valStr = inputEl.value.replace(/,/g, '').trim();
            let num = parseInt(valStr, 10);

            const roomName = inputEl.dataset.room;
            const roomIdx = inputEl.dataset.roomidx;
            const chKey = inputEl.dataset.channel;
            const takeKey = inputEl.dataset.take;
            const pIdx = parseInt(inputEl.dataset.point, 10);
            const limit = parseInt(inputEl.dataset.limit, 10);

            if (!isNaN(num) && num >= 0) {{
                multiRoomData[roomName][chKey][takeKey][pIdx] = num;
                inputEl.value = num.toLocaleString('en-US');

                if (num > limit) {{
                    inputEl.classList.add('out-of-spec');
                    inputEl.classList.remove('in-spec');
                }} else {{
                    inputEl.classList.remove('out-of-spec');
                    inputEl.classList.add('in-spec');
                }}
            }} else {{
                multiRoomData[roomName][chKey][takeKey][pIdx] = -1;
                inputEl.value = '';
                inputEl.classList.remove('out-of-spec', 'in-spec');
            }}

            recalculateRoom(roomName, roomIdx);
        }}

        function recalculateRoom(roomName, roomIdx) {{
            updateRoomSummaryCards(roomName, roomIdx);
            updateRoomCharts(roomName, roomIdx);
            updateRoomMapPins(roomName, roomIdx);
        }}

        function getRoomChannelAvg(roomName, chKey) {{
            const rawT1 = multiRoomData[roomName][chKey].t1.filter(v => v >= 0);
            const rawT2 = multiRoomData[roomName][chKey].t2.filter(v => v >= 0);

            const sumT1 = rawT1.reduce((a, b) => a + b, 0);
            const sumT2 = rawT2.reduce((a, b) => a + b, 0);

            const countT1 = rawT1.length || 1;
            const countT2 = rawT2.length || 1;

            const avgT1 = Math.round(sumT1 / countT1);
            const avgT2 = Math.round(sumT2 / countT2);
            const avgGlobal = Math.round((avgT1 + avgT2) / 2);

            return {{ avgT1, avgT2, avgGlobal }};
        }}

        function updateRoomSummaryCards(roomName, roomIdx) {{
            const container = document.getElementById(`summary-${{roomIdx}}`);
            if (!container) return;
            container.innerHTML = '';

            const channels = [
                {{ key: 'c05', name: docMeta.ch1_name, limitName: 'Max ' + LIMITS.c05.toLocaleString(), limit: LIMITS.c05 }},
                {{ key: 'c1',  name: docMeta.ch2_name, limitName: 'Max ' + LIMITS.c1.toLocaleString(),  limit: LIMITS.c1 }},
                {{ key: 'c5',  name: docMeta.ch3_name, limitName: 'Max ' + LIMITS.c5.toLocaleString(),   limit: LIMITS.c5 }}
            ];

            channels.forEach(ch => {{
                const {{ avgT1, avgT2, avgGlobal }} = getRoomChannelAvg(roomName, ch.key);
                const isExceeded = avgGlobal > ch.limit || multiRoomData[roomName][ch.key].t1.some(v => v > ch.limit) || multiRoomData[roomName][ch.key].t2.some(v => v > ch.limit);

                const badgeEl = document.getElementById(`badge-${{ch.key === 'c05' ? '05' : ch.key === 'c1' ? '1' : '5'}}-${{roomIdx}}`);
                if (badgeEl) {{
                    if (isExceeded) {{
                        badgeEl.innerText = "EXCEDE LÍMITE ISO 8";
                        badgeEl.className = "px-1.5 py-0.5 text-[9px] font-bold rounded-full bg-red-100 text-red-800";
                    }} else {{
                        badgeEl.innerText = "CUMPLE ISO 8";
                        badgeEl.className = "px-1.5 py-0.5 text-[9px] font-bold rounded-full bg-green-100 text-green-800";
                    }}
                }}

                const cardHtml = `
                    <div class="border ${{isExceeded ? 'border-red-300 bg-red-50' : 'border-gray-200 bg-gray-50'}} rounded p-1.5 flex items-center justify-between">
                        <div class="font-bold text-gray-800 border-r border-gray-300 pr-1.5">
                            <span class="block text-[10px] font-extrabold ${{isExceeded ? 'text-red-700' : 'text-gray-900'}}">${{ch.name}}</span>
                            <span class="text-[8px] text-gray-500 font-normal">(${{ch.limitName}})</span>
                        </div>
                        <div class="grid grid-cols-2 gap-x-1.5 text-center text-[8px]">
                            <div>
                                <span class="block text-gray-500 font-semibold">Toma 1</span>
                                <span class="font-mono font-bold text-gray-800">${{avgT1.toLocaleString()}}</span>
                            </div>
                            <div>
                                <span class="block text-gray-500 font-semibold">Toma 2</span>
                                <span class="font-mono font-bold text-gray-800">${{avgT2.toLocaleString()}}</span>
                            </div>
                        </div>
                        <div class="border-l border-gray-300 pl-1.5 text-right">
                            <span class="block text-[8px] text-gray-500 font-bold uppercase">Prom. General</span>
                            <span class="font-mono font-extrabold text-[10px] ${{isExceeded ? 'text-red-600' : 'text-blue-700'}}">${{avgGlobal.toLocaleString()}}</span>
                        </div>
                    </div>
                `;
                container.insertAdjacentHTML('beforeend', cardHtml);
            }});
        }}

        function initRoomCharts(roomName, roomIdx) {{
            const labels = Array.from({{length: 20}}, (_, i) => `${{i + 1}}`);

            const createConfig = (chKey, limit) => {{
                return {{
                    type: 'line',
                    data: {{
                        labels: labels,
                        datasets: [
                            {{
                                label: 'Toma 1',
                                data: multiRoomData[roomName][chKey].t1.map(v => v >= 0 ? v : null),
                                borderColor: '#0284c7',
                                backgroundColor: 'rgba(2, 132, 199, 0.1)',
                                borderWidth: 1.5,
                                pointRadius: 2,
                                tension: 0.2
                            }},
                            {{
                                label: 'Toma 2',
                                data: multiRoomData[roomName][chKey].t2.map(v => v >= 0 ? v : null),
                                borderColor: '#0d9488',
                                backgroundColor: 'rgba(13, 148, 136, 0.1)',
                                borderWidth: 1.5,
                                pointRadius: 2,
                                tension: 0.2
                            }},
                            {{
                                label: `Límite ISO 8 (${{limit.toLocaleString()}})`,
                                data: Array(20).fill(limit),
                                borderColor: '#ef4444',
                                borderWidth: 1.2,
                                borderDash: [3, 3],
                                pointRadius: 0,
                                fill: false
                            }}
                        ]
                    }},
                    options: {{
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {{
                            legend: {{ display: true, position: 'top', labels: {{ boxWidth: 8, fontSize: 8, padding: 4 }} }}
                        }},
                        scales: {{
                            x: {{ ticks: {{ font: {{ size: 7 }} }} }},
                            y: {{ ticks: {{ font: {{ size: 7 }}, callback: v => v.toLocaleString() }} }}
                        }}
                    }}
                }};
            }};

            const canvas05 = document.getElementById(`chart05-${{roomIdx}}`);
            const canvas1 = document.getElementById(`chart1-${{roomIdx}}`);
            const canvas5 = document.getElementById(`chart5-${{roomIdx}}`);

            if (canvas05) chartInstances[`c05-${{roomIdx}}`] = new Chart(canvas05.getContext('2d'), createConfig('c05', LIMITS.c05));
            if (canvas1)  chartInstances[`c1-${{roomIdx}}`]  = new Chart(canvas1.getContext('2d'),  createConfig('c1', LIMITS.c1));
            if (canvas5)  chartInstances[`c5-${{roomIdx}}`]  = new Chart(canvas5.getContext('2d'),  createConfig('c5', LIMITS.c5));
        }}

        function updateRoomCharts(roomName, roomIdx) {{
            if (!chartInstances[`c05-${{roomIdx}}`]) return;
            chartInstances[`c05-${{roomIdx}}`].data.datasets[0].data = multiRoomData[roomName].c05.t1.map(v => v >= 0 ? v : null);
            chartInstances[`c05-${{roomIdx}}`].data.datasets[1].data = multiRoomData[roomName].c05.t2.map(v => v >= 0 ? v : null);
            chartInstances[`c05-${{roomIdx}}`].update();

            chartInstances[`c1-${{roomIdx}}`].data.datasets[0].data = multiRoomData[roomName].c1.t1.map(v => v >= 0 ? v : null);
            chartInstances[`c1-${{roomIdx}}`].data.datasets[1].data = multiRoomData[roomName].c1.t2.map(v => v >= 0 ? v : null);
            chartInstances[`c1-${{roomIdx}}`].update();

            chartInstances[`c5-${{roomIdx}}`].data.datasets[0].data = multiRoomData[roomName].c5.t1.map(v => v >= 0 ? v : null);
            chartInstances[`c5-${{roomIdx}}`].data.datasets[1].data = multiRoomData[roomName].c5.t2.map(v => v >= 0 ? v : null);
            chartInstances[`c5-${{roomIdx}}`].update();
        }}

        function renderRoomMapPins(roomName, roomIdx) {{
            const layer = document.getElementById(`pinsLayer-${{roomIdx}}`);
            if (!layer) return;
            layer.innerHTML = '';

            const mapData = roomMaps[roomName];
            const pinsInfo = (mapData && mapData.pins && mapData.pins.length > 0) 
                ? mapData.pins 
                : defaultPinCoords.map((coord, i) => ({{ point: i + 1, x_pct: coord.x, y_pct: coord.y }}));

            pinsInfo.forEach((pinData) => {{
                const pNum = pinData.point;
                const pin = document.createElement('div');
                pin.className = 'map-pin pass';
                pin.id = `pin-${{roomIdx}}-${{pNum}}`;
                pin.innerText = pNum;
                pin.style.left = `${{pinData.x_pct}}%`;
                pin.style.top = `${{pinData.y_pct}}%`;
                
                makeDraggable(pin);
                layer.appendChild(pin);
            }});

            updateRoomMapPins(roomName, roomIdx);
        }}

        function updateRoomMapPins(roomName, roomIdx) {{
            let failCount = 0;
            let passCount = 0;

            const mapData = roomMaps[roomName];
            const pinsInfo = (mapData && mapData.pins && mapData.pins.length > 0) 
                ? mapData.pins 
                : defaultPinCoords.map((coord, i) => ({{ point: i + 1, x_pct: coord.x, y_pct: coord.y }}));

            pinsInfo.forEach((pinData) => {{
                const p = pinData.point - 1;
                const pin = document.getElementById(`pin-${{roomIdx}}-${{pinData.point}}`);
                if (!pin) return;

                const c05Exceed = multiRoomData[roomName].c05.t1[p] > LIMITS.c05 || multiRoomData[roomName].c05.t2[p] > LIMITS.c05;
                const c1Exceed  = multiRoomData[roomName].c1.t1[p]  > LIMITS.c1  || multiRoomData[roomName].c1.t2[p]  > LIMITS.c1;
                const c5Exceed  = multiRoomData[roomName].c5.t1[p]  > LIMITS.c5  || multiRoomData[roomName].c5.t2[p]  > LIMITS.c5;

                if (c05Exceed || c1Exceed || c5Exceed) {{
                    pin.className = 'map-pin fail';
                    failCount++;
                }} else {{
                    pin.className = 'map-pin pass';
                    passCount++;
                }}
            }});

            const passEl = document.getElementById(`passCountText-${{roomIdx}}`);
            const failEl = document.getElementById(`failCountText-${{roomIdx}}`);
            if (passEl) passEl.innerText = `Dentro: ${{passCount}}`;
            if (failEl) failEl.innerText = `Fuera: ${{failCount}}`;
        }}

        function makeDraggable(element) {{
            let isDragging = false;

            element.style.cursor = 'grab';
            element.style.touchAction = 'none';

            element.addEventListener('mousedown', startDrag);
            element.addEventListener('touchstart', startDrag, {{ passive: false }});

            function startDrag(e) {{
                isDragging = true;
                element.style.cursor = 'grabbing';
                element.style.zIndex = '100';
                e.preventDefault();
                e.stopPropagation();

                window.addEventListener('mousemove', onMove, {{ capture: true }});
                window.addEventListener('touchmove', onMove, {{ passive: false, capture: true }});
                window.addEventListener('mouseup', stopDrag, {{ capture: true }});
                window.addEventListener('touchend', stopDrag, {{ capture: true }});
            }}

            function onMove(e) {{
                if (!isDragging) return;
                e.preventDefault();
                e.stopPropagation();

                const container = element.parentElement;
                if (!container) return;

                const rect = container.getBoundingClientRect();
                const clientX = (e.touches && e.touches.length > 0) ? e.touches[0].clientX : e.clientX;
                const clientY = (e.touches && e.touches.length > 0) ? e.touches[0].clientY : e.clientY;

                if (clientX === undefined || clientY === undefined) return;

                let x = ((clientX - rect.left) / rect.width) * 100;
                let y = ((clientY - rect.top) / rect.height) * 100;

                x = Math.max(1, Math.min(99, x));
                y = Math.max(1, Math.min(99, y));

                element.style.left = `${{x.toFixed(2)}}%`;
                element.style.top = `${{y.toFixed(2)}}%`;
            }}

            function stopDrag(e) {{
                if (!isDragging) return;
                isDragging = false;
                element.style.cursor = 'grab';
                element.style.zIndex = '30';

                window.removeEventListener('mousemove', onMove, {{ capture: true }});
                window.removeEventListener('touchmove', onMove, {{ capture: true }});
                window.removeEventListener('mouseup', stopDrag, {{ capture: true }});
                window.removeEventListener('touchend', stopDrag, {{ capture: true }});
            }}
        }}

        function switchRoom(target) {{
            const blocks = document.querySelectorAll('.room-block');
            blocks.forEach(b => {{
                if (target === 'all') {{
                    b.style.display = 'block';
                }} else {{
                    const roomIdx = target.replace('Cuarto ', '');
                    if (b.id === `block-${{target.replace(' ', '-')}}`) {{
                        b.style.display = 'block';
                    }} else {{
                        b.style.display = 'none';
                    }}
                }}
            }});

            for (let r = 1; r <= 6; r++) {{
                const btn = document.getElementById(`btn-room-${{r}}`);
                if (btn) {{
                    btn.className = (target === `Cuarto ${{r}}`) ? "px-2.5 py-1 text-xs font-bold rounded bg-red-600 text-white shadow-sm" : "px-2.5 py-1 text-xs font-bold rounded bg-white text-gray-700 border hover:bg-gray-200";
                }}
            }}
            const btnAll = document.getElementById('btn-room-all');
            if (btnAll) {{
                btnAll.className = (target === 'all') ? "px-2.5 py-1 text-xs font-bold rounded bg-red-600 text-white shadow-sm" : "px-2.5 py-1 text-xs font-bold rounded bg-white text-gray-700 border hover:bg-gray-200";
            }}
        }}
    </script>
</body>
</html>"""
    return html_template


def generate_single_room_html_report(metadata, room_name, room_data, num_points=20, limits=None, room_map=None):
    """
    Generates standalone HTML report string for a SINGLE specified room/area with a custom number of points (1 to 20).
    """
    if limits is None:
        limits = DEFAULT_LIMITS
        
    if room_map is None:
        all_maps = load_room_maps_and_coordinates()
        room_map = all_maps.get(room_name, {})

    json_room_data = json.dumps(room_data)
    json_limits = json.dumps(limits)
    json_room_map = json.dumps(room_map)

    fecha = str(metadata.get("fecha", "2025-07-21"))
    auditor = str(metadata.get("auditor", "Armando Reyes"))
    equipo = str(metadata.get("equipo", "BCS-QRO-LAB-ANA001, Particles Plus 8503."))
    temp = str(metadata.get("temp", "21.15"))
    rh = str(metadata.get("rh", "48.32"))
    ch1_name = str(metadata.get("ch1_name", "0.5 µm"))
    ch2_name = str(metadata.get("ch2_name", "1.0 µm"))
    ch3_name = str(metadata.get("ch3_name", "5.0 µm"))
    area_size = str(metadata.get("area_size", "1662.81 m²"))

    room_name_clean = room_name.upper()

    html_template = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Reporte Individual de Medición - {room_name} - BCS</title>
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
            padding: 1px 2px;
            font-size: 0.68rem;
            text-align: right;
            border: 1px solid #d1d5db;
            border-radius: 2px;
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
            max-width: 1200px;
            margin: 0 auto 1.5rem auto;
            background: #ffffff;
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.1);
        }}

        @media print {{
            body {{
                background: #ffffff !important;
                padding: 0 !important;
                margin: 0 !important;
            }}
            .no-print {{
                display: none !important;
            }}
            .page-break {{
                page-break-before: always !important;
                break-before: page !important;
            }}
            .page-container {{
                box-shadow: none !important;
                max-width: 100% !important;
                width: 100% !important;
                padding: 0 !important;
                margin: 0 0 10px 0 !important;
                page-break-inside: avoid !important;
                break-inside: avoid !important;
            }}
            .chart-wrapper {{
                height: 140px !important;
            }}
            tr, table, tbody, td, th, .chart-wrapper, .map-pin, img, .summary-card-block {{
                page-break-inside: avoid !important;
                break-inside: avoid !important;
            }}
            @page {{
                size: letter portrait;
                margin: 6mm 5mm;
            }}
        }}

        .map-pin {{
            position: absolute;
            width: 24px;
            height: 24px;
            border-radius: 50%;
            color: white;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 0.7rem;
            font-weight: 700;
            cursor: move;
            user-select: none;
            box-shadow: 0 2px 5px rgba(0,0,0,0.3);
            transform: translate(-50%, -50%);
            transition: background-color 0.3s ease, transform 0.1s ease;
        }}
        .map-pin:hover {{
            transform: translate(-50%, -50%) scale(1.25);
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
<body class="p-2 sm:p-4">

    <!-- Action Bar -->
    <div class="no-print max-w-[1200px] mx-auto mb-4 bg-white p-4 rounded-xl shadow-md border border-gray-200 flex flex-wrap items-center justify-between gap-3">
        <div class="flex items-center space-x-3">
            <div class="p-2 bg-red-50 rounded-lg border border-red-100">
                <i class="fa-solid fa-map-location-dot text-red-600 text-xl"></i>
            </div>
            <div>
                <h1 class="font-bold text-gray-800 text-lg leading-tight">Reporte Individual: {room_name}</h1>
                <p class="text-xs text-gray-500">Monitoreo Ambiental Área Específica - Norma ISO 14644-1 ({num_points} Puntos)</p>
            </div>
        </div>

        <div class="flex flex-wrap items-center gap-2">
            <button onclick="fillSingleRandomCompliantData()" class="px-3 py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold rounded-lg shadow-sm transition flex items-center gap-2">
                <i class="fa-solid fa-dice text-sm"></i> Generar Datos Aleatorios Válidos (ISO)
            </button>
            <button onclick="window.print()" class="px-4 py-2 bg-red-600 hover:bg-red-700 text-white text-xs font-bold rounded-lg shadow-sm transition flex items-center gap-2">
                <i class="fa-solid fa-file-pdf text-sm"></i> Imprimir Reporte de {room_name} (PDF Vertical)
            </button>
        </div>
    </div>

    <!-- PAGE 1: DATA & CHARTS -->
    <div class="page-container p-3 sm:p-5 rounded-xl">
        <div class="grid grid-cols-12 gap-3 pb-3 border-b-2 border-gray-800 items-stretch">
            <div class="col-span-12 md:col-span-3 flex flex-col justify-center items-start">
                <img src="https://raw.githubusercontent.com/aldoaoa/Visualizador-BCS-IDS/3a44ab1685fb192b1420168d4e246059c8261134/BCS%20LOGO.png" alt="BCS Logo" class="h-10 w-auto object-contain">
            </div>
            <div class="col-span-12 md:col-span-6 text-center flex flex-col justify-center">
                <h2 class="text-lg font-black text-gray-900 tracking-tight uppercase">
                    REPORTE DE MEDICIÓN DE PARTÍCULAS - {room_name_clean}
                </h2>
                <p class="text-[10px] text-gray-500 font-semibold tracking-wider">SISTEMA DE CONTROL DE CALIDAD AMBIENTAL - CUARTO LIMPIO ISO 8</p>
            </div>
            <div class="col-span-12 md:col-span-3 text-[9px] border border-gray-400 rounded p-1 bg-gray-50 flex flex-col justify-between">
                <div class="flex justify-between border-b border-gray-300 pb-0.5">
                    <span class="font-bold text-gray-600">Código Formato:</span>
                    <span class="font-mono text-gray-800">B_020_4_002_QRO_SP</span>
                </div>
                <div class="flex justify-between border-b border-gray-300 py-0.5">
                    <span class="font-bold text-gray-600">Revisión:</span>
                    <span class="font-mono text-gray-800">A</span>
                </div>
                <div class="flex justify-between pt-0.5">
                    <span class="font-bold text-gray-600">Página:</span>
                    <span class="font-mono text-gray-800">1 de 2</span>
                </div>
            </div>
        </div>

        <!-- General Parameters Grid -->
        <div class="grid grid-cols-12 gap-2 my-2 text-[10px]">
            <div class="col-span-12 md:col-span-6 grid grid-cols-3 gap-1 bg-gray-50 p-1.5 rounded border border-gray-200">
                <div class="font-semibold text-gray-700">Fecha: <span class="font-normal text-gray-900">{fecha}</span></div>
                <div class="font-semibold text-gray-700">Auditor: <span class="font-normal text-gray-900">{auditor}</span></div>
                <div class="font-semibold text-gray-700">Área: <span class="font-bold text-blue-700">{room_name}</span></div>
            </div>
            <div class="col-span-12 md:col-span-6 grid grid-cols-3 gap-1 bg-gray-50 p-1.5 rounded border border-gray-200">
                <div class="font-semibold text-gray-700">Equipo: <span class="font-normal text-gray-900">{equipo}</span></div>
                <div class="font-semibold text-gray-700">Temp: <span class="font-normal text-gray-900">{temp} °C</span></div>
                <div class="font-semibold text-gray-700">Humedad: <span class="font-normal text-gray-900">{rh} %</span></div>
            </div>
        </div>

        <div class="bg-gray-800 text-white font-bold text-center py-0.5 rounded-t text-[10px] uppercase">
            Medición de Concentración de Partículas por M³ - {room_name} ({num_points} Puntos)
        </div>

        <div class="overflow-x-auto border border-gray-300 rounded-b mb-2">
            <table class="w-full text-[10px] border-collapse bg-white" id="singleTable">
                <thead>
                    <tr class="bg-gray-100 text-gray-700 text-center border-b border-gray-300">
                        <th class="p-0.5 border-r border-gray-300 w-24 text-left pl-1">Muestra por M³</th>
                        <th class="p-0.5 border-r border-gray-300 w-8 bg-gray-200 font-bold">Toma</th>
                        {"".join([f'<th class="p-0.5 border-r border-gray-300 font-bold text-center">{i+1}</th>' for i in range(num_points)])}
                    </tr>
                </thead>
                <tbody id="singleTbody"></tbody>
            </table>
        </div>

        <!-- Summary Cards -->
        <div class="mb-3 summary-card-block">
            <div class="grid grid-cols-1 md:grid-cols-3 gap-2 text-[10px]" id="singleSummary"></div>
        </div>

        <!-- Charts -->
        <div class="space-y-2">
            <div class="border border-gray-300 rounded-lg p-1.5 bg-white shadow-sm">
                <div class="flex justify-between items-center mb-0.5 px-1">
                    <span class="font-bold text-[10px] text-gray-800">Canal: {ch1_name} (Límite Máx ISO 8: {limits.get('c05', DEFAULT_LIMITS['c05']):,} part/m³)</span>
                    <span id="singleBadge05" class="px-1.5 py-0.5 text-[9px] font-bold rounded-full bg-green-100 text-green-800">CUMPLE ISO</span>
                </div>
                <div class="relative w-full h-32 chart-wrapper"><canvas id="singleChart05"></canvas></div>
            </div>

            <div class="border border-gray-300 rounded-lg p-1.5 bg-white shadow-sm">
                <div class="flex justify-between items-center mb-0.5 px-1">
                    <span class="font-bold text-[10px] text-gray-800">Canal: {ch2_name} (Límite Máx ISO 8: {limits.get('c1', DEFAULT_LIMITS['c1']):,} part/m³)</span>
                    <span id="singleBadge1" class="px-1.5 py-0.5 text-[9px] font-bold rounded-full bg-green-100 text-green-800">CUMPLE ISO</span>
                </div>
                <div class="relative w-full h-32 chart-wrapper"><canvas id="singleChart1"></canvas></div>
            </div>

            <div class="border border-gray-300 rounded-lg p-1.5 bg-white shadow-sm">
                <div class="flex justify-between items-center mb-0.5 px-1">
                    <span class="font-bold text-[10px] text-gray-800">Canal: {ch3_name} (Límite Máx ISO 8: {limits.get('c5', DEFAULT_LIMITS['c5']):,} part/m³)</span>
                    <span id="singleBadge5" class="px-1.5 py-0.5 text-[9px] font-bold rounded-full bg-green-100 text-green-800">CUMPLE ISO</span>
                </div>
                <div class="relative w-full h-32 chart-wrapper"><canvas id="singleChart5"></canvas></div>
            </div>
        </div>
    </div>

    <div class="page-break"></div>

    <!-- PAGE 2: MAP & LOCATION PLAN -->
    <div class="page-container p-3 sm:p-5 rounded-xl mb-6">
        <div class="flex justify-between items-center border-b-2 border-gray-800 pb-2 mb-3">
            <div>
                <h2 class="text-lg font-black text-gray-900 tracking-tight uppercase">
                    PLANO DE UBICACIÓN Y DISTRIBUCIÓN - {room_name_clean}
                </h2>
                <p class="text-[10px] text-gray-500 font-semibold">Mapeo Físico de Puntos de Muestreo en Planta ({num_points} Puntos)</p>
            </div>
            <div class="text-right text-[10px]">
                <span class="font-bold text-gray-600">Página:</span>
                <span class="font-mono text-gray-800">2 de 2</span>
            </div>
        </div>

        <div class="grid grid-cols-12 gap-4 items-start">
            <div class="col-span-12 bg-gray-50 p-3 rounded-xl border border-gray-200">
                <div class="grid grid-cols-3 gap-3 mb-2">
                    <div>
                        <label class="block text-[9px] font-bold text-gray-500 uppercase">Área Registrada</label>
                        <div class="text-sm font-black text-gray-800">{room_name}</div>
                    </div>
                    <div>
                        <label class="block text-[9px] font-bold text-gray-500 uppercase">Superficie Total</label>
                        <div class="text-sm font-bold text-gray-700">{area_size}</div>
                    </div>
                    <div>
                        <label class="block text-[9px] font-bold text-gray-500 uppercase">Simbología y Estado</label>
                        <div class="flex items-center gap-3 text-[10px] font-semibold">
                            <span id="singlePassCountText" class="text-sky-700">Dentro: {num_points}</span>
                            <span id="singleFailCountText" class="text-red-700">Fuera: 0</span>
                        </div>
                    </div>
                </div>
            </div>

            <div class="col-span-12">
                <div id="singleMapContainer"></div>
            </div>
        </div>
    </div>

    <script>
        const LIMITS = {json_limits};
        let roomData = {json_room_data};
        const roomMap = {json_room_map};
        const numPoints = {num_points};
        let chartInstances = {{}};

        function fillSingleRandomCompliantData() {{
            const lim05 = LIMITS.c05 || 3520000;
            const lim1  = LIMITS.c1  || 832000;
            const lim5  = LIMITS.c5  || 29300;

            const base05 = lim05 * (0.15 + Math.random() * 0.25);
            const base1  = Math.min(lim1 * (0.15 + Math.random() * 0.20), base05 * 0.25);
            const base5  = Math.min(lim5 * (0.08 + Math.random() * 0.20), base1 * 0.15);

            for (let p = 0; p < numPoints; p++) {{
                const ptFactor = 0.80 + Math.random() * 0.40;
                
                const v05_1 = Math.round(base05 * ptFactor * (0.95 + Math.random() * 0.10));
                const v05_2 = Math.round(base05 * ptFactor * (0.95 + Math.random() * 0.10));

                const v1_1  = Math.round(base1 * ptFactor * (0.92 + Math.random() * 0.16));
                const v1_2  = Math.round(base1 * ptFactor * (0.92 + Math.random() * 0.16));

                const v5_1  = Math.round(base5 * ptFactor * (0.85 + Math.random() * 0.30));
                const v5_2  = Math.round(base5 * ptFactor * (0.85 + Math.random() * 0.30));

                roomData.c05.t1[p] = Math.min(v05_1, lim05 > 0 ? lim05 - 1 : 0);
                roomData.c05.t2[p] = Math.min(v05_2, lim05 > 0 ? lim05 - 1 : 0);

                roomData.c1.t1[p]  = Math.min(v1_1, lim1 > 0 ? lim1 - 1 : 0);
                roomData.c1.t2[p]  = Math.min(v1_2, lim1 > 0 ? lim1 - 1 : 0);

                roomData.c5.t1[p]  = Math.min(v5_1, lim5 > 0 ? lim5 - 1 : 0);
                roomData.c5.t2[p]  = Math.min(v5_2, lim5 > 0 ? lim5 - 1 : 0);
            }}
            fillSingleInputs();
        }}

        const docMeta = {{
            fecha: "{fecha}",
            auditor: "{auditor}",
            equipo: "{equipo}",
            temp: "{temp}",
            rh: "{rh}",
            ch1_name: "{ch1_name}",
            ch2_name: "{ch2_name}",
            ch3_name: "{ch3_name}",
            area_size: "{area_size}"
        }};

        window.onload = function() {{
            renderSingleMapVisual();
            buildSingleTableRows();
            fillSingleInputs();
            initSingleCharts();
            renderSingleMapPins();
        }};

        function renderSingleMapVisual() {{
            const container = document.getElementById('singleMapContainer');
            const hasImage = roomMap && roomMap.image_b64 ? true : false;

            if (hasImage) {{
                container.innerHTML = `
                    <div class="relative w-full overflow-hidden border-2 border-gray-400 rounded-lg shadow-inner flex items-center justify-center bg-gray-100" style="aspect-ratio: ${{roomMap.width}} / ${{roomMap.height}};">
                        <img src="data:image/png;base64,${{roomMap.image_b64}}" class="w-full h-full object-contain block pointer-events-none select-none" draggable="false" alt="Plano {room_name}">
                        <div id="singlePinsLayer" class="absolute inset-0 w-full h-full pointer-events-auto"></div>
                    </div>
                `;
            }} else {{
                container.innerHTML = `
                    <div class="relative w-full aspect-[4/3] bg-gray-100 border-2 border-gray-400 rounded-lg overflow-hidden shadow-inner flex items-center justify-center">
                        <svg class="w-full h-full opacity-60" viewBox="0 0 800 600" xmlns="http://www.w3.org/2000/svg">
                            <rect width="800" height="600" fill="#f8fafc"/>
                            <rect x="40" y="40" width="720" height="520" fill="none" stroke="#334155" stroke-width="4"/>
                            <text x="70" y="85" font-family="sans-serif" font-size="14" font-weight="bold" fill="#334155">{room_name_clean}</text>
                        </svg>
                        <div id="singlePinsLayer" class="absolute inset-0 w-full h-full pointer-events-auto"></div>
                    </div>
                `;
            }}
        }}

        function buildSingleTableRows() {{
            const tbody = document.getElementById('singleTbody');
            if (!tbody) return;
            tbody.innerHTML = '';

            const channels = [
                {{ key: 'c05', label: docMeta.ch1_name + ' (Max ' + LIMITS.c05.toLocaleString() + ')', limit: LIMITS.c05 }},
                {{ key: 'c1',  label: docMeta.ch2_name + ' (Max ' + LIMITS.c1.toLocaleString() + ')',  limit: LIMITS.c1 }},
                {{ key: 'c5',  label: docMeta.ch3_name + ' (Max ' + LIMITS.c5.toLocaleString() + ')',   limit: LIMITS.c5 }}
            ];

            channels.forEach(ch => {{
                for (let t = 1; t <= 2; t++) {{
                    const tr = document.createElement('tr');
                    tr.className = "border-b border-gray-200 hover:bg-gray-50";

                    if (t === 1) {{
                        const tdLabel = document.createElement('td');
                        tdLabel.rowSpan = 2;
                        tdLabel.className = "p-0.5 border-r border-gray-300 font-bold bg-gray-50 text-gray-800 text-[9px]";
                        tdLabel.innerText = ch.label;
                        tr.appendChild(tdLabel);
                    }}

                    const tdTake = document.createElement('td');
                    tdTake.className = "p-0.5 border-r border-gray-300 font-bold text-center bg-gray-100 text-gray-700 text-[9px]";
                    tdTake.innerText = t;
                    tr.appendChild(tdTake);

                    for (let p = 0; p < numPoints; p++) {{
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
                            formatSingleInputAndCalculate(this);
                        }};

                        tdInput.appendChild(input);
                        tr.appendChild(tdInput);
                    }}

                    tbody.appendChild(tr);
                }}
            }});
        }}

        function fillSingleInputs() {{
            const inputs = document.querySelectorAll('#singleTbody .cell-input');
            inputs.forEach(input => {{
                const chKey = input.dataset.channel;
                const takeKey = input.dataset.take;
                const pIdx = parseInt(input.dataset.point, 10);
                const limit = parseInt(input.dataset.limit, 10);

                const val = roomData[chKey][takeKey][pIdx];
                if (val !== undefined && val !== null && val >= 0) {{
                    input.value = val.toLocaleString('en-US');
                    if (val > limit) {{
                        input.classList.add('out-of-spec');
                        input.classList.remove('in-spec');
                    }} else {{
                        input.classList.remove('out-of-spec');
                        input.classList.add('in-spec');
                    }}
                }} else {{
                    input.value = '';
                    input.classList.remove('out-of-spec', 'in-spec');
                }}
            }});

            recalculateSingle();
        }}

        function formatSingleInputAndCalculate(inputEl) {{
            let valStr = inputEl.value.replace(/,/g, '').trim();
            let num = parseInt(valStr, 10);

            const chKey = inputEl.dataset.channel;
            const takeKey = inputEl.dataset.take;
            const pIdx = parseInt(inputEl.dataset.point, 10);
            const limit = parseInt(inputEl.dataset.limit, 10);

            if (!isNaN(num) && num >= 0) {{
                roomData[chKey][takeKey][pIdx] = num;
                inputEl.value = num.toLocaleString('en-US');

                if (num > limit) {{
                    inputEl.classList.add('out-of-spec');
                    inputEl.classList.remove('in-spec');
                }} else {{
                    inputEl.classList.remove('out-of-spec');
                    inputEl.classList.add('in-spec');
                }}
            }} else {{
                roomData[chKey][takeKey][pIdx] = -1;
                inputEl.value = '';
                inputEl.classList.remove('out-of-spec', 'in-spec');
            }}

            recalculateSingle();
        }}

        function recalculateSingle() {{
            updateSingleSummaryCards();
            updateSingleCharts();
            updateSingleMapPins();
        }}

        function getSingleChannelAvg(chKey) {{
            const rawT1 = roomData[chKey].t1.slice(0, numPoints).filter(v => v >= 0);
            const rawT2 = roomData[chKey].t2.slice(0, numPoints).filter(v => v >= 0);

            const sumT1 = rawT1.reduce((a, b) => a + b, 0);
            const sumT2 = rawT2.reduce((a, b) => a + b, 0);

            const countT1 = rawT1.length || 1;
            const countT2 = rawT2.length || 1;

            const avgT1 = Math.round(sumT1 / countT1);
            const avgT2 = Math.round(sumT2 / countT2);
            const avgGlobal = Math.round((avgT1 + avgT2) / 2);

            return {{ avgT1, avgT2, avgGlobal }};
        }}

        function updateSingleSummaryCards() {{
            const container = document.getElementById('singleSummary');
            if (!container) return;
            container.innerHTML = '';

            const channels = [
                {{ key: 'c05', name: docMeta.ch1_name, limitName: 'Max ' + LIMITS.c05.toLocaleString(), limit: LIMITS.c05 }},
                {{ key: 'c1',  name: docMeta.ch2_name, limitName: 'Max ' + LIMITS.c1.toLocaleString(),  limit: LIMITS.c1 }},
                {{ key: 'c5',  name: docMeta.ch3_name, limitName: 'Max ' + LIMITS.c5.toLocaleString(),   limit: LIMITS.c5 }}
            ];

            channels.forEach(ch => {{
                const {{ avgT1, avgT2, avgGlobal }} = getSingleChannelAvg(ch.key);
                const isExceeded = avgGlobal > ch.limit || roomData[ch.key].t1.slice(0, numPoints).some(v => v > ch.limit) || roomData[ch.key].t2.slice(0, numPoints).some(v => v > ch.limit);

                const badgeEl = document.getElementById(`singleBadge${{ch.key === 'c05' ? '05' : ch.key === 'c1' ? '1' : '5'}}`);
                if (badgeEl) {{
                    if (isExceeded) {{
                        badgeEl.innerText = "EXCEDE LÍMITE ISO 8";
                        badgeEl.className = "px-1.5 py-0.5 text-[9px] font-bold rounded-full bg-red-100 text-red-800";
                    }} else {{
                        badgeEl.innerText = "CUMPLE ISO 8";
                        badgeEl.className = "px-1.5 py-0.5 text-[9px] font-bold rounded-full bg-green-100 text-green-800";
                    }}
                }}

                const cardHtml = `
                    <div class="border ${{isExceeded ? 'border-red-300 bg-red-50' : 'border-gray-200 bg-gray-50'}} rounded p-1.5 flex items-center justify-between">
                        <div class="font-bold text-gray-800 border-r border-gray-300 pr-1.5">
                            <span class="block text-[10px] font-extrabold ${{isExceeded ? 'text-red-700' : 'text-gray-900'}}">${{ch.name}}</span>
                            <span class="text-[8px] text-gray-500 font-normal">(${{ch.limitName}})</span>
                        </div>
                        <div class="grid grid-cols-2 gap-x-1.5 text-center text-[8px]">
                            <div>
                                <span class="block text-gray-500 font-semibold">Toma 1</span>
                                <span class="font-mono font-bold text-gray-800">${{avgT1.toLocaleString()}}</span>
                            </div>
                            <div>
                                <span class="block text-gray-500 font-semibold">Toma 2</span>
                                <span class="font-mono font-bold text-gray-800">${{avgT2.toLocaleString()}}</span>
                            </div>
                        </div>
                        <div class="border-l border-gray-300 pl-1.5 text-right">
                            <span class="block text-[8px] text-gray-500 font-bold uppercase">Prom. General</span>
                            <span class="font-mono font-extrabold text-[10px] ${{isExceeded ? 'text-red-600' : 'text-blue-700'}}">${{avgGlobal.toLocaleString()}}</span>
                        </div>
                    </div>
                `;
                container.insertAdjacentHTML('beforeend', cardHtml);
            }});
        }}

        function initSingleCharts() {{
            const labels = Array.from({{length: numPoints}}, (_, i) => `${{i + 1}}`);

            const createConfig = (chKey, limit) => {{
                return {{
                    type: 'line',
                    data: {{
                        labels: labels,
                        datasets: [
                            {{
                                label: 'Toma 1',
                                data: roomData[chKey].t1.slice(0, numPoints).map(v => v >= 0 ? v : null),
                                borderColor: '#0284c7',
                                backgroundColor: 'rgba(2, 132, 199, 0.1)',
                                borderWidth: 1.5,
                                pointRadius: 2,
                                tension: 0.2
                            }},
                            {{
                                label: 'Toma 2',
                                data: roomData[chKey].t2.slice(0, numPoints).map(v => v >= 0 ? v : null),
                                borderColor: '#0d9488',
                                backgroundColor: 'rgba(13, 148, 136, 0.1)',
                                borderWidth: 1.5,
                                pointRadius: 2,
                                tension: 0.2
                            }},
                            {{
                                label: `Límite ISO 8 (${{limit.toLocaleString()}})`,
                                data: Array(numPoints).fill(limit),
                                borderColor: '#ef4444',
                                borderWidth: 1.2,
                                borderDash: [3, 3],
                                pointRadius: 0,
                                fill: false
                            }}
                        ]
                    }},
                    options: {{
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {{
                            legend: {{ display: true, position: 'top', labels: {{ boxWidth: 8, fontSize: 8, padding: 4 }} }}
                        }},
                        scales: {{
                            x: {{ ticks: {{ font: {{ size: 7 }} }} }},
                            y: {{ ticks: {{ font: {{ size: 7 }}, callback: v => v.toLocaleString() }} }}
                        }}
                    }}
                }};
            }};

            const canvas05 = document.getElementById('singleChart05');
            const canvas1 = document.getElementById('singleChart1');
            const canvas5 = document.getElementById('singleChart5');

            if (canvas05) chartInstances['single05'] = new Chart(canvas05.getContext('2d'), createConfig('c05', LIMITS.c05));
            if (canvas1)  chartInstances['single1']  = new Chart(canvas1.getContext('2d'),  createConfig('c1', LIMITS.c1));
            if (canvas5)  chartInstances['single5']  = new Chart(canvas5.getContext('2d'),  createConfig('c5', LIMITS.c5));
        }}

        function updateSingleCharts() {{
            if (!chartInstances['single05']) return;
            chartInstances['single05'].data.datasets[0].data = roomData.c05.t1.slice(0, numPoints).map(v => v >= 0 ? v : null);
            chartInstances['single05'].data.datasets[1].data = roomData.c05.t2.slice(0, numPoints).map(v => v >= 0 ? v : null);
            chartInstances['single05'].update();

            chartInstances['single1'].data.datasets[0].data = roomData.c1.t1.slice(0, numPoints).map(v => v >= 0 ? v : null);
            chartInstances['single1'].data.datasets[1].data = roomData.c1.t2.slice(0, numPoints).map(v => v >= 0 ? v : null);
            chartInstances['single1'].update();

            chartInstances['single5'].data.datasets[0].data = roomData.c5.t1.slice(0, numPoints).map(v => v >= 0 ? v : null);
            chartInstances['single5'].data.datasets[1].data = roomData.c5.t2.slice(0, numPoints).map(v => v >= 0 ? v : null);
            chartInstances['single5'].update();
        }}

        function renderSingleMapPins() {{
            const layer = document.getElementById('singlePinsLayer');
            if (!layer) return;
            layer.innerHTML = '';

            const pinsInfo = (roomMap && roomMap.pins && roomMap.pins.length > 0) 
                ? roomMap.pins.slice(0, numPoints)
                : Array.from({{length: numPoints}}, (_, i) => ({{ point: i + 1, x_pct: (i % 5)*18 + 10, y_pct: Math.floor(i / 5)*20 + 15 }}));

            pinsInfo.forEach((pinData, i) => {{
                const pNum = pinData.point || (i + 1);
                const pin = document.createElement('div');
                pin.className = 'map-pin pass';
                pin.id = `singlePin-${{pNum}}`;
                pin.innerText = pNum;
                pin.style.left = `${{pinData.x_pct}}%`;
                pin.style.top = `${{pinData.y_pct}}%`;
                
                makeDraggable(pin);
                layer.appendChild(pin);
            }});

            updateSingleMapPins();
        }}

        function updateSingleMapPins() {{
            let failCount = 0;
            let passCount = 0;

            for (let p = 0; p < numPoints; p++) {{
                const pin = document.getElementById(`singlePin-${{p + 1}}`);
                if (!pin) continue;

                const c05Exceed = roomData.c05.t1[p] > LIMITS.c05 || roomData.c05.t2[p] > LIMITS.c05;
                const c1Exceed  = roomData.c1.t1[p]  > LIMITS.c1  || roomData.c1.t2[p]  > LIMITS.c1;
                const c5Exceed  = roomData.c5.t1[p]  > LIMITS.c5  || roomData.c5.t2[p]  > LIMITS.c5;

                if (c05Exceed || c1Exceed || c5Exceed) {{
                    pin.className = 'map-pin fail';
                    failCount++;
                }} else {{
                    pin.className = 'map-pin pass';
                    passCount++;
                }}
            }}

            const passEl = document.getElementById('singlePassCountText');
            const failEl = document.getElementById('singleFailCountText');
            if (passEl) passEl.innerText = `Dentro: ${{passCount}}`;
            if (failEl) failEl.innerText = `Fuera: ${{failCount}}`;
        }}

        function makeDraggable(element) {{
            let isDragging = false;

            element.style.cursor = 'grab';
            element.style.touchAction = 'none';

            element.addEventListener('mousedown', startDrag);
            element.addEventListener('touchstart', startDrag, {{ passive: false }});

            function startDrag(e) {{
                isDragging = true;
                element.style.cursor = 'grabbing';
                element.style.zIndex = '100';
                e.preventDefault();
                e.stopPropagation();

                window.addEventListener('mousemove', onMove, {{ capture: true }});
                window.addEventListener('touchmove', onMove, {{ passive: false, capture: true }});
                window.addEventListener('mouseup', stopDrag, {{ capture: true }});
                window.addEventListener('touchend', stopDrag, {{ capture: true }});
            }}

            function onMove(e) {{
                if (!isDragging) return;
                e.preventDefault();
                e.stopPropagation();

                const container = element.parentElement;
                if (!container) return;

                const rect = container.getBoundingClientRect();
                const clientX = (e.touches && e.touches.length > 0) ? e.touches[0].clientX : e.clientX;
                const clientY = (e.touches && e.touches.length > 0) ? e.touches[0].clientY : e.clientY;

                if (clientX === undefined || clientY === undefined) return;

                let x = ((clientX - rect.left) / rect.width) * 100;
                let y = ((clientY - rect.top) / rect.height) * 100;

                x = Math.max(1, Math.min(99, x));
                y = Math.max(1, Math.min(99, y));

                element.style.left = `${{x.toFixed(2)}}%`;
                element.style.top = `${{y.toFixed(2)}}%`;
            }}

            function stopDrag(e) {{
                if (!isDragging) return;
                isDragging = false;
                element.style.cursor = 'grab';
                element.style.zIndex = '30';

                window.removeEventListener('mousemove', onMove, {{ capture: true }});
                window.removeEventListener('touchmove', onMove, {{ capture: true }});
                window.removeEventListener('mouseup', stopDrag, {{ capture: true }});
                window.removeEventListener('touchend', stopDrag, {{ capture: true }});
            }}
        }}
    </script>
</body>
</html>"""
    return html_template

