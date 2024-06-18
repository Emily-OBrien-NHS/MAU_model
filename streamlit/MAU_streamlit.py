import streamlit as st
#import AcutePlusEDModel_streamlit as md
import stqdm
#from modelReplicator import Replicator
import os
os.chdir('C:/Users/obriene/Projects/MAU model')
from mau_model import default_params
from mau_model import run_the_model
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import numpy as np

#import time
def log_normal_transform(mu, sigma):
    #function to take the mean and standard deviation of a series
    #and convert then into the mu and sigma inputes required
    #to use a log normal distribution for randomly generating
    #patient times.
    input_mu = np.log((mu**2) / ((mu**2 + sigma**2)**0.5))
    input_sigma = np.log(1 + (sigma**2 / mu**2))**0.5
    return input_mu, input_sigma


st.set_page_config(
     #page_title="Ex-stream-ly Cool App",
     #page_icon="🧊",
     layout="wide",
     initial_sidebar_state="expanded",
     menu_items={
     #    'Get Help': 'https://www.extremelycoolapp.com/help',
     #    'Report a bug': "https://www.extremelycoolapp.com/bug",
         'About': "Model to simulate MAU demand"
     }
 )

st.title('MAU Model')

#Put input parameters in a sidebar
with st.sidebar:
    st.markdown('# Input Parameters')
    run_time = mean_other_mau_arr = st.slider('Simulation run time (days)', 7,
                                              730,
                                        value=int(default_params.run_time
                                                  // (60*24)))
    iterations = mean_other_mau_arr = st.slider('Simulation iterations', 1, 10,
                                        value=default_params.iterations)
    st.divider()
    st.markdown('# Arrivals')
    mean_other_mau_arr = st.slider('Average time between non ED MAU arrivals',
                                   0, 1000,
                                   value=default_params.mean_other_mau_arr)
    st.divider()
    st.markdown('# Average stay')
    mean_ed = st.slider('Average time in ED until DTA',0, 500,
                                value = default_params.mean_ed)
    mean_mau = st.slider('Average time in MAU', 0, 3000,
                                value = default_params.mean_mau)
    mau_bed_downtime = st.slider('Average MAU bed downtime', 30, 180,
                                value = default_params.mau_bed_downtime)
    st.divider()
    st.markdown('# MAU beds')
    no_mau_beds = st.slider('Number of MAU beds', 25, 100,
                                value = default_params.no_mau_beds)
    st.divider()
    st.markdown('# Split probabilities')
    ed_disc_prob = st.slider('Proportion discharged from ED', 0.0, 1.0,
                                value=default_params.ed_disc_prob)
    dta_admit_elsewhere_prob = st.slider('Proportion admitted elsewhere than MAU', 
                                         0.0, 1.0,
                                         value=default_params.dta_admit_elsewhere_prob)
    mau_disc_prob = st.slider('Proportion discharged from MAU', 0.0, 1.0,
                                value = default_params.mau_disc_prob)

#Get the parameters in a usable format
args = default_params()
#update defaults to selections
args.mean_other_mau_arr = mean_other_mau_arr
args.mean_ed = mean_ed
args.mu_ed, args.sigma_ed = log_normal_transform(mean_ed, args.std_ed)
args.mean_mau = mean_mau
args.mu_mau, args.sigma_mau = log_normal_transform(mean_mau, args.std_mau)
args.mau_bed_downtime = mau_bed_downtime
args.no_mau_beds = no_mau_beds
args.ed_disc_prob = ed_disc_prob
args.dta_admit_elsewhere_prob = dta_admit_elsewhere_prob
args.mau_disc_prob = mau_disc_prob
args.run_time = run_time*(60*24)#go back to minutes
args.iterations = iterations

	
#Button to run simulation
if st.button('Run simulation'):
    #First delete the previous results
    #if pat:
     #   del pat, occ
    # Run sim
    with st.empty():
        #progress_bar = stqdm(iterations, desc = 'Simulation progress...')
        pat, occ = run_the_model(args)
        #with st.spinner('Simulating patient arrivals and discharges...'):
        #	replications = Replicator(args,replications = args.number_of_runs)
        #	results, ed_res = replications.run_scenarios()
    st.success('Done!')

    #Add table of averages from simulation run
    st.subheader('Averages of the model run (time in minutes)')
    patient_averages = pat.mean(numeric_only=True).rename('average')
    occ_averages = occ.mean(numeric_only=True).rename('average')
    averages = pd.DataFrame(patient_averages._append(occ_averages)).transpose()
    averages = averages[['time in ED', 'ED Occupancy', 'time in MAU queue',
                         'MAU queue length', 'time in MAU',
                         'MAU beds occupied']].copy()
    averages[['time in ED',
              'time in MAU',
              'time in MAU queue']] = averages[['time in ED',
                                                'time in MAU',
                                                'time in MAU queue']].astype(int)
    st.dataframe(averages)

    #Group up data for plots
    mau_pat = (pat.dropna(subset='enter MAU queue')
               .groupby('simulation arrival day', as_index=False)
               ['time in MAU queue'].mean())
    av_occ = (occ.groupby('day', as_index=False)
              [['MAU queue length', 'MAU beds occupied']].mean())

    #Time in MAU queue plot
    st.subheader('Average time spent in MAU queue by day')
    st.line_chart(data=mau_pat, x='simulation arrival day',
                  y=['time in MAU queue'])
    #Length of MAU queue plot
    st.subheader('Length of MAU queue')
    st.line_chart(data=av_occ, x='day', y=['MAU queue length'])
    #MAU beds occupancy plot
    st.subheader('MAU beds occupancy')
    st.line_chart(data=av_occ, x='day', y=['MAU beds occupied'])
    #MAU wait times distribution plot
    st.subheader('Distribution of MAU wait times')
    fig, ax = plt.subplots()
    ax.hist(pat['time in MAU queue'], bins=25)
    ax.set_xlabel('Time in MAU queue')
    ax.set_ylabel('Frequency')
    st.pyplot(fig)


    #Print a table of the input parameters
    param_table = f'''
        |Parameter| Value                | Description                                                          |
        |---|-------------------------|----------------------------------------------------------------------|
        | Mean non-ED MAU arrivals | {args.mean_other_mau_arr}| Average time between non-ED MAU arrivals |
        | Average time in ED | {args.mean_ed}   | The average time until DTA in ED        |
        | Average time in MAU | {args.mean_mau}  | Teh average time spent in MAU     |
        | MAU bed downtime | {args.mau_bed_downtime}  | The average MAU bed downtime between patients     |
        | Number of MAU beds | {args.no_mau_beds}  | The number of beds in MAU  |
        | ED Discharge Probability | {args.ed_disc_prob} | The probability of being discharged from ED  |
        | Admitted elsewhere probability | {args.dta_admit_elsewhere_prob} | The probability that a patient is admitted somewhere other than MAU  |
        | MAU Discharge probability | {args.mau_disc_prob} | The probability of being discharged from MAU  |
        | Simulation run time | {args.run_time // (60*24)} | The simulation run time  |
        | Simulation iteraitons | {args.iterations} | The number of iterations to run the model for  |
        '''
    st.markdown(param_table)