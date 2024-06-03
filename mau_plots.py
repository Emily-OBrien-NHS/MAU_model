import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

os.chdir('C:/Users/obriene/Projects/MAU model/outputs')

scenario_name = 'Double MAU LoS'
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
    ax1 = run_n.plot(x='time', y='MAU beds occupied', title='MAU Beds Occupancy',
            xlabel='time (minutes)', ylabel='Beds Occupied')
    fig1 = ax1.get_figure()
    fig1.savefig(f'Run {run} MAU Bed Occupancy.png')
    plt.close(fig1)
    #ED Occupancy
    ax2 = run_n.plot(x='time', y='ED Occupancy', title='ED Occupancy',
            xlabel='time (minutes)', ylabel='patients')
    fig2 = ax2.get_figure()
    fig2.savefig(f'Run {run} ED Occupancy.png')
    plt.close(fig2)
    #Number of patients in MAU Queue
    ax3 = run_n.plot(x='time', y='MAU queue length', title='MAU Queue',
            xlabel='time (minutes)', ylabel='Number of Patients in Queue')
    fig3 = ax3.get_figure()
    fig3.savefig(f'Run {run} Number of patients in MAU Queue.png')
    plt.close(fig3)

    #filter the patient data
    pat_run_n = (patient_df[(patient_df['run'] == run) & (patient_df['patient ID'] > 0)].copy()
                 .groupby('simulation arrival day', as_index=False).mean(numeric_only=True))
    
    #Time spent in ED
    ax4 = pat_run_n.plot(x='simulation arrival day', y='time in ED',
                   title='Average Time in ED until DTA by Simulation Day', xlabel='day',
                   ylabel='average time(minutes)')
    fig4 = ax4.get_figure()
    fig4.savefig(f'Run {run} Average Time in ED until DTA by Simulation Day.png')
    plt.close(fig4)
    #Time spent in MAU queue
    ax5 = pat_run_n.plot(x='simulation arrival day', y='time in MAU queue',
                   title='Average Time in MAU queue by Simulation Day', xlabel='day',
                   ylabel='average time(minutes)')
    fig5 = ax5.get_figure()
    fig5.savefig(f'Run {run} Average Time in MAU queue by Simulation Day.png')
    plt.close(fig5)
    #Time spent in MAU
    ax6 = pat_run_n.plot(x='simulation arrival day', y='time in MAU',
                   title='Average Time in MAU by Simulation Day', xlabel='day',
                   ylabel='average time(minutes)')
    fig6 = ax6.get_figure()
    fig6.savefig(f'Run {run} Average Time in MAU by Simulation Day.png')
    plt.close(fig6)
    #Average MAU queue at time of joining averaged by simulation day
    ax7 = pat_run_n.plot(x='simulation arrival day', y='MAU occ when queue joined',
                   title='MAU Occupancy when Queue Joined by Simulation Day', xlabel='day',
                   ylabel='Beds Occupied')
    fig7 = ax7.get_figure()
    fig7.savefig(f'Run {run} MAU Occupancy when Queue Joined by Simulation Day.png')
    plt.close(fig7)
    #frequency plot of MAU wait times
    ax8 = pat_run_n['time in MAU queue'].dropna().plot.hist(bins=25)
    fig8 = ax8.get_figure()
    ax8.set_title('Distribution of time spent in MAU queue')
    ax8.set_xlabel('Time in MAU queue')
    fig8.savefig(f'Run {run} Distribution of MAU Wait Times.png')
    plt.close(fig8)

#Average across all runs
av_occ = occ_df.loc[(occ_df['time'] > 0)].copy().groupby('time', as_index=False).mean(numeric_only=True).sort_values(by='time')
av_pat = (patient_df.loc[(patient_df['simulation arrival time'] > 0)].copy().groupby('simulation arrival day', as_index=False)
          .mean(numeric_only=True).sort_values(by='simulation arrival day'))

#Average bed occupancy by time
ax9 = av_occ.plot(x='time', y='MAU beds occupied', title='Average MAU Bed Occupancy',
                xlabel='time (minutes)', ylabel='Number of Beds Occupied')
fig9 = ax9.get_figure()
fig9.savefig('Average MAU Bed Occupancy.png')
plt.close(fig9)
#ED Occupancy
ax10 = av_occ.plot(x='time', y='ED Occupancy', title='ED Occupancy',
                xlabel='time', ylabel='patients')
fig10 = ax10.get_figure()
fig10.savefig('Average ED Occupancy.png')
plt.close(fig10)
#Number of patients in MAU Queue
ax11 = av_occ.plot(x='time', y='MAU queue length', title='MAU Queue',
       xlabel='time (minutes)', ylabel='Number of Patients in Queue')
fig11 = ax11.get_figure()
fig11.savefig('Average Number of patients in MAU Queue.png')
plt.close(fig11)
#Time spent in ED
ax12 = av_pat.plot(x='simulation arrival day', y='time in ED',
                title='Average Time in ED until DTA by Simulation Day', xlabel='day',
                ylabel='average time(minutes)')
fig12 = ax12.get_figure()
fig12.savefig('Average Time in ED until DTA by Simulation Day.png')
plt.close(fig12)
#Time spent in MAU queue
ax13 = av_pat.plot(x='simulation arrival day', y='time in MAU queue',
                   title='Average Time in MAU queue by Simulation Day', xlabel='day',
                   ylabel='average time(minutes)')
fig13 = ax13.get_figure()
fig13.savefig('Average Time in MAU queue by Simulation Day.png')
plt.close(fig13)
#Time spent in MAU
ax14 = av_pat.plot(x='simulation arrival day', y='time in MAU',
                   title='Average Time in MAU by Simulation Day', xlabel='day',
                   ylabel='average time(minutes)')
fig14 = ax14.get_figure()
fig14.savefig('Average Time in MAU by Simulation Day.png')
plt.close(fig14)
#Average MAU queue at time of joining averaged by simulation day
ax15 = av_pat.plot(x='simulation arrival day', y='MAU occ when queue joined',
                   title='MAU Occupancy when Queue Joined by Simulation Day', xlabel='day',
                   ylabel='Beds Occupied')
fig15 = ax15.get_figure()
fig15.savefig('Average MAU Occupancy when Queue Joined by Simulation Day.png')
plt.close(fig15)

#frequency plot of MAU wait times
ax16 = patient_df['time in MAU queue'].dropna().plot.hist(bins=25)
fig16 = ax16.get_figure()
ax16.set_title('Distribution of time spent in MAU queue')
ax16.set_xlabel('Time in MAU queue')
fig16.savefig('Distribution of MAU wait times.png')

#Calculate averages and save as csv
patient_averages = (patient_df.groupby('run').mean(numeric_only=True)
                    ._append(patient_df.mean(numeric_only=True).rename('average'))
                    [['time in ED', 'time in MAU queue', 'MAU occ when queue joined', 'time in MAU']])
occ_averages = (occ_df.groupby('run').mean(numeric_only=True)
                ._append(occ_df.mean(numeric_only=True).rename('average'))
                [['MAU beds occupied', 'MAU queue length', 'ED Occupancy']])
patient_averages.join(occ_averages).to_csv('Averages.csv')
