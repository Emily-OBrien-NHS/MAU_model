import streamlit as st
from stqdm import stqdm
from mau_model import default_params
from mau_model import run_the_model
from mau_replicator import Replicator
import matplotlib.pyplot as plt
import pandas as pd


st.set_page_config(
     page_title="MAU Model",
     page_icon="🏥",
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
    mean_amb_arr = st.slider('Average time between Ambulance ED arrivals',
                             0, 60, value=default_params.mean_amb_arr)
    mean_wlkin_arr = st.slider('Average time between walk-in ED arrivals',
                               0, 60, value=default_params.mean_wlkin_arr)
    mean_other_mau_arr = st.slider('Average time between non ED MAU arrivals',
                                   0, 1000,
                                   value=default_params.mean_other_mau_arr)
    st.divider()
    st.markdown('# Average stay')
    mean_ed = st.slider('Average time in ED until DTA',0, 500,
                                value = default_params.mean_ed)
    mean_mau = st.slider('Average time in MAU', 0, 3000,
                                value = default_params.mean_mau)
    st.divider()
    st.markdown('# patient move and bed downitme')
    mean_move = st.slider('Average time to move patient into MAU bed',
                          10, 60, value = default_params.mean_move)
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
args.scenario_name = 'streamlit'
args.mean_amb_arr = mean_amb_arr
args.mean_wlkin_arr = mean_wlkin_arr
args.mean_other_mau_arr = mean_other_mau_arr
args.mean_ed = mean_ed
args.mean_move = mean_move
args.mean_mau = mean_mau
args.mau_bed_downtime = mau_bed_downtime
args.no_mau_beds = no_mau_beds
args.ed_disc_prob = ed_disc_prob
args.dta_admit_elsewhere_prob = dta_admit_elsewhere_prob
args.mau_disc_prob = mau_disc_prob
args.run_time = run_time*(60*24)#go back to minutes
args.run_days = int(args.run_time/(60*24))
args.iterations = iterations
args.patient_results = []
args.mau_occupancy_results = []

    
#Button to run simulation
if st.button('Run simulation'):
    #First delete the previous results
    #try:
     #  if pat:
      #     del pat, occ
    #except:
     #   pass

    # Run sim
    st.subheader('Simulation progress:')
    with st.empty():
        #progress_bar = stqdm(range(iterations), desc='Simulation progress...',
         #                    mininterval=1)
        #pat, occ = run_the_model(args)

        with st.spinner('Simulating patient arrivals and discharges...'):
            replications = Replicator(args, replications=args.iterations)
            pat, occ = replications.run_scenarios()
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
               .groupby('simulation arrival day', as_index=False,
                        observed=True)['time in MAU queue'].mean())
    av_occ = (occ.groupby('day', as_index=False, observed=True)
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
    #Add table of the discharge specialty counts
    st.subheader('Average number of patients discharged to each specialty from MAU over run time')
    disc_spec = (pat['discharge specialty'].value_counts()
                 / args.iterations).astype(int)
    st.table(disc_spec.loc[disc_spec > 0])