import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import io

def generate_sample_excel_bytes():
    """Generates sample cleanroom particle measurement Excel file as bytes."""
    start_time = datetime(2025, 7, 21, 8, 30, 0)
    
    # Sample realistic values matching the PDF/HTML example report (20 points x 2 takes = 40 rows)
    c05_t1 = [986090, 1146810, 1222830, 1340370, 1158220, 1780510, 1242410, 1282758, 1120280, 1182300, 1386470, 1321280, 1242410, 2266720, 1172810, 1062300, 1111220, 1182180, 1182110, 1482110]
    c05_t2 = [908291, 1112610, 1182200, 1411620, 1102100, 1682100, 1152800, 1404503, 1082100, 1112100, 1282100, 1217677, 1118770, 2182100, 1116810, 1012100, 1082180, 1102182, 1112100, 1382100]

    c1_t1 = [112541, 145550, 184223, 139227, 124500, 341200, 158210, 122765, 145210, 122678, 128210, 172420, 75110, 214200, 81200, 92100, 102100, 184223, 122678, 168200]
    c1_t2 = [102100, 128210, 162100, 128200, 114121, 312100, 142100, 122651, 132100, 118222, 118200, 154387, 72100, 192733, 78100, 88100, 98200, 162100, 118222, 152100]

    c5_t1 = [2947, 3110, 4810, 6210, 4820, 5183, 5770, 4533, 6434, 5174, 2819, 6571, 4210, 5210, 1878, 1280, 4533, 4414, 5200, 4810]
    c5_t2 = [2810, 2980, 4520, 6114, 4540, 5040, 5510, 4485, 6120, 4810, 2577, 6210, 3980, 5004, 1676, 1201, 4310, 4122, 4980, 4510]

    rows = []
    current_time = start_time
    np.random.seed(42)

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
            "CntsCumM3 CH1": c05_t1[p],
            "CntsCumM3 CH2": c1_t1[p],
            "CntsCumM3 CH3": c5_t1[p]
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
            "CntsCumM3 CH1": c05_t2[p],
            "CntsCumM3 CH2": c1_t2[p],
            "CntsCumM3 CH3": c5_t2[p]
        })
        current_time += timedelta(minutes=3)

    df = pd.DataFrame(rows)
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Mediciones')
    
    return output.getvalue()
