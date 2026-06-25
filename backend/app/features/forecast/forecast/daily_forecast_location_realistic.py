# forecast/daily_forecast_location_realistic.py

import pandas as pd
import numpy as np

# CONFIG
input_csv = "forecast/daily_forecast_location_compare_realistic.csv"  # file input lama
output_csv = "forecast/daily_forecast_location_realistic.csv"          # file output baru

# Kapasitas slot per lokasi
capacities = {
    "P1W": 300,
    "P1E": 300,
    "P2W": 300,
    "P2E": 300,
    "P3W": 300,
    "P3E": 300
}

# Threshold untuk Warning (misal < 10% slot tersisa)
warning_threshold_ratio = 0.1

# LOAD DATA
df = pd.read_csv(input_csv)

# BUAT VARIABEL AVAILABLE DAN STATUS 
for loc in capacities.keys():
    pred_col = f"{loc}_predicted"
    avail_col = f"{loc}_available"
    status_col = f"{loc}_status"
    
    # Hitung slot tersisa
    df[avail_col] = capacities[loc] - df[pred_col]
    
    # Pastikan tidak negatif
    df[avail_col] = df[avail_col].apply(lambda x: max(0, x))
    
    # Tentukan status
    def compute_status(available):
        if available == 0:
            return "Full"
        elif available <= capacities[loc] * warning_threshold_ratio:
            return "Warning"
        else:
            return "Normal"
    
    df[status_col] = df[avail_col].apply(compute_status)

#  HITUNG TOTAL KENDARAAN 
predicted_cols = [f"{loc}_predicted" for loc in capacities.keys()]
df['total_vehicles'] = df[predicted_cols].sum(axis=1)

#  SIMPAN CSV BARU 
df.to_csv(output_csv, index=False)
print(f"Daily forecast per location (realistic) saved: {output_csv}")