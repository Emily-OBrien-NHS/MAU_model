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
select prvsp_refno, MAUStart = min(sstay_start_dttm), MAUEnd = max(sstay_end_dttm)
  into #MAUStay
  from [PiMSMarts].[dbo].[ip_movements]
  where move_reason_sp = 's'
  and sstay_ward_code in ('RK950MAU','RK950AMW')
  and sstay_end_dttm between '01-Apr-2023 00:00:00' and '31-Mar-2024 00:00:00'
  group by prvsp_refno

  select mstay.*, post_mau.sstay_ward_code, post_mau.sstay_start_dttm,
  case when (post_mau.sstay_ward_code is NULL or post_mau.sstay_ward_code = 'RK950101' or post_mau.sstay_ward_code = 'RK950113') then 'MAU Discharge' --If they go to DL
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
      ,[DischargeDateTime]
      ,[DischargeDestinationGroup]
      ,[ActualDischargeDestinationDescription]
      ,[LengthOfStay]
	  ,AdmitPrvspRefno
  FROM [DataWarehouse].[ED].[vw_EDAttendance]
  WHERE DischargeDateTime between '01-Apr-2023 00:00:00' and '31-Mar-2024 00:00:00'
  AND IsNewAttendance = 'Y'
"""

mau_df = pd.read_sql(mau_query, SDMart_engine).rename(columns={'prvsp_refno':'AdmitPrvspRefno'})
ed_df = pd.read_sql(ed_query, cl3_engine)

#Close the connection
SDMart_engine.dispose()
cl3_engine.dispose()

#####################################################################################
#interarrival times for ambulance and walkin
#ambulance
amb_df = ed_df.loc[ed_df['ArrivalModeDescription'].str.contains('ambulance'),
                   ['ArrivalDateTime', 'ArrivalModeDescription']].sort_values(by='ArrivalDateTime')
amb_df['DateShifted'] = amb_df['ArrivalDateTime'].shift(-1)
amb_df['TimeBetweenArrivals'] = (amb_df['DateShifted'] - amb_df['ArrivalDateTime']) / pd.Timedelta(minutes=1)
print(f'Average time between ambulance arrivals is {amb_df['TimeBetweenArrivals'].mean():.0f} minutes')

#walk in
wlkin_df = ed_df.loc[~ed_df['ArrivalModeDescription'].str.contains('ambulance'),
                   ['ArrivalDateTime', 'ArrivalModeDescription']].sort_values(by='ArrivalDateTime')
wlkin_df['DateShifted'] = wlkin_df['ArrivalDateTime'].shift(-1)
wlkin_df['TimeBetweenArrivals'] = (wlkin_df['DateShifted'] - wlkin_df['ArrivalDateTime']) / pd.Timedelta(minutes=1)
print(f'Average time between walk in arrivals is {wlkin_df['TimeBetweenArrivals'].mean():.0f} minutes')

#Non-ed MAU admissions
merged = ed_df.loc[~ed_df['AdmitPrvspRefno'].isna()].merge(mau_df, on='AdmitPrvspRefno', how='outer')
merged = merged.loc[merged['ArrivalDateTime'].isnull(),
                    ['MAUStart', 'DischRoute']].sort_values(by='MAUStart')
merged['DateShifted'] = merged['MAUStart'].shift(-1)
merged['TimeBetweenArrivals'] = (merged['DateShifted'] - merged['MAUStart']) / pd.Timedelta(minutes=1)
print(f'Average time between non-ED MAU arrivals is {merged['TimeBetweenArrivals'].mean():.0f} minutes')

#Average time in ED until DTA
ed_df['TimeToDTA'] = (ed_df['DecidedToAdmitDateTime'] - ed_df['ArrivalDateTime']) / pd.Timedelta(minutes=1)
print(f'Average time in ED until DTA is {ed_df['TimeToDTA'].mean():.0f} minutes')
print(f'Standard Deviation time in ED until DTA is {ed_df['TimeToDTA'].std():.0f} minutes')

#average time spent in MAU
mau_df['MAU Time'] = (mau_df['MAUEnd'] - mau_df['MAUStart']) / pd.Timedelta(minutes=1)
print(f'Average time spent in MAU is {round(mau_df['MAU Time'].mean())} minutes')
print(f'Standard Deviation time in ED until DTA is {mau_df['MAU Time'].std():.0f} minutes')

#Proportion of ED patients who get discharged
prop = ed_df['AdmitPrvspRefno'].notnull().value_counts(normalize=True)
print(f'Proportion of patients being discharged from ED is {prop[False]:.2f}')

#Proportion of admitted that are admitted to MAU
merged = ed_df.loc[~ed_df['AdmitPrvspRefno'].isna()].merge(mau_df, on='AdmitPrvspRefno', how='left')
prop = merged['sstay_start_dttm'].notnull().value_counts(normalize=True)
print(f'Proportion of patients that are admitted to somewhere other than MAU is {prop[False]:.2f}')

#proportion that get discharged home from MAU
mau_disc = (mau_df.loc[mau_df['DischRoute'] == 'MAU Discharge', 'DischRoute'].count()
            / mau_df['DischRoute'].count())
print(f'Proportion of patients that get discharged from MAU is {mau_disc:.2f}')