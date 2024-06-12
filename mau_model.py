import os
import math
import simpy
import random
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

os.chdir('C:/Users/obriene/Projects/MAU model/outputs')

class params():
    def log_normal_transform(mu, sigma):
        #function to take the mean and standard deviation of a series
        #and convert then into the mu and sigma inputes required
        #to use a log normal distribution for randomly generating
        #patient times.
        input_mu = np.log((mu**2) / ((mu**2 + sigma**2)**0.5))
        input_sigma = np.log(1 + (sigma**2 / mu**2))**0.5
        return input_mu, input_sigma

    scenario_name = 'Baseline'
    #run times and iterations
    run_time = 525600
    iterations = 1
    #times of processes
    mean_arr = pd.read_csv('C:/Users/obriene/Projects/MAU model/arrival distributions.csv')
    #mean_amb_arr = 18
    #mean_walk_arr = 7
    mean_other_mau_arr = 751
    mau_bed_downtime = 59
    mean_ed = 283
    std_ed = 246
    mu_ed, sigma_ed = log_normal_transform(mean_ed, std_ed)
    mean_mau = 1784
    std_mau = 2224
    mu_mau, sigma_mau = log_normal_transform(mean_mau, std_mau)
    #resources
    no_mau_beds = 52
    #Initial capacities
    init_ed_capacity = 80
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
        self.bed_downtime = np.nan
        self.note = ''

        self.mau_occ_when_queue_joined = np.nan

class mau_model:
    def __init__(self, run_number):
        #start environment and set patient counter to 0 and set run number
        self.env = simpy.Environment()
        self.patient_counter = 0
        self.run_number = run_number
        #Counters for initial filling of ED and MAU
        self.init_ed = 0
        self.init_bed = 0
        #establish resources
        self.ed = simpy.Resource(self.env, capacity=np.inf) 
        self.mau_bed = simpy.PriorityResource(self.env, capacity=params.no_mau_beds)

    ##################FILL ED AND MAU AT START OF RUN####################
    #ED
    def generate_initial_ed_patients(self):
        #request an MAU bed at time 0 until all mau beds are filled
        while self.init_ed < params.init_ed_capacity:
            fill_patient = spawn_patient(0, params.ed_disc_prob,
                                         params.dta_admit_elsewhere_prob,
                                         params.mau_disc_prob)
            fill_patient.arrival = 'ED filler patient'
            self.env.process(self.ed_to_mau_journey(fill_patient))
            self.init_ed += 1
            yield self.env.timeout(0)

    #MAU
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
            #randomly sample the time spent in an MAU bed, pause for that
            #plus twice the ED time, to allow a queue to build up before
            #initial patients start leaving.
            sampled_mau_duration = random.lognormvariate(params.mu_mau, params.sigma_mau)
            yield self.env.timeout((sampled_mau_duration + 2*params.mean_ed))
        patient.leave_mau = self.env.now
        patient.note = 'MAU filler patient'
        self.store_patient_results(patient)

    ########################ARRIVALS################################
    def generate_walkin_ed_arrivals(self):
        yield self.env.timeout(1)
        while True > 0:
            #Find out what the average walkin arrival time is for that time of day
            time_of_day = math.floor(self.env.now % (60*24) / 60)
            mean_walk_arr = (params.mean_arr['WlkinTimeBetweenArrivals'].to_numpy()
                            [params.mean_arr['ArrivalHour'] == time_of_day].item())
            #up patient counter and spawn a new patient
            self.patient_counter += 1
            p = spawn_patient(self.patient_counter, params.ed_disc_prob,
                              params.dta_admit_elsewhere_prob, params.mau_disc_prob)
            p.arrival = 'Walk-in'
            #begin patient ed process
            self.env.process(self.ed_to_mau_journey(p))
            #randomly sample the time until the next patient arrival
            sampled_interarrival = random.expovariate(1.0 / mean_walk_arr)
            yield self.env.timeout(sampled_interarrival)
    
    def generate_ambulance_ed_arrivals(self):
        yield self.env.timeout(1)
        while True > 0:
            #Find out what the average ambulance arrival time is for that time of day
            time_of_day = math.floor(self.env.now % (60*24) / 60)
            mean_amb_arr = (params.mean_arr['AmbTimeBetweenArrivals'].to_numpy()
                            [params.mean_arr['ArrivalHour'] == time_of_day].item())
            #up patient counter and spawn a new patient
            self.patient_counter += 1
            p = spawn_patient(self.patient_counter, params.ed_disc_prob,
                              params.dta_admit_elsewhere_prob, params.mau_disc_prob)
            p.arrival = 'Ambulance'
            #begin patient ed process
            self.env.process(self.ed_to_mau_journey(p))
            #randomly sample the time until the next patient arrival
            sampled_interarrival = random.expovariate(1.0 / mean_amb_arr)
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

    ##################ED TO MAU PROCESS #########################
    def ed_to_mau_journey(self, patient):
        #Patient comes into ed
        patient.ed_arrival_time = self.env.now 
        with self.ed.request() as req:
            yield req
            #randomly sample the time spent in ED
            sampled_ed_time = random.lognormvariate(params.mu_ed, params.sigma_ed)
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
                    #randomly sample the time spent in an MAU bed and the downtime
                    sampled_mau_duration = random.lognormvariate(params.mu_mau, params.sigma_mau)
                    sampled_bed_downtime = max(random.expovariate(1.0 / params.mau_bed_downtime), 30)
                    yield self.env.timeout(sampled_mau_duration +  sampled_bed_downtime)
                patient.bed_downtime = sampled_bed_downtime
                patient.leave_mau = self.env.now - sampled_bed_downtime

                #Record where the patient goes after MAU
                if patient.mau_disc:
                    patient.note = 'Discharged from MAU'
                else:
                    patient.note = 'Admitted to Specialty Ward'

        self.store_patient_results(patient)

    #####################DIRECT TO MAU PROCESS#############################
    def mau(self, patient):
        #Patient begins wait for mau bed
        patient.enter_mau_queue = self.env.now
        patient.mau_occ_when_queue_joined = self.mau_bed.count

        with self.mau_bed.request(priority=0) as req:
            yield req
            #record how long the patient was in the MAU queue
            patient.leave_mau_queue = self.env.now
            #randomly sample the time spent in an MAU bed
            sampled_mau_duration = (random.lognormvariate(params.mu_mau, params.sigma_mau)
                                    + params.mau_bed_downtime)
            #sampled_mau_duration = random.expovariate(1.0 / params.mean_mau)
            yield self.env.timeout(sampled_mau_duration)
        patient.leave_mau = self.env.now - params.mau_bed_downtime

        #Where does patient go on to from the MAU
        if patient.mau_disc:
            patient.note = 'Discharged from MAU'
            patient.split3 = 'Discharged'
        else:
            patient.note = 'Admitted to Specialty Ward'
            patient.split3 = 'Specialty Ward'

        self.store_patient_results(patient)
    
    ###################RECORD RESULTS####################
    def store_patient_results(self, patient):
        params.patient_results.append([self.run_number, patient.id, patient.arrival, patient.ed_arrival_time,
                               patient.ed_leave_time, patient.enter_mau_queue, patient.leave_mau_queue,
                               patient.leave_mau, patient.bed_downtime, patient.note, patient.mau_occ_when_queue_joined])
        
    def store_occupancy(self):
        while True:
            params.mau_occupancy_results.append([self.run_number, self.mau_bed._env.now,
                                                 self.mau_bed.count, len(self.mau_bed.queue),
                                                 self.ed.count])
            yield self.env.timeout(60)

    ########################RUN#######################
    def run(self):
        #Run process for the run time specified
        self.env.process(self.generate_initial_ed_patients())
        self.env.process(self.generate_initial_mau_patients())
        self.env.process(self.generate_walkin_ed_arrivals())
        self.env.process(self.generate_ambulance_ed_arrivals())
        self.env.process(self.generate_non_ed_mau_arrivals())
        self.env.process(self.store_occupancy())
        self.env.run(until=(params.run_time))

class run_the_model:
    #run the model for the number of iterations specified
    for run in range(params.iterations):
        print(f"Run {run+1} of {params.iterations}")
        model = mau_model(run)
        model.run()

    #put full results into a dataframe and export to csv
    patient_df = (pd.DataFrame(params.patient_results,
                              columns= ['run', 'patient ID', 'ED arrival type', 'ED arrival time',
                                        'ED leave time', 'enter MAU queue', 'leave MAU queue',
                                        'leave MAU', 'MAU bed downtime', 'note', 'MAU occ when queue joined'])
                                        .sort_values(by=['run', 'patient ID']))
    patient_df['simulation arrival time'] = patient_df['ED arrival time'].fillna(patient_df['enter MAU queue'])
    patient_df['simulation arrival day'] = pd.cut(patient_df['simulation arrival time'],
                                  bins=365, labels=np.linspace(1,365,365))
    patient_df['time in ED'] = patient_df['ED leave time'] - patient_df['ED arrival time']
    patient_df['time in MAU queue'] = patient_df['leave MAU queue'] - patient_df['enter MAU queue']
    patient_df['time in MAU'] = patient_df['leave MAU'] - patient_df['leave MAU queue']

    patient_df = patient_df[['run', 'patient ID', 'simulation arrival time', 'simulation arrival day', 'ED arrival type',
             'ED arrival time', 'ED leave time', 'time in ED', 'enter MAU queue', 'leave MAU queue',
             'time in MAU queue', 'MAU occ when queue joined', 'leave MAU', 'time in MAU', 'MAU bed downtime', 'note']].copy()
    #patient_df.to_csv(params.scenario_name + ' mau patients.csv', index=False)
    
    occ_df = pd.DataFrame(params.mau_occupancy_results,
                              columns=['run', 'time', 'MAU beds occupied', 'MAU queue length',
                                       'ED Occupancy'])
    occ_df['day'] = pd.cut(occ_df['time'], bins=365, labels=np.linspace(1,365,365))
   # occ_df.to_csv(params.scenario_name + ' mau occupancy.csv', index=False)

    x=5

#walkin = patient_df.loc[patient_df['ED arrival type'] == 'Ambulance'].copy()
#walkin['TimeBetweenArrivals'] = walkin['simulation arrival time'].shift(-1) - walkin['simulation arrival time']
#print(walkin['TimeBetweenArrivals'].mean())
