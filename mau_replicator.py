from mau_model import mau_model
from mau_model import transform_inputs
from mau_model import export_results
from joblib import Parallel, delayed
from concurrent.futures import ProcessPoolExecutor, as_completed
from stqdm import stqdm

class Replicator:
    def __init__(self, inputs, replications):
        #set up the number of runs and the inputs
        self.replications = replications
        self.inputs = inputs
        # Set up DataFrames for all trials results
        self.patient_res = []
        self.occupation_res = []
        
#    def run_trial(self, inputs):
 #       print('running through replicator')
        #Runs trial of a single scenario over multiple CPU cores.
        #n_jobs = max cores to use; use -1 for all available cores.
        # Use of  `delayed` ensures different random  numbers in each run
  #      trial_output = Parallel(n_jobs=-1)(delayed(self.single_run)(inputs, i) 
   #             for i in range(self.replications))
    #    return trial_output
    
    def run_trial(self, inputs):
        with ProcessPoolExecutor() as executor:
            futures = [executor.submit(self.single_run, inputs, run)
                       for run in range(inputs.iterations)]
            for future in as_completed(futures):
                pat_res, occ_res = future.result()
                self.patient_res += pat_res
                self.occupation_res += occ_res
                
    def single_run(self, inputs, i=0):
        print(f'single run {i}')
        #Performs a single run of the model and returns a dictionary contianing
        #the two results tables
        model = mau_model(i, inputs)
        model.run()
        #Return the results from the run
        pat_results = model.patient_results
        occ_results = model.mau_occupancy_results
        return [pat_results, occ_results]
    
    def run_scenarios(self):

        #transform mean and std inputs with user inputs
        transform_inputs(self.inputs)
        # Call for all replications of a single scenario to be run
    #    scenario_output = self.run_trial(self.inputs)
        self.run_trial(self.inputs)

        #combine the results of all the runs
#        pat_res = []
 #       occ_res = []
  #      for run in range(self.replications):
            #Get results for that run
   #         run_output = scenario_output[run]
            #Add patient results to the patient list
    #        result_pat = run_output[0]
     #       pat_res += result_pat
            #Add occupation results to occupation list
      #      result_occ = run_output[1]
       #     occ_res += result_occ
        #Convert results into output dataframes
        patient_res, occ_res = export_results(self.inputs.run_days,
                                              self.patient_res,
                                              self.occupation_res)
        return patient_res, occ_res

if __name__ == '__main__':
    Replicator()