import os
import simpy
import random
import pandas as pd
import numpy as np
os.chdir('C:/Users/obriene/Projects/MAU model/outputs')

class params():
    scenario_name = 'baseline'
    #run times and iterations
    warm_up = 0
    run_time = 525600
    iterations = 1
    #times of processes
    mean_amb_arr = 18
    mean_walk_arr = 7
    mean_ed = 283
    mean_mau = 1784
    #resources
    no_mau_beds = 52
    #split probabilities
    ed_disc_prob = 0.64
    dta_admit_elsewhere_prob = 0.67
    mau_disc_prob = 0.2
    #empty list for results
    results = []

class spawn_patient:
    def __init__(self, p_id, eu_disc_prob, dta_admit_elsewhere_prob, mau_disc_prob):
        #set up patient id and arrival type
        self.id = p_id
        self.arrival = ''

        #work out probabilities of patient following each path
        #Does patient get discharged from ED
        self.decide_ed_disc_prob = random.uniform(0,1)
        self.ed_disc = True if self.decide_ed_disc_prob <= eu_disc_prob else False
        #Does patient get admitted to MAU
        self.decide_mau_adm_prob = random.uniform(0,1)
        self.dta_admit_elsewhere = True if self.decide_mau_adm_prob <= dta_admit_elsewhere_prob else False
        #Does patient get discharged from MAU
        self.decide_mau_disc_prob = random.uniform(0,1)
        self.mau_disc = True if self.decide_mau_disc_prob <= mau_disc_prob else False
        
        #Establish variables to store results
        self.ed_arrival_time = np.nan
        self.ed_leave_time = np.nan
        self.enter_mau_queue = np.nan
        self.leave_mau_queue = np.nan
        self.leave_mau = np.nan
        self.note = ''


class mau_model:
    def __init__(self, run_number):
        #start environment and set patient counter to 0 and set run number
        self.env = simpy.Environment()
        self.patient_counter = 0
        self.run_number = run_number
        #establish resources
        self.ed = simpy.Resource(self.env, capacity=100000000) 
        self.mau_bed = simpy.Resource(self.env, capacity=params.no_mau_beds)
        
    def generate_walkin_ed_arrivals(self):
        while True:
            #up patient counter and spawn a new patient
            self.patient_counter += 1
            p = spawn_patient(self.patient_counter, params.ed_disc_prob,
                              params.dta_admit_elsewhere_prob, params.mau_disc_prob)
            p.arrival = 'Walk-in'
            #begin patient ed process
            self.env.process(self.mau_journey(p))
            #randomly sample the time until the next patient arrival
            sampled_interarrival = random.expovariate(1.0 / params.mean_walk_arr)
            yield self.env.timeout(sampled_interarrival)
    
    def generate_ambulance_ed_arrivals(self):
        while True:
            #up patient counter and spawn a new patient
            self.patient_counter += 1
            p = spawn_patient(self.patient_counter, params.ed_disc_prob,
                              params.dta_admit_elsewhere_prob, params.mau_disc_prob)
            p.arrival = 'Ambulance'
            #begin patient ed process
            self.env.process(self.mau_journey(p))
            #randomly sample the time until the next patient arrival
            sampled_interarrival = random.expovariate(1.0 / params.mean_amb_arr)
            yield self.env.timeout(sampled_interarrival)
        
    def mau_journey(self, patient):

        patient.ed_arrival_time = self.env.now 

        #ED time
        with self.ed.request() as req:
            yield req
            #randomly sample the time spent in ED
            sampled_ed_time = random.expovariate(1.0 / params.mean_ed)
            yield self.env.timeout(sampled_ed_time)
        
        patient.ed_leave_time = self.env.now

        if patient.ed_disc:
            #patient discharged from ED and leaves the process
            patient.note = 'Discharged from ED'
        else:
            #Patient to be admitted somewhere else
            if patient.dta_admit_elsewhere:
                #Patient admitted elsewhere from dta and leaves the process
                patient.note = 'Admitted elsewhere'
            else:
                #Patient begins wait for mau bed
                patient.enter_mau_queue = self.env.now

                with self.mau_bed.request() as req:
                    yield req
                    #record how long the patient was in the MAU queue
                    patient.leave_mau_queue = self.env.now
                    #randomly sample the time spent in an MAU bed
                    sampled_mau_duration = random.expovariate(1.0 / params.mean_mau)
                    yield self.env.timeout(sampled_mau_duration)

                patient.leave_mau = self.env.now

                if patient.mau_disc:
                    #Patient discharged from MAU
                    patient.note = 'Discharged from MAU'
                else:
                    #Patient admitted to specialty ward
                    patient.note = 'Admitted to Specialty Ward'

        #If past the warm up period, start recoring results
        #if self.env.now > params.warm_up:
        self.store_patient_results(patient)

    #Save patients results in a list to turn into a dataframe later
    def store_patient_results(self, patient):
        params.results.append([self.run_number, patient.id, patient.arrival, patient.ed_arrival_time,
                               patient.ed_leave_time, patient.enter_mau_queue, patient.leave_mau_queue,
                               patient.leave_mau, patient.note])

    def run(self):
        #Run process for the run time specified
        self.env.process(self.generate_walkin_ed_arrivals())
        self.env.process(self.generate_ambulance_ed_arrivals())
        self.env.run(until=(params.warm_up + params.run_time))

class run_the_model:
    #run the model for the number of iterations specified
    for run in range(params.iterations):
        print(f"Run {run+1} of {params.iterations}")
        model = mau_model(run)
        model.run()

    #put full results into a dataframe and export to csv
    df = pd.DataFrame(params.results,
                      columns= ['run', 'patient id', 'ed arrival type', 'ed arrival time',
                                'ed leave time', 'enter mau queue', 'leave mau queue',
                                'leave mau', 'note']).sort_values(by='patient id')
    df.to_csv(params.scenario_name + ' mau results.csv', index=False)

#df['ED time'] = df['ed leave time'] - df['ed arrival time']
#df['MAU Queue'] = df['leave mau queue'] - df['enter mau queue']
