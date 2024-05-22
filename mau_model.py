import os
import simpy
import random
import pandas as pd
import numpy as np
os.chdir('C:/Users/obriene/Projects/MAU_model/outputs')

class params():
    warm_up = 30
    run_time = 2400
    iterations = 10
    no_mau_beds = 52
    results = []

class spawn_patient:
    def __init__(self, p_id):
        #set up patient id
        self.id = p_id

class mau_model:
    def __init__(self, run_number):
        #start environment and set patient counter to 0 and set run number
        self.env = simpy.Environment()
        self.patient_counter = 0
        self.run_number = run_number
        #establish resources
        self.mau_bed = simpy.Resource(self.env, capacity=params.no_mau_beds)

    def generate_ed_arrivals(self):
        while True:
            #up patient counter and spawn a new patient
            self.patient_counter += 1
            p = spawn_patient(self.patient_counter)
            #begin patient ed process
            self.env.process(self.mau_journey(p))
            #randomly sample the time until the next patient arrival
            sampled_interarrival = random.expovariate(1.0 / params.mean_inter_arr)
            yield self.env.timeout(sampled_interarrival)
        
    def mau_journey(self, patient):
        patient.start_time = self.env.now

        #If past the warm up period, start recoring results
        if self.env.now > params.warm_up:
            self.store_patient_results(patient)

    #Save patients results in a list to turn into a dataframe later
    def store_patient_results(self, patient):
        params.results.append([])

    def run(self):
        #Run process for the run time specified
        self.env.process(self.generate_ed_arrivals())
        self.env.run(until=(params.warm_up + params.run_time))

class run_the_model:
    #run the model for the number of iterations specified
    for run in range(params.iterations):
        print(f"Run {run+1} of {params.iterations}")
        model = mau_model(run)
        model.run()

    #put full results into a dataframe and export to csv
    df = pd.DataFrame(params.results,
                      columns= [])
    df.to_csv('mau results.csv', index=False)
