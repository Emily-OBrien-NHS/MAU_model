import os
import math
import simpy
import random
import pandas as pd
import numpy as np
from datetime import datetime

class default_params():
    def multiply_scalars(df, col_name, mean):
        df[col_name] = df[col_name] * mean

    def log_normal_transform(mean_std):
        #function to take two columns of mean and standard deviation
        #and convert then into the mu and sigma inputes required
        #to use a log normal distribution for randomly generating
        #patient times.
        mu = mean_std.iloc[0]
        sigma = mean_std.iloc[1]
        input_mu = np.log((mu**2) / ((mu**2 + sigma**2)**0.5))
        input_sigma = np.log(1 + (sigma**2 / mu**2))**0.5
        return input_mu, input_sigma

    scenario_name = 'Baseline'
    #Time between ococupancy samples
    occ_sample_time = 60
    #run times and iterations
    run_time = 525600
    run_days = int(run_time/(60*24))
    iterations = 10
    #inter arrival times
    mean_amb_arr = 18
    mean_wlkin_arr = 7
    mean_other_mau_arr = 751
    #times of processes
    mau_bed_downtime = 59
    mean_ed = 283
    std_ed = 246
    mean_move = 23
    std_move = 12
    mean_mau = 1784
    std_mau = 2224

    #Multiply hourly scalars by averages
    hourly_scalars = pd.read_csv('C:/Users/obriene/Projects/MAU model'
                           '/hourly average scalars.csv')
    pairs = [('AmbTimeBetweenArrivals', mean_amb_arr),
             ('WlkinTimeBetweenArrivals',  mean_wlkin_arr),
             ('Non ED MAU Admissions', mean_other_mau_arr),
             ('mean ED LoS', mean_ed),
             ('std ED LoS', std_ed),
             ('mean move', mean_move),
             ('std move', std_move),
             ('mean MAU LoS', mean_mau),
             ('std MAU LoS', std_mau)]
    for col, av in pairs:
        multiply_scalars(hourly_scalars, col, av)

    #Transform log normal columns to the input mu and sigma
    log_pairs = [('mean ED LoS', 'std ED LoS'),
                 ('mean move', 'std move'),
                 ('mean MAU LoS', 'std MAU LoS')]
    for input_mean, input_std in log_pairs:
       hourly_scalars[[input_mean,
                       input_std]] = (hourly_scalars[[input_mean, input_std]]
                                      .apply(log_normal_transform, axis=1,
                                             result_type='expand'))
    #Get the initial mau times for filling mau at time 0
    init_mu_mau, init_sigma_mau = hourly_scalars.loc[0,
                                    ['mean MAU LoS', 'std MAU LoS']].tolist()
    #resources
    no_mau_beds = 52
    #Initial capacities
    init_ed_capacity = 80
    #split probabilities
    ed_disc_prob = 0.64
    dta_admit_elsewhere_prob = 0.67
    mau_disc_prob = 0.2
    #Get discharge specialty distributions
    dis_spec_prob = pd.read_csv('C:/Users/obriene/Projects/MAU model'
                                '/discharge specialties.csv')
    dis_spec = dis_spec_prob['local_spec_desc'].tolist()
    dis_prob = dis_spec_prob['count'].tolist()
    #empty list for results
    patient_results = []
    mau_occupancy_results = []

class spawn_patient:
    def __init__(self, p_id, eu_disc_prob, dta_admit_elsewhere_prob,
                 mau_disc_prob):
        #set up patient id and arrival type
        self.id = p_id
        self.arrival = ''

        #work out probabilities of patient following each path
        #Does patient get discharged from ED
        self.decide_ed_disc_prob = random.uniform(0,1)
        self.ed_disc = (True if self.decide_ed_disc_prob <= eu_disc_prob
                        else False)
        #Does patient get admitted to MAU
        self.decide_mau_adm_prob = random.uniform(0,1)
        self.dta_admit_elsewhere = (True if self.decide_mau_adm_prob
                                    <= dta_admit_elsewhere_prob else False)
        #Does patient get discharged from MAU
        self.decide_mau_disc_prob = random.uniform(0,1)
        self.mau_disc = (True if self.decide_mau_disc_prob <= mau_disc_prob
                         else False)
        
        #Establish variables to store results
        self.ed_arrival_time = np.nan
        self.ed_leave_time = np.nan
        self.enter_mau_queue = np.nan
        self.move_time = np.nan
        self.leave_mau_queue = np.nan
        self.leave_mau = np.nan
        self.bed_downtime = np.nan
        self.discharge_specialty = np.nan
        self.note = ''

        self.mau_occ_when_queue_joined = np.nan

class mau_model:
    def __init__(self, run_number, input_params):
        #start environment and set patient counter to 0 and set run number
        self.env = simpy.Environment()
        self.input_params = input_params
        self.patient_counter = 0
        self.run_number = run_number
        #Counters for initial filling of ED and MAU
        self.init_ed = 0
        self.init_bed = 0
        #establish resources
        self.ed = simpy.Resource(self.env, capacity=np.inf) 
        self.mau_bed = simpy.PriorityResource(self.env,
                                              capacity=input_params.no_mau_beds)

    ##################FILL ED AND MAU AT START OF RUN####################
    #ED
    def generate_initial_ed_patients(self):
        #request an MAU bed at time 0 until all mau beds are filled
        while self.init_ed < self.input_params.init_ed_capacity:
            fill_patient = spawn_patient(0, self.input_params.ed_disc_prob,
                                    self.input_params.dta_admit_elsewhere_prob,
                                    self.input_params.mau_disc_prob)
            fill_patient.arrival = 'ED filler patient'
            self.env.process(self.ed_to_mau_journey(fill_patient))
            self.init_ed += 1
            yield self.env.timeout(0)

    #MAU
    def generate_initial_mau_patients(self):
        #request an MAU bed at time 0 until all mau beds are filled
        while self.init_bed < self.input_params.no_mau_beds:
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
            sampled_mau_duration = random.lognormvariate(
                self.input_params.init_mu_mau, self.input_params.init_sigma_mau)
            yield self.env.timeout((sampled_mau_duration
                                    + 2*self.input_params.mean_ed))
        patient.leave_mau = self.env.now
        patient.note = 'MAU filler patient'
        self.store_patient_results(patient)

    ########################ARRIVALS################################
    def generate_walkin_ed_arrivals(self):
        yield self.env.timeout(1)
        while True > 0:
            #Calculate the current time of day in the simulation, and look up
            #the average walkin arrival for that time of day
            time_of_day = math.floor(self.env.now % (60*24) / 60)
            mean_walk_arr = (self.input_params
                             .hourly_scalars['WlkinTimeBetweenArrivals']
                             .to_numpy()
                             [self.input_params
                              .hourly_scalars['ArrivalHour'].to_numpy()
                              == time_of_day].item())
            #up patient counter and spawn a new walk-in patient
            self.patient_counter += 1
            p = spawn_patient(self.patient_counter,
                              self.input_params.ed_disc_prob,
                              self.input_params.dta_admit_elsewhere_prob,
                              self.input_params.mau_disc_prob)
            p.arrival = 'Walk-in'
            #begin patient ED process
            self.env.process(self.ed_to_mau_journey(p))
            #randomly sample the time until the next patient arrival
            sampled_interarrival = random.expovariate(1.0 / mean_walk_arr)
            yield self.env.timeout(sampled_interarrival)
    
    def generate_ambulance_ed_arrivals(self):
        yield self.env.timeout(1)
        while True > 0:
            #Calculate the current time of day in the simulation, and look up
            #the average ambulance arrival for that time of day
            time_of_day = math.floor(self.env.now % (60*24) / 60)
            mean_amb_arr = (self.input_params
                            .hourly_scalars['AmbTimeBetweenArrivals'].to_numpy()
                            [self.input_params
                             .hourly_scalars['ArrivalHour'].to_numpy()
                             == time_of_day].item())
            #up patient counter and spawn a new ambulance patient
            self.patient_counter += 1
            p = spawn_patient(self.patient_counter,
                              self.input_params.ed_disc_prob,
                              self.input_params.dta_admit_elsewhere_prob,
                              self.input_params.mau_disc_prob)
            p.arrival = 'Ambulance'
            #begin patient ed process
            self.env.process(self.ed_to_mau_journey(p))
            #randomly sample the time until the next patient arrival
            sampled_interarrival = random.expovariate(1.0 / mean_amb_arr)
            yield self.env.timeout(sampled_interarrival)

    def generate_non_ed_mau_arrivals(self):
            yield self.env.timeout(1)
            while True > 0:
                #Calculate the current time of day in the simulation, and look
                #up the average non ed arrival for that time of day
                time_of_day = math.floor(self.env.now % (60*24) / 60)
                mean_non_ed_arr = (self.input_params
                                   .hourly_scalars['Non ED MAU Admissions']
                                   .to_numpy()
                                   [self.input_params
                                    .hourly_scalars['ArrivalHour']
                                    == time_of_day].item())
                
                #up patient counter and spawn a new patient
                self.patient_counter += 1
                p = spawn_patient(self.patient_counter,
                                  self.input_params.ed_disc_prob,
                                self.input_params.dta_admit_elsewhere_prob,
                                self.input_params.mau_disc_prob)
                p.arrival = 'Non-ED MAU Admission'
                #begin patient ed process
                self.env.process(self.mau(p))
                #randomly sample the time until the next patient arrival
                sampled_interarrival = random.expovariate(1.0 / mean_non_ed_arr)
                yield self.env.timeout(sampled_interarrival)

    ##################ED TO MAU PROCESS #########################
    def ed_to_mau_journey(self, patient):
        #Patient comes into ed
        patient.ed_arrival_time = self.env.now 
        with self.ed.request() as req:
            yield req
            #randomly sample the time spent in ED from the average for the time
            #of day
            time_of_day = math.floor(self.env.now % (60*24) / 60)
            hour_mask = (self.input_params.hourly_scalars['ArrivalHour']
                             == time_of_day)
            mu_ed_time = (self.input_params
                          .hourly_scalars['mean ED LoS'].to_numpy()
                          [hour_mask].item())
            sigma_ed_time = (self.input_params
                             .hourly_scalars['std ED LoS'].to_numpy()
                             [hour_mask].item())
            sampled_ed_time = random.lognormvariate(mu_ed_time, sigma_ed_time)
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
                    #randomly sample the time to move to MAU and the time spent
                    #in an MAU bed from the average for the time of day
                    time_of_day = math.floor(self.env.now % (60*24) / 60)
                    hour_mask = (self.input_params.hourly_scalars['ArrivalHour']
                                    == time_of_day)
                    #mau_time = (self.input_params.hourly_scalars[[
                     #   'mean move', 'std move', 'mean MAU LoS', 'std MAU LoS']]
                      #  .to_numpy())
                    #mu_sigma_mau_times = (mau_time[hour_mask][0])
                    mu_mau_time = (self.input_params
                                   .hourly_scalars['mean MAU LoS'].to_numpy()
                                   [hour_mask].item())
                    sigma_mau_time = (self.input_params
                                      .hourly_scalars['std MAU LoS'].to_numpy()
                                      [hour_mask].item())
                    mu_mau_move_time = (self.input_params
                                        .hourly_scalars['mean move'].to_numpy()
                                        [hour_mask].item())
                    sigma_mau_move_time = (self.input_params
                                        .hourly_scalars['std move'].to_numpy()
                                        [hour_mask].item())
            
                    sampled_pat_move_duration = max(random.lognormvariate(
                                                mu_mau_time, sigma_mau_time), 5)
                    sampled_mau_duration = random.lognormvariate(
                                                    mu_mau_move_time,
                                                    sigma_mau_move_time)
                    #randomly sample bed downtime
                    sampled_bed_downtime = max(random.expovariate(1.0
                                        / self.input_params.mau_bed_downtime),
                                        30)
                    yield self.env.timeout(sampled_pat_move_duration
                                           + sampled_mau_duration
                                           +  sampled_bed_downtime)
                #Record patient MAU stay data
                patient.move_time = sampled_pat_move_duration
                patient.bed_downtime = sampled_bed_downtime
                patient.leave_mau = (self.env.now
                                     - sampled_bed_downtime
                                     - sampled_pat_move_duration)

                #Record where the patient goes after MAU
                if patient.mau_disc:
                    patient.note = 'Discharged from MAU'
                else:
                    patient.note = 'Admitted to Specialty Ward'
                    patient.discharge_specialty = random.choices(
                                                  self.input_params.dis_spec,
                                                  self.input_params.dis_prob)[0]

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
            #randomly sample the time to move to MAU and the time spent
            #in an MAU bed from the average for the time of day
            time_of_day = math.floor(self.env.now % (60*24) / 60)
            hour_mask = (self.input_params.hourly_scalars['ArrivalHour']
                            == time_of_day)
            #mau_time = (self.input_params.hourly_scalars[[
             #       'mean move', 'std move', 'mean MAU LoS', 'std MAU LoS']]
              #      .to_numpy())
            #mu_sigma_mau_times = (mau_time[hour_mask][0])
            mu_mau_time = (self.input_params
                           .hourly_scalars['mean MAU LoS'].to_numpy()
                           [hour_mask].item())
            sigma_mau_time = (self.input_params
                              .hourly_scalars['std MAU LoS'].to_numpy()
                              [hour_mask].item())
            mu_mau_move_time = (self.input_params
                                .hourly_scalars['mean move'].to_numpy()
                                [hour_mask].item())
            sigma_mau_move_time = (self.input_params
                                   .hourly_scalars['std move'].to_numpy()
                                   [hour_mask].item())
            
            sampled_pat_move_duration = max(random.lognormvariate(
                                                mu_mau_time, sigma_mau_time), 5)
            sampled_mau_duration = random.lognormvariate(
                                                    mu_mau_move_time,
                                                    sigma_mau_move_time)

            #randomly sample bed downtime
            sampled_bed_downtime = max(random.expovariate(1.0
                                    / self.input_params.mau_bed_downtime), 30)
            yield self.env.timeout(sampled_pat_move_duration
                                    + sampled_mau_duration
                                    +  sampled_bed_downtime)
            #Record patient MAU stay data
            patient.move_time = sampled_pat_move_duration
            patient.bed_downtime = sampled_bed_downtime
            patient.leave_mau = (self.env.now
                                - sampled_bed_downtime
                                - sampled_pat_move_duration)

        #Where does patient go on to from the MAU
        if patient.mau_disc:
            patient.note = 'Discharged from MAU'
        else:
            patient.note = 'Admitted to Specialty Ward'
            patient.discharge_specialty = random.choices(
                                          self.input_params.dis_spec,
                                          self.input_params.dis_prob)[0]

        self.store_patient_results(patient)
    
    ###################RECORD RESULTS####################
    def store_patient_results(self, patient):
        self.input_params.patient_results.append([self.run_number, patient.id,
                            patient.arrival, patient.ed_arrival_time,
                            patient.ed_leave_time, patient.enter_mau_queue,
                             patient.leave_mau_queue, patient.move_time,
                            patient.leave_mau, patient.bed_downtime,
                            patient.note, patient.mau_occ_when_queue_joined,
                            patient.discharge_specialty])
        
    def store_occupancy(self):
        while True:
            self.input_params.mau_occupancy_results.append([self.run_number,
                                                        self.mau_bed._env.now,
                                                        self.mau_bed.count,
                                                        len(self.mau_bed.queue),
                                                    self.ed.count])
            yield self.env.timeout(self.input_params.occ_sample_time)

    ########################RUN#######################
    def run(self):
        #Run process for the run time specified
        self.env.process(self.generate_initial_ed_patients())
        self.env.process(self.generate_initial_mau_patients())
        self.env.process(self.generate_walkin_ed_arrivals())
        self.env.process(self.generate_ambulance_ed_arrivals())
        self.env.process(self.generate_non_ed_mau_arrivals())
        self.env.process(self.store_occupancy())
        self.env.run(until=(self.input_params.run_time))

def export_results(scenario, run_days, pat_res, occ_res):
    #Create folders for outputs, do data processing and write to csv
    #Create folder for today's runs
    date_folder = (f'C:/Users/obriene/Projects/MAU model/outputs'
                   f'/{datetime.today().strftime('%Y-%m-%d')}')
    if not os.path.exists(date_folder):
        os.makedirs(date_folder)
    os.chdir(date_folder)
    
    #Create output folder (if doesn't exist) and navigate to it
    scenario_folder = scenario
    if not os.path.exists(scenario_folder):
        os.makedirs(scenario_folder)
    os.chdir(scenario_folder)

    #put full patient results into a dataframe and export to csv
    patient_df = (pd.DataFrame(pat_res,
                              columns=['run', 'patient ID', 'ED arrival type',
                                       'ED arrival time', 'ED leave time',
                                       'enter MAU queue', 'leave MAU queue',
                                       'ED to MAU move time', 'leave MAU',
                                       'MAU bed downtime', 'note',
                                       'MAU occ when queue joined',
                                       'discharge specialty'])
                                       .sort_values(by=['run', 'patient ID']))
    patient_df['simulation arrival time'] = (patient_df['ED arrival time']
                                        .fillna(patient_df['enter MAU queue']))
    patient_df['simulation arrival day'] = pd.cut(
                                          patient_df['simulation arrival time'],
                                          bins=run_days,
                                          labels=np.linspace(1,
                                                 run_days,
                                                 run_days))
    patient_df['simulation arrival hour'] = (
                                        patient_df['simulation arrival time']
                                        % (60*24) / 60).astype(int)
    patient_df['time in ED'] = (patient_df['ED leave time']
                                - patient_df['ED arrival time'])
    patient_df['time in MAU queue'] = (patient_df['leave MAU queue']
                                       - patient_df['enter MAU queue'])
    patient_df['time in MAU'] = (patient_df['leave MAU']
                                 - patient_df['leave MAU queue'])

    patient_df = patient_df[['run', 'patient ID', 'simulation arrival time',
                             'simulation arrival day','simulation arrival hour',
                             'ED arrival type', 'ED arrival time',
                             'ED leave time', 'time in ED', 'enter MAU queue',
                             'leave MAU queue', 'time in MAU queue',
                             'MAU occ when queue joined', 'leave MAU',
                             'time in MAU', 'MAU bed downtime', 'note',
                             'discharge specialty']].copy()
    patient_df.to_csv('mau patients.csv', index=False)

    #Put occupaion output data into dataframe and save to csv
    occ_df = pd.DataFrame(occ_res,
                              columns=['run', 'time', 'MAU beds occupied',
                                       'MAU queue length', 'ED Occupancy'])
    occ_df['day'] = pd.cut(occ_df['time'], bins=run_days,
                           labels=np.linspace(1,run_days,
                                              run_days))
    occ_df.to_csv('mau occupancy.csv', index=False)
    return patient_df, occ_df


def run_the_model(input_params):
    #run the model for the number of iterations specified
    for run in range(input_params.iterations):
        print(f"Run {run+1} of {input_params.iterations}")
        model = mau_model(run, input_params)
        model.run()

    patient_df, occ_df = export_results(input_params.scenario_name,
                                        input_params.run_days,
                                        input_params.patient_results,
                                        input_params.mau_occupancy_results)
    return patient_df, occ_df

pat, occ = run_the_model(default_params)

