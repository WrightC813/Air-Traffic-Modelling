# -*- coding: utf-8 -*-
"""
Created on Thu Apr 30 11:08:54 2026

@author: thecd
"""

import sqlite3
import pandas as pd
import numpy as np
import random
from CTMC_Model import *
import matplotlib.pyplot as plt

start_time = '2026-04-26 00:00'
start_time_pd = pd.Timestamp(start_time)

# %% Loading data to pandas dataframes for training
conn = sqlite3.connect('airport_data.db', isolation_level=None)

#Checking all airport codes are in airports table, and all airports have at least some flights
codes = conn.execute('SELECT DISTINCT airport FROM flights INTERSECT SELECT DISTINCT code FROM airports').fetchall()
codes = [c[0] for c in codes]
n_airports = len(codes)

#Removing any duplicate flight rows
conn.execute('''DELETE FROM flights
WHERE EXISTS (
  SELECT 1 FROM flights f2 
  WHERE flights.flight_code = f2.flight_code
  AND flights.flight_datetime = f2.flight_datetime
  AND flights.rowid > f2.rowid
);''')

#Selecting data from each airport
#Getting two versions of the data, one for discrete time model, other for cts time model
individual_df_disc = []
individual_df_cts = []
for c in codes:
    #getting data for this airport, converting the individual increments to a cumulative sum
    data_disc = conn.execute('SELECT flight_code, flight_datetime, increment, SUM(increment) OVER (ORDER BY flight_datetime) FROM flights WHERE (airport=? AND flight_datetime >= "2026-04-26 00:00") ORDER BY flight_datetime',[c]).fetchall()
    df_disc = pd.DataFrame(data_disc,columns=('Flight Code', 'Datetime', 'Increment', 'Number of Planes'))
    df_disc['Datetime'] = pd.to_datetime(df_disc['Datetime'])
    #In cases where more than one plane arrives at same datetime, collapse to single entry
    unique, counts = np.unique(df_disc['Datetime'], return_counts=True)
    dups = unique[counts > 1]
    for d in dups:
        f_codes = df_disc['Flight Code'][df_disc['Datetime'] == d].values
        inds = (df_disc.loc[df_disc['Datetime'] == dups[0]].index).values
        df_disc.drop(inds[1:],inplace=True)
        df_disc.loc[inds[0],'Flight Code'] = ', '.join(f_codes)
        
    
    individual_df_disc.append(df_disc)

    #In cts case, add random number of micro seconds up to one minute, reflecting our ignorance about exact time and to break any ties
    data_cts = conn.execute('SELECT flight_code, flight_datetime, increment FROM flights WHERE (airport=? AND flight_datetime >= "2026-04-26 00:00") ORDER BY flight_datetime',[c]).fetchall()
    df_cts = pd.DataFrame(data_cts,columns=('Flight Code', 'Datetime', 'Increment'))
    df_cts['Datetime'] = pd.to_datetime(df_cts['Datetime']).apply(lambda x: x + pd.Timedelta(random.randint(0,59999999),unit='us'))
    df_cts.sort_values('Datetime', inplace=True)
    df_cts['Number of Planes'] = df_cts['Increment'].cumsum()
    individual_df_cts.append(df_cts)
    

# %% Processing data frames for Markov chain model
for df in individual_df_cts  + individual_df_disc:
    #Convert datetime into minutes from start
    df['Minutes From Start'] = (df['Datetime'] - start_time_pd).apply(lambda x: x.total_seconds()/60)
    #Adding initial state
    df.loc[len(df)] = [None,start_time_pd,0,df.iloc[0]['Number of Planes'] - df.iloc[0]['Increment'],0]
    df.sort_values('Minutes From Start',inplace=True)
    #df = pd.concat([df,pd.DataFrame({'Flight Code':None, 'Datetime': start_time_pd, 'Increment':0, 'Number of Planes':df.iloc[0]['Number of Planes'] - df.iloc[0]['Increment'], 'Minutes From Start': 0},index=[-1])])#
    #Subtracting min number of planes to get a state in {0,1,...,S-1}
    df['State'] = df['Number of Planes'] - min(df['Number of Planes'])



# %% Fitting CTMC for cts version of dataset
n_iter = 10

for i, df in enumerate(individual_df_cts):
    name = conn.execute('SELECT name FROM airports WHERE code=?',[codes[i]]).fetchone()[0]
    states = df['State'].values
    times = df['Minutes From Start'].values
    xi = [180,540,900,1260]
    print(name)
    ctmc_MLE = CTMC()
    ctmc_MLE.fit(states,times,xi,a_optim='MLE',xi_optim='fixed',N=n_iter)
    print(f'Final xi values: {ctmc_MLE.xi}')
    
    ctmc_PM = CTMC()
    ctmc_PM.fit(states,times,xi,a_optim='PM',xi_optim='fixed',N=n_iter)
    
    fig, axs = plt.subplots(1,1)
    axs.set_title(name + ' - MLE')
    
    for j in range(2):
        s,t = ctmc_MLE.generate_path(states[0],0,times[-1])
        axs.step(t,s,where='post', label=f'Sample path {j+1}')
    axs.step(times,states,where='post',color='green', label='Observed path')
    axs.legend()
    axs.plot()
    
    fig, axs = plt.subplots(1,1)
    axs.set_title(name + ' - PM')
    
    for j in range(2):
        s,t = ctmc_PM.generate_path(states[0],0,times[-1])
        axs.step(t,s,where='post', label=f'Sample path {j+1}')
    axs.step(times,states,where='post',color='green', label='Observed path')
    axs.legend()
    axs.plot()




conn.close()