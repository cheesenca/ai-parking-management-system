import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# Load preprocessed dataset
df = pd.read_csv("dataset/ParkingRecord_Preprocessed.csv")
df['TIME_SCAN'] = pd.to_datetime(df['TIME_SCAN'])

# distribution vehichle of each member category
plt.figure(figsize=(8,5))
sns.countplot(x='member_category', data=df)
plt.title("distribution vehichle of each member category")
plt.show()

# distribution vehichle of each vehicle type
plt.figure(figsize=(8,5))
sns.countplot(x='vehicle_type', data=df)
plt.title("distribution vehichle of each vehicle type")
plt.show()

# Peak hour of each member category
plt.figure(figsize=(12,5))
sns.countplot(x='hour', hue='member_category', data=df)
plt.title("Peak hour of each member category")
plt.show()