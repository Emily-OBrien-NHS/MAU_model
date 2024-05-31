import os
import simpy
import random
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

os.chdir('C:/Users/obriene/Projects/MAU model/outputs')

scenario_name = 'baseline'
patient_df = pd.read_csv(scenario_name + ' mau patients.csv')
occ_df = pd.read_csv(scenario_name + ' mau occupancy.csv')

plot_folder = scenario_name + ' plots'
if not os.path.exists(plot_folder):
   os.makedirs(plot_folder)
os.chdir(f'C:/Users/obriene/Projects/MAU model/outputs/{plot_folder}')


for run in patient_df['run'].drop_duplicates().values:
    #Filter the occupancy data
    run_n = occ_df.loc[(occ_df['run'] == run) & (occ_df['MAU beds occupied'] != 0)].copy()
    #Number of MAU Beds occupied
    ax = run_n.plot(x='time', y='MAU beds occupied', title='MAU Beds Occupancy',
            xlabel='time (minutes)', ylabel='Beds Occupied')
    fig = ax.get_figure()
    fig.savefig(f'Run {run} MAU Bed Occupancy.png')
    #ED Occupancy
    ax = run_n.plot(x='time', y='ED Occupancy', title='ED Occupancy',
            xlabel='time (minutes)', ylabel='patients')
    fig = ax.get_figure()
    fig.savefig(f'Run {run} ED Occupancy.png')
    #Number of patients in MAU Queue
    ax = run_n.plot(x='time', y='MAU queue length', title='MAU Queue',
            xlabel='time (minutes)', ylabel='Number of Patients in Queue')
    fig = ax.get_figure()
    fig.savefig(f'Run {run} Number of patients in MAU Queue.png')

    #filter the patient data
    pat_run_n = (patient_df[(patient_df['run'] == run) & (patient_df['patient ID'] > 0)].copy()
                 .groupby('simulation arrival day', as_index=False).mean(numeric_only=True))
    
    #Time spent in ED
    ax = pat_run_n.plot(x='simulation arrival day', y='time in ED',
                   title='Average Time in ED until DTA by Simulation Day', xlabel='day',
                   ylabel='average time(minutes)')
    fig = ax.get_figure()
    fig.savefig(f'Run {run} Average Time in ED until DTA by Simulation Day.png')
    #Time spent in MAU queue
    ax = pat_run_n.plot(x='simulation arrival day', y='time in MAU queue',
                   title='Average Time in MAU queue by Simulation Day', xlabel='day',
                   ylabel='average time(minutes)')
    fig = ax.get_figure()
    fig.savefig(f'Run {run} Average Time in MAU queue by Simulation Day.png')
    #Time spent in MAU
    ax = pat_run_n.plot(x='simulation arrival day', y='time in MAU',
                   title='Average Time in MAU by Simulation Day', xlabel='day',
                   ylabel='average time(minutes)')
    fig = ax.get_figure()
    fig.savefig(f'Run {run} Average Time in MAU by Simulation Day.png')
    #Average MAU queue at time of joining averaged by simulation day
    ax = pat_run_n.plot(x='simulation arrival day', y='MAU occ when queue joined',
                   title='MAU Occupancy when Queue Joined by Simulation Day', xlabel='day',
                   ylabel='Beds Occupied')
    fig = ax.get_figure()
    fig.savefig(f'Run {run} MAU Occupancy when Queue Joined by Simulation Day.png')


#Average across all runs
av_occ = occ_df.loc[(occ_df['time'] > 0)].copy().groupby('time', as_index=False).mean(numeric_only=True).sort_values(by='time')
av_pat = (patient_df.loc[(patient_df['simulation arrival time'] > 0)].copy().groupby('simulation arrival day', as_index=False)
          .mean(numeric_only=True).sort_values(by='simulation arrival day'))

#Average bed occupancy by time
ax = av_occ.plot(x='time', y='MAU beds occupied', title='Average MAU Bed Occupancy',
                xlabel='time (minutes)', ylabel='Number of Beds Occupied')
fig = ax.get_figure()
fig.savefig('Average MAU Bed Occupancy.png')
#ED Occupancy
ax = av_occ.plot(x='time', y='ED Occupancy', title='ED Occupancy',
                xlabel='time', ylabel='patients')
fig = ax.get_figure()
fig.savefig('Average ED Occupancy.png')
#Number of patients in MAU Queue
ax = av_occ.plot(x='time', y='MAU queue length', title='MAU Queue',
       xlabel='time (minutes)', ylabel='Number of Patients in Queue')
fig = ax.get_figure()
fig.savefig('Average Number of patients in MAU Queue.png')

#Time spent in ED
ax = av_pat.plot(x='simulation arrival day', y='time in ED',
                title='Average Time in ED until DTA by Simulation Day', xlabel='day',
                ylabel='average time(minutes)')
fig = ax.get_figure()
fig.savefig('Average Time in ED until DTA by Simulation Day.png')
#Time spent in MAU queue
ax = av_pat.plot(x='simulation arrival day', y='time in MAU queue',
                   title='Average Time in MAU queue by Simulation Day', xlabel='day',
                   ylabel='average time(minutes)')
fig = ax.get_figure()
fig.savefig('Average Time in MAU queue by Simulation Day.png')
#Time spent in MAU
ax = av_pat.plot(x='simulation arrival day', y='time in MAU',
                   title='Average Time in MAU by Simulation Day', xlabel='day',
                   ylabel='average time(minutes)')
fig = ax.get_figure()
fig.savefig('Average Time in MAU by Simulation Day.png')
#Average MAU queue at time of joining averaged by simulation day
ax = av_pat.plot(x='simulation arrival day', y='MAU occ when queue joined',
                   title='MAU Occupancy when Queue Joined by Simulation Day', xlabel='day',
                   ylabel='Beds Occupied')
fig = ax.get_figure()
fig.savefig('Average MAU Occupancy when Queue Joined by Simulation Day.png')





(patient_df.dropna(subset='time in MAU queue').groupby('simulation arrival day', as_index=False)
 ['time in MAU queue'].mean().sort_values(by='simulation arrival day')
 .plot(x='simulation arrival day', y='time in MAU queue', title='Average wait to enter MAU by simulation day',
       ylabel='time (minutes)'))
