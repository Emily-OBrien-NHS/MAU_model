import os
import simpy
import random
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

os.chdir('C:/Users/obriene/Projects/MAU model/outputs')

scenario_name = 'baseline'
patient_df = pd.read_csv(scenario_name + ' mau patients.csv')
mau_occ_df = pd.read_csv(scenario_name + ' mau occupancy.csv')

plot_folder = scenario_name + ' plots'
if not os.path.exists(plot_folder):
   os.makedirs(plot_folder)
os.chdir(f'C:/Users/obriene/Projects/MAU model/outputs/{plot_folder}')


run0 = mau_occ_df.loc[(mau_occ_df['run'] == 0) & (mau_occ_df['beds occupied'] != 0)].copy()
run0.plot(x='time', y='beds occupied', title='MAU Beds Occupancy',
          xlabel='time (minutes)', ylabel='Number of Beds Occupied')
run0.plot(x='time', y='queue length', title='MAU Queue',
          xlabel='time (minutes)', ylabel='Number of Patients in Queue')

#Avergae bed occupancy doesn't hit up agaist the limit.
av_mau_occ = mau_occ_df.groupby('time', as_index=False).mean().sort_values(by='time')
av_mau_occ = av_mau_occ.loc[(av_mau_occ['beds occupied'] > 0)].copy()
ax = av_mau_occ.plot(x='time', y='beds occupied', title='MAU Beds Occupancy',
                xlabel='time (minutes)', ylabel='Number of Beds Occupied')
fig = ax.get_figure()
fig.savefig('MAU Bed Occupancy.png')

(patient_df.dropna(subset='time in MAU queue').groupby('simulation arrival day', as_index=False)
 ['time in MAU queue'].mean().sort_values(by='simulation arrival day')
 .plot(x='simulation arrival day', y='time in MAU queue', title='Average wait to enter MAU by simulation day',
       ylabel='time (minutes)'))
