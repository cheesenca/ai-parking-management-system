import pandas as pd

# Load daily forecast
df = pd.read_csv("forecast/daily_forecast_location_compare_realistic.csv")

# Nama lokasi
locations = ['P1W', 'P1E', 'P2W', 'P2E', 'P3W', 'P3E']

# Tambahkan kolom tahun dan minggu
df['ds'] = pd.to_datetime(df['ds'])
df['year'] = df['ds'].dt.isocalendar().year
df['week'] = df['ds'].dt.isocalendar().week

# Kapasitas harian per lokasi (sesuaikan)
daily_capacity = {'P1W': 200, 'P1E': 200, 'P2W': 200, 'P2E': 200, 'P3W': 400, 'P3E': 300}

# Hitung prediksi mingguan per lokasi
weekly_data = df.groupby(['year','week'])[ [loc+"_predicted" for loc in locations] ].sum().reset_index()

# Hitung available & status per lokasi
for loc in locations:
    weekly_capacity = daily_capacity[loc] * 7  # kapasitas mingguan
    weekly_data[loc+"_available"] = weekly_capacity - weekly_data[loc+"_predicted"]
    threshold = weekly_capacity * 0.1
    weekly_data[loc+"_status"] = weekly_data[loc+"_available"].apply(
        lambda x: "Full" if x <= 0 else ("Warning" if x <= threshold else "Normal")
    )

# Total kendaraan per minggu
weekly_data["total_vehicles"] = weekly_data[[loc+"_predicted" for loc in locations]].sum(axis=1)

# Save CSV
weekly_data.to_csv("forecast/weekly_forecast_location_realistic.csv", index=False)
print("Weekly realistic forecast created successfully!")