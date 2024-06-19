import os
os.chdir('C:/Users/obriene/Projects/MAU model')
from mau_model import default_params
from mau_model import mau_model
from mau_model import export_results
import numpy as np
import pandas as pd
import datetime
from joblib import Parallel, delayed
#from AcutePlusEDModel_streamlit import IPACS_Model

class Replicator:
    def __init__(self, inputs, replications):
        #set up the number of runs and the inputs
        self.replications = replications
        self.inputs = inputs
        # Set up DataFrames for all trials results
        self.patient_res = []
        self.occupation_res = []
        
    def run_trial(self, inputs):
        print('running through replicator')
        #Runs trial of a single scenario over multiple CPU cores.
        #n_jobs = max cores to use; use -1 for all available cores.
        # Use of  `delayed` ensures different random  numbers in each run
        trial_output = Parallel(n_jobs=-1)(delayed(self.single_run)(inputs, i) 
                for i in range(self.replications))
        return trial_output
    
    def single_run(self, inputs, i=0):
        print(f'single run {i}')
        #Performs a single run of the model and returns a dictionary contianing
        #the two results tables
        model = mau_model(i, inputs)
        model.run()
        # Put results in a dictionary
        results = {'patients': model.inputs.patient_results,
                   'Occupancy': model.mau_occupancy_results}
        return results

    def collate_trial_results(self, results):
        #Make a list of lists with all results
        for run in range(self.replications):
            #Patient summary
            result_pat = results[run]['patients']
            self.patient_res.append(result_pat)
            #result_item['run'] = run
            #self.patient = pd.concat([self.patient_res,result_item])
            
            #occupancy summary
            result_occ = results[run]['Occupancy']
            self.occupation_res.append(result_occ)
            #result_item['run'] = run
            #self.summary_ed = pd.concat([self.summary_ed,result_item])
            
            export_results(self.inputs.scenario_name, self.inputs.run_days,
                           result_pat, result_occ)
    
    def run_scenarios(self):
        #Runs each of the replications of the model, then calls to collate all
        #the data into one output
        
        # Call for all replications of a single scenario to be run
        scenario_output = self.run_trial(self.inputs)
        
        # Collate trial results into single DataFrame 
        patient_res, occ_res = self.collate_trial_results(scenario_output)
        #Aggregate the results over all of the replications and return the 
        #aggregated results
        return patient_res, occ_res
