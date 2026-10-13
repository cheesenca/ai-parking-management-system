import pandas as pd

# Load dataset

df = pd.read_csv("dataset/ParkingRecord_Updated.csv")

print("=== Preview first dataset ===")
print(df.head())
print(df.info())

# confersion column TIME_SCAN into datetime
df['TIME_SCAN'] = pd.to_datetime(df['TIME_SCAN'])

# Buat fitur tambahan
df['date'] = df['TIME_SCAN'].dt.date           # just only date
df['hour'] = df['TIME_SCAN'].dt.hour           # jam kendaraan masuk/keluar
df['day_of_week'] = df['TIME_SCAN'].dt.day_name()  # Monday, Tuesday, ...
df['month'] = df['TIME_SCAN'].dt.month         # 1–12

# Preview dataset after preprocessing
print("\n=== dataset after preprocessing ===")
print(df.head())
print(df.info())

# (Opsional) saved dataset from preprocessing
df.to_csv("dataset/ParkingRecord_Preprocessed.csv", index=False)
print("\nDataset preprocessing saved in dataset/ParkingRecord_Preprocessed.csv")