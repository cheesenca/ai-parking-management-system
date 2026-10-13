import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# Load preprocessed dataset
df = pd.read_csv("dataset/ParkingRecord_Preprocessed.csv")
df['TIME_SCAN'] = pd.to_datetime(df['TIME_SCAN'])

# Distribution vehicle of each member category
plt.figure(figsize=(8,5))
sns.countplot(x='member_category', data=df)
plt.title("Distribution vehicle of each member category")
plt.show()

# Distribution vehicle of each vehicle type
plt.figure(figsize=(8,5))
sns.countplot(x='vehicle_type', data=df)
plt.title("Distribution vehicle of each vehicle type")
plt.show()

# Peak hour of each member category
plt.figure(figsize=(12,5))
sns.countplot(x='hour', hue='member_category', data=df)
plt.title("Peak hour of each member category")
plt.show()

# Daily trend amount of vehicle
daily_count = df.groupby('date').size()
plt.figure(figsize=(12,5))
daily_count.plot()
plt.title("Daily trend amount of vehicle")
plt.xlabel("Date")
plt.ylabel("amount of vehicle")
plt.show()

# weekly trend amount of vehicle
weekly_count = df.groupby(pd.Grouper(key='TIME_SCAN', freq='W')).size()
plt.figure(figsize=(12,5))
weekly_count.plot()
plt.title("weekly tyrend amount of vehicle")
plt.xlabel("Week")
plt.ylabel("amount of vehicle")
plt.show()

# Monthly trend amount of vehicle type
monthly_count = df.groupby(['month', 'vehicle_type']).size().unstack()
monthly_count.plot(kind='bar', figsize=(12,5))
plt.title("Monthly trend amount of vehicle type")
plt.xlabel("Month")
plt.ylabel("amount of vehicle")
plt.show()