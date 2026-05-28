# -*- coding: utf-8 -*-
"""
Created on Thu Apr 30 11:08:54 2026

@author: thecd
"""

import sqlite3
import pandas as pd
import numpy as np
import random
import bisect
from CTMC_Model import *
import matplotlib.pyplot as plt

#Start and end times to consider data between
start_time = '2026-04-26 00:00'
start_time_pd = pd.Timestamp(start_time)
end_time = '2026-05-26 00:00'

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
    data_disc = conn.execute('SELECT flight_code, flight_datetime, increment, SUM(increment) OVER (ORDER BY flight_datetime) FROM flights WHERE (airport=? AND flight_datetime >= ? AND flight_datetime <= ?) ORDER BY flight_datetime',[c,start_time, end_time]).fetchall()
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
    data_cts = conn.execute('SELECT flight_code, flight_datetime, increment FROM flights WHERE (airport=? AND flight_datetime >= ? AND flight_datetime <= ?) ORDER BY flight_datetime',[c,start_time,end_time]).fetchall()
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
n_iter = 100

for i, df in enumerate(individual_df_cts[:1]):
    name = conn.execute('SELECT name FROM airports WHERE code=?',[codes[i]]).fetchone()[0]
    states = df['State'].values
    times = df['Minutes From Start'].values
    S = max(states) + 1
    #Default model structure - all 1 off diagonals have own parameter, all others 0
    structure = np.zeros((S,S))
    for i in range(S-1):
        structure[i,i+1] = 2*i + 1
        structure[i+1,i] = 2*i + 2
    
    print(name)
    
    
    # Comparing the optimistion methods for a and xi
    
    a_method = ['MLE', 'PM']
    xi_method = ['anneal', 'random']
    
    for a_m in a_method:
        for xi_m in xi_method:
            print(f'a_optim={a_m}, xi_optim={xi_m}')
            xi = [360,1080]
            Mod = CTMC()
            err, log_l = Mod.fit(states,times,xi,a_m,xi_m,N=n_iter, coeff_struct=structure)
            fig, axs = plt.subplots(figsize=(20,5))
            axs.set_title(f'{name} - a_optim={a_m}, xi_optim={xi_m}')
            for j in range(2):
                s,t = Mod.generate_path(states[0],0,times[-1])
                axs.step(t,s,where='post', label=f'Sample path {j+1}')
            axs.step(times,states,where='post',color='green', label='Observed path')
            axs.legend()
            print(f'Chosen xi - {Mod.xi}')
            print(f'log l= {log_l}')
            print(f'L1 error = {err[0]} +- {err[1]}')
            
            
# %% Testing predictions from solving transition semi-group equation
df = individual_df_cts[0]
states = df['State'].values
times = df['Minutes From Start'].values
S = max(states) + 1
#Default model structure - all 1 off diagonals have own parameter, all others 0
structure = np.zeros((S,S))
for i in range(S-1):
    structure[i,i+1] = 2*i + 1
    structure[i+1,i] = 2*i + 2

xi = [360,1080]
Mod = CTMC()
err, log_l = Mod.fit(states,times,xi,'MLE','anneal',N=100, coeff_struct=structure)

ts = sorted(random.sample(range(0,int(times[-1])),k=5))
P_0 = np.zeros(S)
P_0[states[0]] = 1
for t in ts:
    eq_times, dist = Mod.solve_forward_eq(0, t, P_0)
    true_state = states[bisect.bisect(times,t)]
    colors = ['blue' for i in range(S)]
    colors[true_state] = 'red'
    fig, ax = plt.subplots()
    
    ax.set_title(f'Predicted Distribution at Time {t}')
    ax.bar(range(S), dist[:,-1], color=colors)


    #Checking stability by looking at total probability
    fig2, ax2 = plt.subplots()
    ax2.plot(eq_times,dist.T, label=[f'State {i}' for i in range(S)])
    ax2.legend(columns=2)

    
    
# %% Investigating error for different partition choices

# n_iter = 10

# for i, df in enumerate(individual_df_cts[:1]):
#     name = conn.execute('SELECT name FROM airports WHERE code=?',[codes[i]]).fetchone()[0]
#     states = df['State'].values
#     times = df['Minutes From Start'].values
#     S = max(states) + 1
#     #Default model structure - all 1 off diagonals have own parameter, all others 0
#     structure = np.zeros((S,S))
#     for i in range(S-1):
#         structure[i,i+1] = 2*i + 1
#         structure[i+1,i] = 2*i + 2
    
#     print(name)
#     #Following uses random search to find x, comparing different numbers of partitions
    
#     fig_1, axs_1 = plt.subplots(2,2,sharex=True,sharey=True,figsize=(10,10))
#     fig_1.suptitle(name + ' - Partition Point L1 Error Estimates',fontsize=16, fontweight='bold')
    
#     fig_2, axs_2 = plt.subplots(4,1,sharex=True,sharey=True, figsize=(10,18))
#     fig_2.suptitle(name + ' - MLE + Random Search',fontsize=16, fontweight='bold')
    
#     fig_3, axs_3 = plt.subplots(2,2,sharex=True,sharey=True,figsize=(10,10))
#     fig_3.suptitle(name + ' - Partition Point Log Likelihood Estimates',fontsize=16, fontweight='bold')
    
#     ctmc_2 = CTMC()
#     err_baseline = ctmc_2.fit(states,times,[0],a_optim='MLE',xi_optim='fixed')
#     log_l_baseline = ctmc_2.log_l(states, times, ctmc_2.a, ctmc_2.xi)
    
#     for K in range(2,6):
#         ctmc_2 = CTMC()
#         xi_list = []
#         err_list = []
#         log_l_list = []
#         for i in range(n_iter):
#             xi = np.sort(random.sample(list(range(0,1440)),k=K))
#             print(f'{i+1} - xi values: {xi}')
#             err = ctmc_2.fit(states,times,xi,a_optim='MLE',xi_optim='fixed',coeff_struct=structure)
#             xi_list.append(xi)
#             err_list.append(err)
#             log_l_list.append(ctmc_2.log_l(states,times,ctmc_2.a,ctmc_2.xi))
            
#         #Plotting errors of each xi choice
#         axs_1[K//4,K%2].set_title(f'K = {K}')
#         axs_3[K//4,K%2].set_title(f'K = {K}')
        
#         x = np.array(xi_list)
#         e = np.array(err_list)
#         e_v = e[:,0]
#         e_sd = e[:,1]
#         axs_1[K//4,K%2].plot(x.T, np.vstack([e_v for i in range(K)]), color='blue', alpha=0.5)
#         err_v_2 = np.ravel([[e[0] for i in range(K)] for e in err_list])
#         err_sd_2 = np.ravel([[e[1] for i in range(K)] for e in err_list])
#         axs_1[K//4,K%2].errorbar(np.ravel(x), err_v_2, yerr=err_sd_2, linestyle='None', marker='x')
#         axs_1[K//4,K%2].hlines(y=err_baseline[0],xmin=0,xmax=1440,color='green')
#         axs_1[K//4,K%2].hlines(y=[err_baseline[0] - err_baseline[1],err_baseline[0] + err_baseline[1]],xmin=0,xmax=1440,color='red')
        
#         axs_3[K//4,K%2].plot(x.T, np.vstack([log_l_list for i in range(K)]), color='blue', alpha=0.5)
#         axs_3[K//4,K%2].hlines(y=log_l_baseline,xmin=0,xmax=1440,color='green')
#         axs_3[K//4,K%2].scatter(np.ravel(x),np.ravel([[l for i in range(K)] for l in log_l_list]), marker='x')
        
#         #Plotting observed vs simulated data
#         axs_2[K-2].set_title(f'K = {K}')
#         best_ind = np.argmin(err_list,axis=0)[0]
#         xi_best = xi_list[best_ind]
#         err_best = err_list[best_ind]
#         print(f'Best xi values: {xi_best}, error: {err_best[0]} +- {err_best[1]}')
#         ctmc_2.fit(states,times,xi_best,a_optim='MLE',xi_optim='fixed')
#         for j in range(2):
#             s,t = ctmc_2.generate_path(states[0],0,times[-1])
#             axs_2[K-2].step(t,s,where='post', label=f'Sample path {j+1}', alpha = 0.5)
#         axs_2[K-2].step(times,states,where='post',color='green', label='Observed path', alpha = 1)
#         axs_2[K-2].legend()
    
    
conn.close()