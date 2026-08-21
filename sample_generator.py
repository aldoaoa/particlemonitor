import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import io

def generate_sample_excel_bytes():
    """Generates sample cleanroom particle measurement Excel file for 6 rooms (Cuarto 1 to Cuarto 6)."""
    start_time = datetime(2025, 7, 21, 8, 30, 0)
    
    # Base realistic values per room
    c05_base = [986090, 1146810, 1222830, 1340370, 1158220, 1780510, 1242410, 1282758, 1120280, 1182300, 1386470, 1321280, 1242410, 2266720, 1172810, 1062300, 1111220, 1182180, 1182110, 1482110]
    c1_base  = [112541, 145550, 184223, 139227, 124500, 341200, 158210, 122765, 145210, 122678, 128210, 172420, 75110, 214200, 81200, 92100, 102100, 184223, 122678, 168200]
    c5_base  = [2947, 3110, 4810, 6210, 4820, 5183, 5770, 4533, 6434, 5174, 2819, 6571, 4210, 5210, 1878, 1280, 4533, 4414, 5200, 4810]

    rows = []
    current_time = start_time
    np.random.seed(42)

    # 6 rooms x 20 points x 2 takes = 240 rows
    for r in range(1, 7):
        # Room factor to introduce slight variations per room
        room_factor = 1.0 + (r - 1) * 0.05

        for p in range(20):
            # Toma 1
            t_str1 = current_time.strftime("%Y-%m-%d %H:%M:%S")
            temp1 = round(21.15 + np.random.normal(0, 0.2), 2)
            rh1 = round(48.32 + np.random.normal(0, 0.5), 2)
            rows.append({
                "Time": t_str1,
                "Temp": temp1,
                "RH": rh1,
                "CH1 Size": 0.5,
                "CH2 Size": 1.0,
                "CH3 Size": 5.0,
                "CntsCumM3 CH1": int(c05_base[p] * room_factor),
                "CntsCumM3 CH2": int(c1_base[p] * room_factor),
                "CntsCumM3 CH3": int(c5_base[p] * room_factor)
            })
            current_time += timedelta(minutes=2)

            # Toma 2
            t_str2 = current_time.strftime("%Y-%m-%d %H:%M:%S")
            temp2 = round(21.15 + np.random.normal(0, 0.2), 2)
            rh2 = round(48.32 + np.random.normal(0, 0.5), 2)
            rows.append({
                "Time": t_str2,
                "Temp": temp2,
                "RH": rh2,
                "CH1 Size": 0.5,
                "CH2 Size": 1.0,
                "CH3 Size": 5.0,
                "CntsCumM3 CH1": int(c05_base[p] * room_factor * 0.95),
                "CntsCumM3 CH2": int(c1_base[p] * room_factor * 0.95),
                "CntsCumM3 CH3": int(c5_base[p] * room_factor * 0.95)
            })
            current_time += timedelta(minutes=2)

    df = pd.DataFrame(rows)
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Mediciones_Cuartos_1_6')
    
    return output.getvalue()
