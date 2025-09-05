#%% Import libraries
import os
import pandas as pd
from dotenv import load_dotenv
from fitbit_client import FitbitClient
from data_preprocessing import *

import matplotlib.pyplot as plt
import seaborn as sns

import warnings
warnings.simplefilter(action='ignore', category=FutureWarning)
warnings.simplefilter(action='ignore', category=UserWarning)

# %% Initialize fitbit client and fetch data
# Load environment variables
load_dotenv()
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI")

# Initialize Fitbit client
fb = FitbitClient(CLIENT_ID, CLIENT_SECRET, REDIRECT_URI)

# Fetch data
params = {
    "detail": "5min",
    "start_date": "2021-10-01",
    "end_date": "2021-10-31"
}
steps = fb.get_timeseries("steps", params)
hr = fb.get_timeseries("heart", params)
azm = fb.get_timeseries("active-zone-minutes", params)
sleep = fb.get_sleep(params)

#%% Process data
df_steps = pd.DataFrame(steps)
df_hr = pd.DataFrame(hr)
df_azm = process_azm_data(azm)
df_sleep = process_sleep_data(sleep)

# Merge data
df = merge_dataframes(df_steps, df_hr, df_azm, df_sleep)
df = get_datetime_params(df)
print(df.head())

# Save data
save_df = True
if save_df:
    df.to_csv(f"data/df_{params['start_date']}_{params['end_date']}.csv", index=False)

#%% Load data
df = pd.read_csv("data/df_2021-10-01_2021-10-31.csv")

# %% Daily parameters by day of month
start_dt = pd.to_datetime('08:00:00').time()
end_dt = pd.to_datetime('12:00:00').time()
df_rest_hr = df.loc[(df['time_dt'] >= start_dt) & (df['time_dt'] <= end_dt)].groupby(
    ['date', 'day_of_month'])[['heart_rate']].mean().reset_index()
df_count = df.groupby(['date', 'day_of_month'])[['steps', 'active_zm']].sum().reset_index()

df.loc[(df['sleep_stage'].isna()) & (df['time_of_day'] == 'night'), 'sleep_stage'] = 'light'
df.loc[(df['sleep_stage'].isna()) & (df['time_of_day'] != 'night'), 'sleep_stage'] = 'wake'
df["is_sleep"] = df["sleep_stage"].ne("wake")
df["elapsed"] = df["datetime_dt"].diff()
df["sleep_elapsed"] = df["elapsed"].where(df["is_sleep"],  pd.Timedelta(0))
sleep_total = df.groupby('sleep_night')['sleep_elapsed'].sum().reset_index()
sleep_total['sleep_hours'] = sleep_total['sleep_elapsed'].dt.total_seconds() / 3600
sleep_total = sleep_total.drop([sleep_total.index[0], sleep_total.index[-1]])
sleep_total['day_of_month'] = pd.to_datetime(sleep_total['sleep_night']).dt.day

fig, ax = plt.subplots(2, 2, figsize=(12, 10), sharex=True)

ax[0, 0].plot(df_rest_hr['day_of_month'], df_rest_hr['heart_rate'], marker='o', color='tab:red')
ax[0, 0].set_title('Resting heart rate', fontsize=12)
ax[0, 0].set_ylabel('Heart rate (bpm)', fontsize=10)

ax[0, 1].plot(df_count['day_of_month'], df_count['steps'], marker='o', color='tab:green')
ax[0, 1].set_title('Daily steps', fontsize=12)
ax[0, 1].set_ylabel('Step count (-)', fontsize=10)
steps_ticks = range(5000, 25001, 5000)
ax[0, 1].set_yticks(steps_ticks)
ax[0, 1].set_yticklabels([f"{round(x/1000)}k" for x in steps_ticks], fontsize=10)

ax[1, 0].plot(df_count['day_of_month'], df_count['active_zm'], marker='o', color='tab:orange')
ax[1, 0].set_title('Daily active time', fontsize=12)
ax[1, 0].set_ylabel('Active zone time (min)', fontsize=10)
ax[1, 0].set_xlabel('Day of month', fontsize=10)

ax[1, 1].plot(sleep_total['day_of_month'], sleep_total['sleep_hours'], marker='o', color='tab:blue')
ax[1, 1].set_title('Daily sleep duration', fontsize=12)
ax[1, 1].set_ylabel('Sleep duration (hours)', fontsize=10)
ax[1, 1].set_xlabel('Day of month', fontsize=10)

for i in range(2):
    for j in range(2):
        ax[i, j].set_xticks([1, 7, 14, 21, 28])

# %% Heart rate over time by day of week
df_plt = df.groupby(['time_float', 'day_of_week'])[['heart_rate']].mean().reset_index()

plt.figure(figsize=(5, 4))
day_of_week_order = ['Mon', 'Tue', 'Wed', 'Thu', 'Sat', 'Sun']
sns.lineplot(data=df_plt, x='time_float', y='heart_rate', hue='day_of_week',
             hue_order=(day_of_week_order))
plt.xlabel("Time of day", fontsize=12)
plt.ylabel("Heart rate (bpm)", fontsize=12)
plt.xticks(
    ticks=range(0, 25, 4), 
    labels=[f"{h:02d}:00" for h in range(0, 25, 4)],
    fontsize=10
)
plt.yticks(fontsize=10)
plt.legend(title="", fontsize=10, loc='upper left', frameon=False)
plt.gca().spines[['top', 'right']].set_visible(False)
plt.tight_layout()

# %% Heart rate over time
plt.figure(figsize=(5, 4))
sns.lineplot(data=df, x='time_float', y='heart_rate')
plt.xlabel("Time of day", fontsize=12)
plt.ylabel("Heart rate (bpm)", fontsize=12)
plt.xticks(
    ticks=range(0, 25, 4), 
    labels=[f"{h:02d}:00" for h in range(0, 25, 4)],
    fontsize=10
)
plt.yticks(fontsize=10)
plt.legend(title="", fontsize=10, loc='upper right', frameon=False)
plt.gca().spines[['top', 'right']].set_visible(False)
plt.tight_layout()

# %% Heart rate heatmap
heatmap_data = df.pivot(index='date', columns='time', values='heart_rate')

plt.figure(figsize=(7, 5))
ax = sns.heatmap(heatmap_data, cmap="coolwarm", xticklabels=24, 
                 yticklabels=False,  cbar=False)

plt.title("Heart rate (bpm)", fontsize=12)
plt.xlabel("Time of day", fontsize=10)
plt.ylabel("Date", fontsize=10)
plt.xticks(fontsize=8)
plt.tight_layout()
plt.show()

#%% Heart rate by activity level
df_plt = df.groupby(['date', 'activity_level'])[['heart_rate']].mean().reset_index()
plt.figure(figsize=(4, 4))
sns.violinplot(data=df_plt, x='activity_level', y='heart_rate', width=0.8,
               linewidth=0.8, hue='activity_level', palette='tab10', alpha=0.6, 
               common_norm=True, linecolor='black')
plt.xlabel("Activity level", fontsize=12)
plt.ylabel("Heart rate (bpm)", fontsize=12)
plt.xticks(fontsize=10)
plt.yticks(fontsize=10)
plt.gca().spines[['top', 'right']].set_visible(False)
plt.tight_layout()

plt.figure(figsize=(5, 4))
sns.histplot(data=df_plt, x='heart_rate', hue='activity_level', bins=30, palette='tab10', 
             element='step', stat='density', common_norm=True, legend=True)
plt.xlabel("Heart rate (bpm)", fontsize=12)
plt.ylabel("Probability (-)", fontsize=12)
plt.xticks(fontsize=10)
plt.yticks(fontsize=10)
sns.move_legend(plt.gca(), loc='best', title='', frameon=False, fontsize=12)
plt.gca().spines[['top', 'right']].set_visible(False)
plt.tight_layout()
plt.show()

# %% Sleep stage analysis
sleep_type = df.groupby(['sleep_night', 'sleep_stage'])['sleep_elapsed'].sum().reset_index()
sleep_type['sleep_hours'] = sleep_type['sleep_elapsed'].dt.total_seconds() / 3600
sleep_type = sleep_type[sleep_type['sleep_night'] != sleep_type['sleep_night'].values[0]]
sleep_type = sleep_type[sleep_type['sleep_night'] != sleep_type['sleep_night'].values[-1]]
sleep_type = sleep_type.drop(sleep_type[sleep_type['sleep_stage'] == 'wake'].index)
sleep_type['day_of_month'] = pd.to_datetime(sleep_type['sleep_night']).dt.day

fig, ax = plt.subplots(1, 2, figsize=(7, 4), sharey=True, width_ratios=[1.5, 1])

sns.pointplot(data=sleep_type, x='day_of_month', y='sleep_hours',
                       hue='sleep_stage', hue_order=['light', 'rem', 'deep'], 
                       markersize=5, legend=False, ax=ax[0])
ax[0].set_ylabel('Sleep duration (hours)', fontsize=12)
ax[0].set_xlabel('Day of month', fontsize=12)
ax[0].set_xticks([1, 7, 14, 21, 28])
ax[0].set_xmargin(0.05)
ax[0].tick_params(labelsize=10)
ax[0].spines[['top', 'right']].set_visible(False)

sns.violinplot(data=sleep_type, x='sleep_stage', y='sleep_hours', order=['light', 'rem', 'deep'], 
               width=0.8, linewidth=0.8, hue='sleep_stage', hue_order=['light', 'rem', 'deep'], 
               alpha=0.8, common_norm=True, linecolor='black', legend=True, ax=ax[1])
ax[1].set_xlabel("Sleep stage", fontsize=12)
ax[1].set_ylabel("Sleep duration (hours)", fontsize=12)
ax[1].tick_params(labelsize=10)
ax[1].spines[['top', 'right']].set_visible(False)
sns.move_legend(ax[1], loc='best', title='', frameon=False, fontsize=12)

plt.tight_layout()
plt.show()

# %% Activity level analysis
activity_stage = df.groupby(['day_of_month', 'activity_level'])[['active_zm']].count().reset_index()
activity_stage['activity_level'] = activity_stage['activity_level'].cat.remove_categories('None')
activity_stage.dropna(inplace=True)
activity_stage['active_zm'] = activity_stage['active_zm'] * 5

fig, ax = plt.subplots(1, 2, figsize=(7, 4), sharey=True, width_ratios=[1.5, 1])

sns.pointplot(data=activity_stage, x='day_of_month', y='active_zm',
               hue='activity_level', markersize=5, legend=False, ax=ax[0])
ax[0].set_ylabel('Active time (min)', fontsize=12)
ax[0].set_xlabel('Day of month', fontsize=12)
ax[0].set_xticks([1, 7, 14, 21, 28])
ax[0].set_xmargin(0.05)
ax[0].set_ymargin(0.05)
ax[0].tick_params(labelsize=10)
ax[0].spines[['top', 'right']].set_visible(False)

sns.boxplot(data=activity_stage, x='activity_level', y='active_zm', 
            hue='activity_level', width=0.5, linecolor='black', medianprops={"linewidth": 2},
            flierprops={'marker': 'o', 'markeredgecolor': 'black', 'markersize': 4},
            legend=True, ax=ax[1])
ax[1].set_xlabel("Activity level", fontsize=12)
ax[1].set_ylabel("Active time (min)", fontsize=12)
ax[1].tick_params(labelsize=10)
ax[1].set_ymargin(0.05)
ax[1].spines[['top', 'right']].set_visible(False)
sns.move_legend(ax[1], loc='best', title='', frameon=False, fontsize=12)

plt.tight_layout()
plt.show()
