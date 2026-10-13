import pandas as pd
import numpy as np

# ----------------------------
# 1️⃣ Load daily forecast CSV (realistic)
# ----------------------------
daily_forecast_file = "forecast/daily_forecast_location_realistic.csv"
df = pd.read_csv(daily_forecast_file)
df['ds'] = pd.to_datetime(df['ds'])

# ----------------------------
# 2️⃣ Tentukan lokasi dan kapasitas per lokasi
# ----------------------------
locations = ['P1W', 'P1E', 'P2W', 'P2E', 'P3W', 'P3E']

# contoh kapasitas per lokasi (bisa diubah sesuai kesepakatan kelompok)
capacity = {
    'P1W': 300,
    'P1E': 300,
    'P2W': 300,
    'P2E': 300,
    'P3W': 400,
    'P3E': 400
}

# threshold untuk warning, misal jika tersisa <= 20 slot
warning_threshold = 50

# ----------------------------
# 3️⃣ Tambahkan kolom year & week
# ----------------------------
df['year'] = df['ds'].dt.isocalendar().year
df['week'] = df['ds'].dt.isocalendar().week

# ----------------------------
# 4️⃣ Hitung prediksi per minggu per lokasi
# ----------------------------
weekly_data = df.groupby(['year', 'week'])[ [loc+'_predicted' for loc in locations] ].sum().reset_index()

# rename kolom supaya lebih rapi
weekly_data.columns = ['year', 'week'] + [loc+'_predicted' for loc in locations]

# ----------------------------
# 5️⃣ Hitung slot tersedia dan status Full/Warning/Normal
# ----------------------------
for loc in locations:
    weekly_data[loc+'_available'] = capacity[loc] - weekly_data[loc+'_predicted']
    # status
    def get_status(x):
        if x <= 0:
            return "Full"
        elif x <= warning_threshold:
            return "Warning"
        else:
            return "Normal"
    weekly_data[loc+'_status'] = weekly_data[loc+'_available'].apply(get_status)
    # pastikan tidak ada nilai negatif
    weekly_data[loc+'_available'] = weekly_data[loc+'_available'].apply(lambda x: max(x,0))

# ----------------------------
# 6️⃣ Hitung total kendaraan per minggu
# ----------------------------
weekly_data['total_vehicles'] = weekly_data[[loc+'_predicted' for loc in locations]].sum(axis=1)

# ----------------------------
# 7️⃣ Simpan CSV hasil forecast weekly
# ----------------------------
output_file = "forecast/weekly_forecast_location_realistic.csv"
weekly_data.to_csv(output_file, index=False)

print(f"Weekly forecast per location (realistic) successfully created! CSV saved in {output_file}")