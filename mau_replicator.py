from mau_model import mau_model
from mau_model import transform_inputs
from mau_model import export_results
from concurrent.futures import ProcessPoolExecutor, as_completed

class Replicator:
    def __init__(self, inputs, replications):
        #set up the number of runs and the inputs
        self.replications = replications
        self.inputs = inputs
        # Set up DataFrames for all trials results
        self.patient_res = []
        self.occupation_res = []

    def run_trial(self, inputs):
        with ProcessPoolExecutor(max_workers=4) as executor:
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

    def run_scenarios(_self):
        #transform mean and std inputs with user inputs
        transform_inputs(_self.inputs)
        # Call for all replications of a single scenario to be run
        _self.run_trial(_self.inputs)
        patient_res, occ_res = export_results(_self.inputs.run_days,
                                              _self.patient_res,
                                              _self.occupation_res)
        return patient_res, occ_res