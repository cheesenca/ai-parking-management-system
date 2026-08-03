import pandas as pd
import numpy as np

# --- Load daily forecast per lokasi ---
df = pd.read_csv("forecast/daily_forecast_location_compare_realistic.csv")
df['ds'] = pd.to_datetime(df['ds'])

# --- Tambahkan kolom tahun & minggu ---
df['year'] = df['ds'].dt.year
df['week'] = df['ds'].dt.isocalendar().week

# --- Tentukan nama lokasi ---
locations = ['P1W','P1E','P2W','P2E','P3W','P3E']

# --- Hitung kendaraan per minggu per lokasi ---
# Gunakan kolom *_predicted
pred_columns = [loc+'_predicted' for loc in locations]
df_pred = df[['year','week'] + pred_columns].copy()

# Pivot tidak diperlukan karena sudah column per lokasi
weekly_data = df_pred.groupby(['year','week'])[pred_columns].sum().reset_index()

# --- Hitung total kendaraan per minggu ---
weekly_data['total_vehicles'] = weekly_data[pred_columns].sum(axis=1)

# --- Hitung available slot per lokasi ---
# Misal kapasitas per lokasi (sesuai asumsi Capstone)
capacity_per_location = {
    'P1W': 192, 'P1E': 192,
    'P2W': 192, 'P2E': 128,
    'P3W': 320, 'P3E': 256
}

for loc in locations:
    weekly_data[loc+'_available'] = capacity_per_location[loc] - weekly_data[loc+'_predicted']
    # Pastikan minimal 0
    weekly_data[loc+'_available'] = weekly_data[loc+'_available'].apply(lambda x: max(0, x))
    # Tentukan status
    def status(x):
        if x == 0:
            return 'Full'
        elif x / capacity_per_location[loc] < 0.1:
            return 'Warning'
        else:
            return 'Normal'
    weekly_data[loc+'_status'] = weekly_data[loc+'_available'].apply(status)

# --- Simpan CSV weekly forecast ---
weekly_data.to_csv("forecast/weekly_forecast_location_final.csv", index=False)

print("Weekly forecast per location successfully created. CSV saved as forecast/weekly_forecast_location_final.csv")