import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
os.chdir('C:/Users/obriene/Projects/MAU model/outputs')

#Select scario run to adjust MAU occupancy restricting wait times
run_date = '2024-07-02'
scenario_name = '1 Hour MAU Queue'

#If MAU_only is True then run capping only the MAU queue, if False
#caps the wait time for ED+MAU queue.
MAU_only = False
total_wait = 240

#Read in data
patient_df = pd.read_csv(f'{run_date}/{scenario_name}/mau patients.csv')
occ_df = pd.read_csv(f'{run_date}/{scenario_name}/mau occupancy.csv')

#Filter to just MAU instances
MAU_patients = patient_df.dropna(subset='leave MAU queue')
MAU_patients = MAU_patients.loc[MAU_patients['patient ID'] > 0,
                                ['run', 'patient ID', 'ED arrival time', 'time in ED', 'leave MAU queue',
                                 'time in MAU queue', 'time in MAU', 'leave MAU', 'MAU bed downtime']].copy()

if MAU_only:
    #Cap only the MAU Queue
    #Cap anyone waiting over the total_wait mins in the queue
    MAU_patients['Capped queue'] = MAU_patients['time in MAU queue'].clip(upper=total_wait)
    #Create their new admitted time if only waiting a maximum of 60 mins
    MAU_patients['NEW leave MAU queue'] = (MAU_patients['leave MAU queue'] - (MAU_patients['time in MAU queue'] - MAU_patients['Capped queue']))
else:
    #Cap ED to DTA time plus MAU Queue time
    MAU_patients['Capped ED Time'] = (MAU_patients['time in ED'] + MAU_patients['time in MAU queue']).clip(upper=total_wait)
    #Create their new admitted time if only waiting a maximum of 60 mins
    MAU_patients['NEW leave MAU queue'] = MAU_patients['ED arrival time'] + MAU_patients['Capped ED Time']

#Get the new time that their bed will be free
MAU_patients['NEW bed free'] = MAU_patients['NEW leave MAU queue'] + (MAU_patients['time in MAU'] + MAU_patients['MAU bed downtime'])
#add bed downtime back to the actual time the bed is in use, not the patient
MAU_patients['bed free'] = MAU_patients['leave MAU'] + MAU_patients['MAU bed downtime']
MAU_patients[['leave MAU queue', 'NEW leave MAU queue', 'bed free', 'NEW bed free']] = MAU_patients[['leave MAU queue', 'NEW leave MAU queue',
                                                                                                     'bed free', 'NEW bed free']].round()

#Group by each time to see how many new and actual admissions and leavers there are at each time.
act_MAU_adm_time = (MAU_patients.groupby(['run', 'leave MAU queue'], as_index=False)['patient ID'].count()
                    .rename(columns = {'leave MAU queue':'time', 'patient ID':'act MAU adm'}).astype(int))
new_MAU_adm_time = (MAU_patients.groupby(['run', 'NEW leave MAU queue'], as_index=False)['patient ID'].count()
                    .rename(columns = {'NEW leave MAU queue':'time', 'patient ID':'new MAU adm'}).astype(int))
act_MAU_leave_time = (MAU_patients.groupby(['run', 'bed free'], as_index=False)['patient ID'].count()
                      .rename(columns = {'bed free':'time', 'patient ID':'act MAU leave'}).astype(int))
new_MAU_leave_time = (MAU_patients.groupby(['run', 'NEW bed free'], as_index=False)['patient ID'].count()
                      .rename(columns = {'NEW bed free':'time', 'patient ID':'new MAU leave'}).astype(int))

#Merge together all the different admissions and leavers onto the occupancy data
occ_df = (occ_df.merge(act_MAU_adm_time, on=['run', 'time'], how='left')
          .merge(new_MAU_adm_time, on=['run', 'time'], how='left')
          .merge(act_MAU_leave_time, on=['run', 'time'], how='left')
          .merge(new_MAU_leave_time, on=['run', 'time'], how='left'))

#Work out what the MAU occupancy would be if everyone waits a maximum of
#inputted wait time
occ_df['change in MAU occ'] = ((-occ_df['act MAU adm'] + occ_df['new MAU adm'])
                               -(-occ_df['act MAU leave'] + occ_df['new MAU leave'])).fillna(0)
occ_df['MAU beds occupied'] = occ_df['MAU beds occupied'] + occ_df['change in MAU occ']

#Re-sample every 60 mins and resave the new outputs
occ_df.loc[(occ_df['time'] % 60 == 0),['run', 'time', 'MAU beds occupied', 'MAU queue length',
                                       'ED Occupancy','day']].to_csv(f'{run_date}/{scenario_name}/mau occupancy.csv')


