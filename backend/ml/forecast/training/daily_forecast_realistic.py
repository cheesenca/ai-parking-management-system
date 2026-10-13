# daily_forecast_realistic.py
import pandas as pd

# Load daily forecast hasil model (Prophet/ARIMA)
df = pd.read_csv("forecast/daily_forecast_location_compare_realistic.csv")

# Tentukan kapasitas slot baru per lokasi
total_slots = {
    "P1W": 300,
    "P1E": 300,
    "P2W": 300,
    "P2E": 300,
    "P3W": 400,
    "P3E": 400
}

# Hitung ulang available dan status
for loc in total_slots.keys():
    pred_col = f"{loc}_predicted"
    avail_col = f"{loc}_available"
    status_col = f"{loc}_status"
    
    # Available = total slot - predicted vehicles
    df[avail_col] = total_slots[loc] - df[pred_col]
    
    # Status berdasarkan jumlah slot tersisa
    def status(x):
        if x <= 0:
            return "Full"
        elif x <= 10:
            return "Warning"
        else:
            return "Normal"
    
    df[status_col] = df[avail_col].apply(status)

# Simpan CSV baru
df.to_csv("forecast/daily_forecast_location_final_realistic.csv", index=False)

# Opsional: buat summary total kendaraan per hari
df['total_vehicles'] = df[[f"{loc}_predicted" for loc in total_slots.keys()]].sum(axis=1)
df['total_slot_remaining'] = df[[f"{loc}_available" for loc in total_slots.keys()]].sum(axis=1)
df['overall_status'] = df['total_slot_remaining'].apply(lambda x: "Full" if x <= 0 else ("Warning" if x < 10 else "Normal"))

summary = df[['ds', 'total_vehicles', 'total_slot_remaining', 'overall_status']]
summary.rename(columns={'ds': 'Tanggal', 'total_vehicles': 'Total_Kendaraan',
                        'total_slot_remaining': 'Total_Slot_Tersisa', 'overall_status': 'Status'},
               inplace=True)
summary.to_csv("forecast/daily_forecast_summary_realistic.csv", index=False)

print("Daily forecast with new capacity completed. CSV ready for dashboard.")