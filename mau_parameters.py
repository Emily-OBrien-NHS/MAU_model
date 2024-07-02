import pandas as pd
import numpy as np
from sqlalchemy import create_engine

#############################################################################
#Create the engine
SDMart_engine = create_engine('mssql+pyodbc://@SDMartDataLive2/PiMSMarts?'\
                           'trusted_connection=yes&driver=ODBC+Driver+17'\
                               '+for+SQL+Server')
cl3_engine = create_engine('mssql+pyodbc://@cl3-data/DataWarehouse?'\
                           'trusted_connection=yes&driver=ODBC+Driver+17'\
                               '+for+SQL+Server')

#sql query
mau_query = """SET NOCOUNT ON
select prvsp_refno, MAUStart = min(sstay_start_dttm),
MAUEnd = max(sstay_end_dttm)
  into #MAUStay
  from [PiMSMarts].[dbo].[ip_movements]
  where move_reason_sp = 's'
  and sstay_ward_code in ('RK950MAU','RK950AMW')
  and sstay_end_dttm between '01-Apr-2023 00:00:00' and '31-Mar-2024 00:00:00'
  group by prvsp_refno

  select mstay.*, post_mau.sstay_ward_code, post_mau.sstay_start_dttm,
  case when (post_mau.sstay_ward_code is NULL
  or post_mau.sstay_ward_code = 'RK950101'
  or post_mau.sstay_ward_code = 'RK950113') then 'MAU Discharge' --If they go to DL
		when post_mau.sstay_ward_code like 'RK950%' then 'Transfer to Acute Ward'
		when (post_mau.sstay_ward_code like 'RK901%' or
			post_mau.sstay_ward_code like 'RK906%' or
			post_mau.sstay_ward_code like 'RK935%' or
			post_mau.sstay_ward_code like 'RK959%' or 
			post_mau.sstay_ward_code like 'RK922%') then 'Transfer to Community Ward'
			else post_mau.sstay_ward_code end as DischRoute
	,totalLoS.DischargeDttm			
  from #MAUStay mstay
  left join [PiMSMarts].[dbo].[ip_movements] post_mau
	on post_mau.prvsp_refno = mstay.prvsp_refno
	and post_mau.move_reason_sp = 's'
	and post_mau.sstay_start_dttm = mstay.MAUEnd ---get next ward after MAU
  left join (select prvsp_refno,  DischargeDttm = max(sstay_end_dttm)
			from [PiMSMarts].[dbo].[ip_movements] 
			where sstay_ward_code not in ('RK950MAU','RK950AMW')
			and sstay_ward_code not like 'rk901%'
			and sstay_ward_code not like 'rk959%'
			and sstay_ward_code not like 'rk935%'
			and sstay_ward_code not like 'rk906%'
			and move_reason_sp = 'S'
			and sstay_end_dttm between '01-Jan-2023 00:00:00' and getdate()
			group by prvsp_refno
			)totalLos
	on totalLos.prvsp_refno = mstay.prvsp_refno
	and totalLos.DischargeDttm > mstay.MAUEnd ---only ward moves that happen after MAU

	order by mstay.prvsp_refno
"""

ed_query = """
SELECT [ArrivalDateTime]
      ,[ArrivalModeDescription]
	  ,[DecidedToAdmitDateTime]
	  ,[BedRequestedDateTime]
      ,[BedReadyDateTime]
      ,[DischargeDateTime]
      ,[DischargeDestinationGroup]
      ,[ActualDischargeDestinationDescription]
      ,[LengthOfStay]
	  ,AdmitPrvspRefno
  FROM [DataWarehouse].[ED].[vw_EDAttendance]
  WHERE DischargeDateTime between '01-Apr-2023 00:00:00' and '31-Mar-2024 00:00:00'
  AND IsNewAttendance = 'Y'
"""

discharge_query = """SET NOCOUNT ON
---Get MAU spells
SELECT prvsp_refno
INTO #MAUStay
FROM [PiMSMarts].[dbo].[ip_movements]
WHERE move_reason_sp = 's'
AND sstay_ward_code IN ('RK950MAU','RK950AMW')
AND sstay_end_dttm BETWEEN '01-Apr-2023 00:00:00' AND '31-Mar-2024 00:00:00'
GROUP BY prvsp_refno


-----Join to ipdc view to find discharging specialties
SELECT  spec.local_spec_desc
      ,COUNT(fce_end_ward) AS 'count'
FROM [InfoDB].[dbo].[vw_ipdc_fces_pfmgt] ipdc
LEFT JOIN [InfoDB].[dbo].[vw_cset_specialties] spec
ON ipdc.local_spec = spec.local_spec
INNER JOIN #MAUStay maustay 
ON maustay.prvsp_refno = ipdc.prvsp_refno
WHERE patcl = 1---inpatients
AND [provider] = 'rk900' ----UHP activity
AND last_episode_in_spell = '1' ----final episode of stay
AND fce_end_ward NOT IN ('rk950amw','rk950mau') ---not discharged from MAU
GROUP BY local_spec_desc"""

mau_df = (pd.read_sql(mau_query, SDMart_engine)
          .rename(columns={'prvsp_refno':'AdmitPrvspRefno'}))
ed_df = pd.read_sql(ed_query, cl3_engine)
dis_df = pd.read_sql(discharge_query, SDMart_engine).sort_values(by='count',
                                                                 ascending=False)
dis_df.to_csv('C:/Users/obriene/Projects/MAU model/discharge specialties.csv',
              index=False)

#Close the connection
SDMart_engine.dispose()
cl3_engine.dispose()

#####################################################################################
#interarrival times for ambulance and walkin
#ambulance
amb_df = (ed_df.loc[ed_df['ArrivalModeDescription'].str.contains('ambulance'),
                   ['ArrivalDateTime', 'ArrivalModeDescription']]
                   .sort_values(by='ArrivalDateTime'))
amb_df['ArrivalHour'] = amb_df['ArrivalDateTime'].dt.hour
amb_df['DateShifted'] = amb_df['ArrivalDateTime'].shift(-1)
amb_df['AmbTimeBetweenArrivals'] = ((amb_df['DateShifted'] - amb_df['ArrivalDateTime'])
                                    / pd.Timedelta(minutes=1))
amb_av = amb_df['AmbTimeBetweenArrivals'].mean()
print(f'Average time between ambulance arrivals is {amb_av:.0f} minutes')
amb_dis = (amb_df.groupby('ArrivalHour', as_index=False)
           ['AmbTimeBetweenArrivals'].mean())
amb_dis['AmbTimeBetweenArrivals'] = amb_dis['AmbTimeBetweenArrivals'] / amb_av

#walk in
wlkin_df = (ed_df.loc[~ed_df['ArrivalModeDescription'].str.contains('ambulance'),
                   ['ArrivalDateTime', 'ArrivalModeDescription']]
                   .sort_values(by='ArrivalDateTime'))
wlkin_df['ArrivalHour'] = wlkin_df['ArrivalDateTime'].dt.hour
wlkin_df['DateShifted'] = wlkin_df['ArrivalDateTime'].shift(-1)
wlkin_df['WlkinTimeBetweenArrivals'] = ((wlkin_df['DateShifted']
                                         - wlkin_df['ArrivalDateTime'])
                                         / pd.Timedelta(minutes=1))
wlkin_av = wlkin_df['WlkinTimeBetweenArrivals'].mean()
print(f'Average time between walk in arrivals is {wlkin_av:.0f} minutes')
wlkin_dis = (wlkin_df.groupby('ArrivalHour', as_index=False)
             ['WlkinTimeBetweenArrivals'].mean())
wlkin_dis['WlkinTimeBetweenArrivals'] = (wlkin_dis['WlkinTimeBetweenArrivals']
                                         / wlkin_av)
#Arrivals based on hour of the day
hourly_averages = wlkin_dis.merge(amb_dis, on='ArrivalHour')

#Non-ed MAU admissions
merged = ed_df.loc[~ed_df['AdmitPrvspRefno'].isna()].merge(mau_df,
                                                           on='AdmitPrvspRefno',
                                                           how='outer')
merged = merged.loc[merged['ArrivalDateTime'].isnull(),
                    ['MAUStart', 'DischRoute']].sort_values(by='MAUStart')
merged['ArrivalHour'] = merged['MAUStart'].dt.hour
merged['DateShifted'] = merged['MAUStart'].shift(-1)
merged['TimeBetweenArrivals'] = ((merged['DateShifted'] - merged['MAUStart'])
                                 / pd.Timedelta(minutes=1))
non_ed_arr_av = merged['TimeBetweenArrivals'].mean()
print(f'Average time between non-ED MAU arrivals is {non_ed_arr_av:.0f} minutes')
non_ed_arr = (merged.groupby('ArrivalHour', as_index=False)
              ['TimeBetweenArrivals'].mean()
              .rename(columns={'TimeBetweenArrivals':'Non ED MAU Admissions'}))
non_ed_arr['Non ED MAU Admissions'] = (non_ed_arr['Non ED MAU Admissions']
                                       / non_ed_arr_av)
hourly_averages = hourly_averages.merge(non_ed_arr, on='ArrivalHour', how='left').interpolate()

#Average time in ED until DTA
ed_df['ArrivalHour'] = ed_df['ArrivalDateTime'].dt.hour
ed_df['TimeToDTA'] = ((ed_df['DecidedToAdmitDateTime'] - ed_df['ArrivalDateTime'])
                      / pd.Timedelta(minutes=1))
mean_ed_los = ed_df['TimeToDTA'].mean()
std_ed_los = ed_df['TimeToDTA'].std()
print(f'Average time in ED until DTA is {mean_ed_los:.0f} minutes')
print(f'Standard Deviation time in ED until DTA is {std_ed_los:.0f} minutes')
ed_los = (ed_df.groupby('ArrivalHour', as_index=False)['TimeToDTA']
          .agg(['mean', 'std']))
ed_los['mean ED LoS'] = ed_los['mean'] / mean_ed_los
ed_los['std ED LoS'] = ed_los['std'] / std_ed_los
hourly_averages = hourly_averages.merge(ed_los[['ArrivalHour', 'mean ED LoS',
                                                'std ED LoS']], on='ArrivalHour',
                                                how='left').interpolate()

#Average time it takes a patient to move fro ED to MAU Bed
#merge on MAU table to get only MAU patients
#Filter data to betwen 5% and 95% quantiles (to remove negatives and multiple
#day transfertimes)
merged = ed_df.loc[~ed_df['AdmitPrvspRefno'].isna()].merge(mau_df,
                                                           on='AdmitPrvspRefno',
                                                           how='inner')
merged['patient move time'] = ((merged['DischargeDateTime']
                              - merged['BedReadyDateTime'])
                              / pd.Timedelta(minutes=1))
lower = merged['patient move time'].quantile(0.05)
upper = merged['patient move time'].quantile(0.95)
merged['ArrivalHour'] = merged['DischargeDateTime'].dt.hour
filtered = merged.loc[(merged['patient move time'] > lower)
                     & (merged['patient move time'] < upper),
                     ['patient move time', 'ArrivalHour']].copy()
mean_move = filtered['patient move time'].mean()
std_move = filtered['patient move time'].std()
print(f'Average time to move a patient to an MAU bed is {mean_move}')
print(f'Standard Deviation time to move a patient to an MAU bed is {std_move}')
move = (filtered.groupby('ArrivalHour', as_index=False)['patient move time']
        .agg(['mean', 'std']))
move['mean move'] = move['mean'] / mean_move
move['std move'] = move['std'] / std_move
hourly_averages = hourly_averages.merge(move[['ArrivalHour',
                                              'mean move', 'std move']],
                                              on='ArrivalHour', how='left').interpolate()

#average time spent in MAU
mau_df['ArrivalHour'] = mau_df['MAUStart'].dt.hour
mau_df['MAU Time'] = ((mau_df['MAUEnd'] - mau_df['MAUStart'])
                      / pd.Timedelta(minutes=1))
mean_mau_los = round(mau_df['MAU Time'].mean())
std_mau_los = mau_df['MAU Time'].std()
print(f'Average time spent in MAU is {mean_mau_los} minutes')
print(f'Standard Deviation time in ED until DTA is {std_mau_los:.0f} minutes')
mau_los = (mau_df.groupby('ArrivalHour', as_index=False)['MAU Time']
           .agg(['mean', 'std']))
mau_los['mean MAU LoS'] = mau_los['mean'] / mean_mau_los
mau_los['std MAU LoS'] = mau_los['std'] / std_mau_los
hourly_averages = hourly_averages.merge(mau_los[['ArrivalHour',
                                                 'mean MAU LoS', 'std MAU LoS']],
                                                 on='ArrivalHour', how='left').interpolate()

#export hourly scalars to csv
hourly_averages.to_csv('C:/Users/obriene/Projects/MAU model/hourly average scalars.csv', index=False)
print(hourly_averages)

####PROPORTIONS####
#Proportion of ED patients who get discharged
prop = ed_df['AdmitPrvspRefno'].notnull().value_counts(normalize=True)
print(f'Proportion of patients being discharged from ED is {prop[False]:.2f}')

#Proportion of admitted that are admitted to MAU
merged = (ed_df.loc[~ed_df['AdmitPrvspRefno'].isna()]
          .merge(mau_df, on='AdmitPrvspRefno', how='left'))
prop = merged['sstay_start_dttm'].notnull().value_counts(normalize=True)
print(f'Proportion of patients that are admitted to somewhere other than MAU is {prop[False]:.2f}')

#proportion that get discharged home from MAU
mau_disc = (mau_df.loc[mau_df['DischRoute'] == 'MAU Discharge', 'DischRoute'].count()
            / mau_df['DischRoute'].count())
print(f'Proportion of patients that get discharged from MAU is {mau_disc:.2f}')