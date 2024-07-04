import os
from datetime import datetime
os.chdir('C:/Users/obriene/Projects/MAU model')
from mau_model import default_params
from mau_model import run_the_model

inputs = default_params()
#List of commented out parameters that could be changed
inputs.scenario_name = 'Baseline 2'
    #run times and iterations
#inputs.run_time = 525600
inputs.iterations = 1
    #inter arrival times
#inputs.mean_amb_arr = 18
#inputs.mean_wlkin_arr = 7
#inputs.mean_other_mau_arr = 751
    #times of processes
#inputs.mau_bed_downtime = 59
#inputs.mean_ed = 283
#inputs.mean_move = 23
#inputs.mean_mau = 1784
    #resources
#inputs.no_mau_beds = 52
    #split probabilities
#inputs.ed_disc_prob = 0.64
#inputs.dta_admit_elsewhere_prob = 0.67
#inputs.mau_disc_prob = 0.2

#Create folders for outputs, do data processing and write to csv
#Create folder for today's runs
date_folder = (f'C:/Users/obriene/Projects/MAU model/outputs'
               f'/{datetime.today().strftime('%Y-%m-%d')}')
if not os.path.exists(date_folder):
    os.makedirs(date_folder)
os.chdir(date_folder)

#Create output folder (if doesn't exist) and navigate to it
scenario_folder = inputs.scenario_name
if not os.path.exists(scenario_folder):
    os.makedirs(scenario_folder)
os.chdir(scenario_folder)

pat, occ = run_the_model(inputs)

pat.to_csv('mau patients.csv', index=False)
occ.to_csv('mau occupancy.csv', index=False)