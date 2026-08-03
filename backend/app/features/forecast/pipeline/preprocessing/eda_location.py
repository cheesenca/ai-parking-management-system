import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# Load preprocessed dataset
df = pd.read_csv("dataset/ParkingRecord_Preprocessed.csv")
df['TIME_SCAN'] = pd.to_datetime(df['TIME_SCAN'])


# Number of vehicles per location
location_count = df['POS_PARK_LOCATION'].value_counts()
print("Number of vehicles per location (historical):")
print(location_count)

# Proportion of vehicles per location
location_prop = df['POS_PARK_LOCATION'].value_counts(normalize=True)
print("\nProportion of vehicles per location:")
print(location_prop)

# Vehicle visualization per location
plt.figure(figsize=(12,5))
sns.countplot(x='POS_PARK_LOCATION', data=df,
              order=df['POS_PARK_LOCATION'].value_counts().index)
plt.title("Vehicle visualization per location")
plt.xlabel("POS Park Location")
plt.ylabel("Amount of Vehicle")
plt.show()

#Daily trends per location
daily_location = df.groupby(['date','POS_PARK_LOCATION']).size().unstack(fill_value=0)
daily_location.plot(figsize=(14,6))
plt.title("Daily trends per location")
plt.xlabel("Date")
plt.ylabel("Amount of Vehicle")
plt.show()