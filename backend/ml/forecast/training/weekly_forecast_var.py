import pandas as pd
import numpy as np

# Nama CSV daily terakhir
daily_csv = "forecast/daily_forecast_location_realistic.csv"

# Kapasitas tiap lokasi (ubah sesuai kapasitas baru)
capacity = {
    "P1W": 300,
    "P1E": 300,
    "P2W": 300,
    "P2E": 700,
    "P3W": 1000,
    "P3E": 650
}

# Baca CSV daily
df_daily = pd.read_csv(daily_csv, parse_dates=['ds'])

# Ambil nama lokasi
locations = [loc for loc in capacity.keys()]

# Tambahkan kolom minggu & tahun
df_daily['year'] = df_daily['ds'].dt.year
df_daily['week'] = df_daily['ds'].dt.isocalendar().week

weekly_rows = []

# Loop per tahun dan minggu
for (y, w), group in df_daily.groupby(['year','week']):
    row = {'year': y, 'week': w}
    total_vehicles = 0
    
    for loc in locations:
        # Jumlahkan prediksi harian untuk lokasi ini
        pred_sum = group[f"{loc}_predicted"].sum()
        total_vehicles += pred_sum
        
        # Hitung slot tersedia (kapasitas - prediksi harian rata-rata)
        avg_pred = group[f"{loc}_predicted"].mean()
        available = max(capacity[loc] - avg_pred, 0)
        
        # Tentukan status
        if available == 0:
            status = "Full"
        elif available / capacity[loc] < 0.1:
            status = "Warning"
        else:
            status = "Normal"
        
        row[f"{loc}_predicted"] = pred_sum
        row[f"{loc}_available"] = round(available,2)
        row[f"{loc}_status"] = status
    
    row['total_vehicles'] = total_vehicles
    weekly_rows.append(row)

# Buat DataFrame weekly
df_weekly = pd.DataFrame(weekly_rows)

# Simpan CSV
output_csv = "forecast/weekly_forecast_location_var.csv"
df_weekly.to_csv(output_csv, index=False)
print(f"Weekly forecast success. CSV saved as {output_csv}")