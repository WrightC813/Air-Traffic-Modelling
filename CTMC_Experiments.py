# -*- coding: utf-8 -*-
"""
Created on Thu Feb 26 20:16:31 2026

@author: thecd
"""

import random
import matplotlib.pyplot as plt
import numpy as np


# %% CTMC

def step(Q,state):
    if -Q[state,state] == 0:
        return np.inf, state
    
    time = random.expovariate(-Q[state,state])
    weights = Q[state,:].copy()
    weights[state] = 0
    new_state = random.choices(list(range(len(weights))),weights,k=1)[0]
    return time, new_state




def generate(Q,chain,times,steps=10):
    for i in range(steps):
        time, state = step(Q,chain[-1])
        times.append(times[-1] + time)
        chain.append(state)
        if times[-1] == np.inf:
            break
    return chain, times

def plot_process(chain, times):
    plt.step(times,chain,where='post')
    plt.show()
    
    
# %% Estimate parameters from observation using MLE and Baysian approach from uniform prior

def MLE_estimate(chain,times):
    times_delta = np.ediff1d(times)
    N = int(max(chain)) + 1
    Q = np.zeros((N,N))
    #J = matrix of numer of jumps i to j
    J = np.zeros((N,N))
    # T = array of holding times in state i
    T = np.zeros(N)
    for i in range(len(chain)-1):
        T[chain[i]] += times_delta[i]
        J[chain[i],chain[i+1]] += 1
    for i in range(N):
        if T[i] == 0:
            Q[i,:] = np.zeros(N)
            continue
        for j in range(N):
            if j==i:
                continue
            Q[i,j] = J[i,j]/T[i]
            
    for i in range(N):
        Q[i,i] = -np.sum(Q[i,:])
        
    return Q


def Bayes_estimtate(chain,times):
    times_delta = np.ediff1d(times)
    N = int(max(chain)) + 1
    Q = np.zeros((N,N))
    #J = matrix of numer of jumps i to j
    J = np.zeros((N,N))
    # T = array of holding times in state i
    T = np.zeros(N)
    for i in range(len(chain)-1):
        T[chain[i]] += times_delta[i]
        J[chain[i],chain[i+1]] += 1
    for i in range(N):
        if T[i] == 0:
            Q[i,:] = np.zeros(N)
            continue
        for j in range(N):
            if j==i:
                continue
            Q[i,j] = (J[i,j]+1)/T[i]
            
    for i in range(N):
        Q[i,i] = -np.sum(Q[i,:])
        
    return Q
    
# %% Two state system


a = 1
b = 2
Q = np.array([[-a,a],[b,-b]])
state_init = 0

discrete_chain = [state_init]
jump_times = [0]
    
discrete_chain, jump_times = generate(Q, discrete_chain, jump_times, steps=100)

plot_process(discrete_chain, jump_times)



# %% Four state chain with absorbing state

Q = np.array([[-1, 0.5, 0.5, 0],[0.25, -0.5, 0, 0.25],[1/6, 0, -1/3, 1/6],[0,0,0,0]])
state_init = 0

discrete_chain = [state_init]
jump_times = [0]
    
discrete_chain, jump_times = generate(Q, discrete_chain, jump_times, steps=100)

plot_process(discrete_chain, jump_times)


Q_MLE = MLE_estimate(discrete_chain,jump_times)
print(Q_MLE)
plt.matshow(Q_MLE)