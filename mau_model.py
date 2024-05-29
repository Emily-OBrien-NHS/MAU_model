import os
import simpy
import random
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

os.chdir('C:/Users/obriene/Projects/MAU model/outputs')

class params():
    scenario_name = 'baseline'
    #run times and iterations
    warm_up = 0
    run_time = 525600
    #run_time = 1000
    iterations = 1
    #times of processes
    mean_amb_arr = 18
    mean_walk_arr = 7
    mean_other_mau_arr = 751
    mean_ed = 283
    mean_mau = 1784
    #resources
    no_mau_beds = 52
    #split probabilities
    ed_disc_prob = 0.64
    dta_admit_elsewhere_prob = 0.67
    mau_disc_prob = 0.2
    #empty list for results
    patient_results = []
    mau_occupancy_results = []

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

        self.mau_occ_when_queue_joined = np.nan


class mau_model:
    def __init__(self, run_number):
        #start environment and set patient counter to 0 and set run number
        self.env = simpy.Environment()
        self.patient_counter = 0
        self.run_number = run_number
        self.init_bed = 0
        #establish resources
        self.ed = simpy.Resource(self.env, capacity=10000000000) 
        self.mau_bed = simpy.PriorityResource(self.env, capacity=params.no_mau_beds)

    ##################FILL MAU AT START OF RUN####################
    def generate_initial_mau_patients(self):
        #request an MAU bed at time 0 until all mau beds are filled
        while self.init_bed < params.no_mau_beds:
            fill_patient = spawn_patient(0, 0, 0, 0)
            self.env.process(self.fill_mau(fill_patient))
            self.init_bed += 1
            yield self.env.timeout(0)

    def fill_mau(self, patient):
        patient.enter_mau_queue = self.env.now
        patient.mau_occ_when_queue_joined = self.mau_bed.count
        #request MAU bed to fill it
        with self.mau_bed.request(priority=-1) as req:
            yield req
            patient.leave_mau_queue = self.env.now
            #randomly sample the time spent in an MAU bed
            sampled_mau_duration = random.expovariate(1.0 / params.mean_mau)
            yield self.env.timeout(sampled_mau_duration)
        patient.leave_mau = self.env.now
        patient.note = 'filler patient'
        self.store_patient_results(patient)

    ##########ARRIVALS##########
    def generate_walkin_ed_arrivals(self):
        yield self.env.timeout(1)
        while True:
            #up patient counter and spawn a new patient
            self.patient_counter += 1
            p = spawn_patient(self.patient_counter, params.ed_disc_prob,
                              params.dta_admit_elsewhere_prob, params.mau_disc_prob)
            p.arrival = 'Walk-in'
            #begin patient ed process
            self.env.process(self.ed_to_mau_journey(p))
            #randomly sample the time until the next patient arrival
            sampled_interarrival = random.expovariate(1.0 / params.mean_walk_arr)
            yield self.env.timeout(sampled_interarrival)
    
    def generate_ambulance_ed_arrivals(self):
        yield self.env.timeout(1)
        while True > 0:
            #up patient counter and spawn a new patient
            self.patient_counter += 1
            p = spawn_patient(self.patient_counter, params.ed_disc_prob,
                              params.dta_admit_elsewhere_prob, params.mau_disc_prob)
            p.arrival = 'Ambulance'
            #begin patient ed process
            self.env.process(self.ed_to_mau_journey(p))
            #randomly sample the time until the next patient arrival
            sampled_interarrival = random.expovariate(1.0 / params.mean_amb_arr)
            yield self.env.timeout(sampled_interarrival)

    def generate_non_ed_mau_arrivals(self):
            yield self.env.timeout(1)
            while True > 0:
                #up patient counter and spawn a new patient
                self.patient_counter += 1
                p = spawn_patient(self.patient_counter, params.ed_disc_prob,
                                params.dta_admit_elsewhere_prob, params.mau_disc_prob)
                p.arrival = 'Non-ED MAU Admission'
                #begin patient ed process
                self.env.process(self.mau(p))
                #randomly sample the time until the next patient arrival
                sampled_interarrival = random.expovariate(1.0 / params.mean_other_mau_arr)
                yield self.env.timeout(sampled_interarrival)

    #####################MAU PROCESS#######################################
    def mau(self, patient):
        #Patient begins wait for mau bed
        patient.enter_mau_queue = self.env.now
        patient.mau_occ_when_queue_joined = self.mau_bed.count

        with self.mau_bed.request(priority=0) as req:
            yield req
            #record how long the patient was in the MAU queue
            patient.leave_mau_queue = self.env.now
            #randomly sample the time spent in an MAU bed
            sampled_mau_duration = random.expovariate(1.0 / params.mean_mau)
            yield self.env.timeout(sampled_mau_duration)
        patient.leave_mau = self.env.now

        #Where does patient go on to from the MAU
        if patient.mau_disc:
            patient.note = 'Discharged from MAU'
        else:
            patient.note = 'Admitted to Specialty Ward'

        self.store_patient_results(patient)

    ##################ED TO MAU PROCESS #########################
    def ed_to_mau_journey(self, patient):
        #Patient comes into ed
        patient.ed_arrival_time = self.env.now 
        with self.ed.request() as req:
            yield req
            #randomly sample the time spent in ED
            sampled_ed_time = random.expovariate(1.0 / params.mean_ed)
            yield self.env.timeout(sampled_ed_time)
        patient.ed_leave_time = self.env.now

        #Decide if patient is discharged from ED, or admitted
        if patient.ed_disc:
            patient.note = 'Discharged from ED'
        else:
            #If patient is admitted, are they admited to MAU or elsewhere
            if patient.dta_admit_elsewhere:
                patient.note = 'Admitted elsewhere'
            else:
                #Patient begins wait for mau bed
                patient.enter_mau_queue = self.env.now
                patient.mau_occ_when_queue_joined = self.mau_bed.count

                with self.mau_bed.request(priority=0) as req:
                    yield req
                    #record how long the patient was in the MAU queue
                    patient.leave_mau_queue = self.env.now
                    #randomly sample the time spent in an MAU bed
                    sampled_mau_duration = random.expovariate(1.0 / params.mean_mau)
                    yield self.env.timeout(sampled_mau_duration)
                
                patient.leave_mau = self.env.now
                #Record where the patient goes after MAU
                if patient.mau_disc:
                    patient.note = 'Discharged from MAU'
                else:
                    patient.note = 'Admitted to Specialty Ward'

        self.store_patient_results(patient)
    
    ###################RECORD RESULTS####################
    def store_patient_results(self, patient):
        params.patient_results.append([self.run_number, patient.id, patient.arrival, patient.ed_arrival_time,
                               patient.ed_leave_time, patient.enter_mau_queue, patient.leave_mau_queue,
                               patient.leave_mau, patient.note, patient.mau_occ_when_queue_joined])
        
    def store_mau_occupancy(self):
        while True:
            params.mau_occupancy_results.append([self.run_number, self.mau_bed._env.now,
                                                 self.mau_bed.count, len(self.mau_bed.queue)])
            yield self.env.timeout(60)

    ########################RUN#######################
    def run(self):
        #Run process for the run time specified
        self.env.process(self.generate_initial_mau_patients())
        self.env.process(self.generate_walkin_ed_arrivals())
        self.env.process(self.generate_ambulance_ed_arrivals())
        self.env.process(self.generate_non_ed_mau_arrivals())
        self.env.process(self.store_mau_occupancy())
        self.env.run(until=(params.warm_up + params.run_time))

class run_the_model:
    #run the model for the number of iterations specified
    for run in range(params.iterations):
        print(f"Run {run+1} of {params.iterations}")
        model = mau_model(run)
        model.run()

    #put full results into a dataframe and export to csv
    df = pd.DataFrame(params.patient_results,
                      columns= ['run', 'patient ID', 'ED arrival type', 'ED arrival time',
                                'ED leave time', 'enter MAU queue', 'leave MAU queue',
                                'leave MAU', 'note', 'MAU occupancy when queue joined']).sort_values(by='patient ID')
    df['simulation arrival time'] = df['ED arrival time'].fillna(df['enter MAU queue'])
    df['simulation arrival day'] = pd.cut(df['simulation arrival time'],
                                  bins=365, labels=np.linspace(1,365,365))
    df['ED time'] = df['ED leave time'] - df['ED arrival time']
    df['MAU Queue'] = df['leave MAU queue'] - df['enter MAU queue']
    #df.to_csv('C:/Users/obriene/Projects/MAU model/outputs/' + params.scenario_name + ' mau patients.csv',
     #         index=False)
    
    mau_occ_df = pd.DataFrame(params.mau_occupancy_results,
                              columns=['run', 'time', 'beds occupied', 'queue length'])
  #  mau_occ_df.to_csv('C:/Users/obriene/Projects/MAU model/outputs/' + params.scenario_name + ' mau occupancy.csv',
   #           index=False)

#    x=5

    df.dropna(subset='MAU Queue').plot(x='simulation arrival day', y='MAU Queue', kind='scatter')
    mau_occ_df.plot(x='time', y='beds occupied')


    p = df[['patient ID', 'simulation arrival day', 'enter MAU queue', 'leave MAU queue',
        'leave MAU', 'MAU Queue', 'note']].copy()
    p = p.sort_values(by='enter MAU queue')
    p['diff in queue arr'] = abs(p['enter MAU queue'].shift(1) - p['enter MAU queue'])
    print(f'Average time between patients joining the MAU queue is {p['diff in queue arr'].mean():.2f} minutes')

    r = df[['patient ID', 'simulation arrival day', 'enter MAU queue', 'leave MAU queue',
        'leave MAU', 'MAU Queue', 'note']].copy()
    r = r.sort_values(by='leave MAU queue')
    r['diff in queue leave'] = abs(r['leave MAU queue'].shift(1) - r['leave MAU queue'])
    print(f'Average time between patients being admitted into the MAU is {r['diff in queue leave'].mean():.2f} minutes')

    q = df[['patient ID', 'simulation arrival day', 'enter MAU queue', 'leave MAU queue',
        'leave MAU', 'MAU Queue', 'note']].copy()
    q = q.sort_values(by='leave MAU')
    q['diff in MAU disc'] = abs(q['leave MAU'].shift(1) - q['leave MAU'])
    print(f'Average time between patients leaving the MAU {q['diff in MAU disc'].mean():.2f} minutes')


