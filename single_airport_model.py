# -*- coding: utf-8 -*-
"""
Created on Fri Apr  3 19:42:11 2026

@author: thecd
"""

from airport_data_scraper import Airport
import pickle
import random
import matplotlib.pyplot as plt
import numpy as np


# %% Loading airport data


with open('airport_data.pickle', 'rb') as f:
    all_airports = pickle.load(f)
print('Data loaded')
names = []
raw_data = []
for A in all_airports:
    names.append(A.name)
    raw_data.append(A.return_data())

# %% Plotting 



for i, df in enumerate(raw_data):
    print(f'Missing from {names[i]}:')
    print(all_airports[i].segments_df.loc[all_airports[i].segments_df['Downloaded'] == False])
    plt.step(df['DateTime'],df['Number of Planes'],where='post')
    plt.title(names[i])
    plt.show()


# %% Functions for log-likelihood and finding best coeficients

def N_val(states,times,xi):
    S = max(states) + 1
    K = len(xi)
    k = k_values(times,xi)
    num = np.zeros((S,S,K))
    for i in range(1,len(states)):
        num[states[i-1],states[i],k[i]] += 1.0
        
    return num

def D_val(states,times,xi):
    S = max(states) + 1
    K = len(xi)
    den = np.zeros((S,S,K))
    for i in range(1,len(states)):
        den[states[i-1],:,:] += np.outer(np.ones(S),time_in_segments(times[i-1], times[i], xi))
        
    return den
        
    	
def k_values(times,xi):
    """
    Function to find which basis function interval times are in
    Parameters
    ----------
    times : List
        Sequence of times
        
    xi : np.array with shape (K)
        array of partition times for piecewise constant basis functions
    

    Returns
    -------
    k_indices : list
        sequence of which time interval each jump time lies in
    """
    k_indices = [0 for i in range(len(times))]
    extended_xi = [xi[-1] - 1440] + list(xi) + [xi[0] + 1440]
    for i in range(len(times)):
        less = [(times[i] % 1440 < x) for x in extended_xi]
        k_indices[i] = (less.index(True) - 2) % len(xi)
        
    return k_indices


def time_in_segments(T_0,T_1,xi):
    """
    Function computing how much time between T_0 and T_1 spent in each segment
    Parameters
    ----------
    T_0 : float
        start time
    
    T_1 : float
        end time
        
    xi : np.array with shape (K)
        array of partition times for piecewise constant basis functions
    

    Returns
    -------
    seg_times : np.array with shape (K)
        array of times spent in each segment
    """
    K = len(xi)
    seg_times = np.zeros(K)
    t = T_0
    while t < T_1:
        current_k = k_values([t], xi)[0]
        if current_k == K-1:
            new_t = t + (xi[0] - (t%1440))
            if (t%1440) > xi[0]:
                new_t += 1440
        else:
            new_t = t + (xi[current_k + 1] - (t%1440))
        time = min([new_t - t,T_1 - t])
        seg_times[current_k] += time
        if new_t <= t:
            break
        t = new_t
        
    return seg_times

def log_l(states,times,a,xi):
    """
    Function to compute the log likelihood of the model
    Parameters
    ----------
    states : List
        Sequence of observed states, assumed from {0,1,..S-1}
        
    times : List
        Sequence of observed jump times (in minutes from initial time 0)
        
    a : np array with shape (S,S,K)
        array of coeffients for Q matrix of model, S = #states, K = #basis functions
        
    xi : np.array with shape (K)
        array of partition times for piecewise constant basis functions
    

    Returns
    -------
    l : float
        Log likelihood of the model

    """
    num = N_val(states, times, xi)
    den = D_val(states, times, xi)
    
    term_1 = np.multiply(num,np.log(a))
    #Dealing with special case where no jumps are observed. MLE then gives a=0
    term_1[num == 0] = 0
    term_2 = np.multiply(a,den)
    return np.sum(term_1 - term_2)
    
    # l = 0
    # S = max(states) + 1
    # k = k_values(times,xi)
    # for i in range(1,len(states)):
    #     l += np.log(a[states[i-1],states[i],k[i]])
    #     for z in range(S):
    #         if z != states[i-1]:
    #             l -= np.inner(a[states[i-1],z,:],time_in_segments(times[i-1], times[i], xi))
        
    # return l
                
def a_MLE(states,times,xi):
    """
    Function to find the MLE estimator for the coefficients a, given the observations and xi
    Parameters
    ----------
    states : List
        Sequence of observed states, assumed from {0,1,..S-1}
        
    times : List
        Sequence of observed jump times (in minutes from initial time 0)
        
    xi : np.array with shape (K)
        array of partition times for piecewise constant basis functions
    

    Returns
    -------
    a : np array with shape (S,S,K)
        array of coeffients for Q matrix of model, S = #states, K = #basis functions
    """
    S = max(states) + 1
    K = len(xi)
    num = N_val(states, times, xi)
    den = D_val(states, times, xi)
    # k = k_values(times, xi)
    # for i in range(1,len(states)):
    #     num[states[i-1],states[i],k[i]] += 1.0
    #     den[states[i-1],:,:] += np.outer(np.ones(S),time_in_segments(times[i-1], times[i], xi))
        
    
    #In case den is zero, we set the corresponding a coefficient to small positive value
    a = np.divide(num,den)
    a[den == 0] = 10**(-8)
    for i in range(S):
        for k in range(K):
            a[i,i,k] = -np.sum(a[i,:,k])
    return a


def a_PM(states,times,xi):
    """
    Function to find the PM (posterior mean) estimator for the coefficients a, given the observations and xi.
    Flat Baysian prior used, yielding gamma posterior, effect is adding one pseudo-count to each jump in each time interval.
    Note MAP estimator is same as MLE
    Parameters
    ----------
    states : List
        Sequence of observed states, assumed from {0,1,..S-1}
        
    times : List
        Sequence of observed jump times (in minutes from initial time 0)
        
    xi : np.array with shape (K)
        array of partition times for piecewise constant basis functions
    

    Returns
    -------
    a : np array with shape (S,S,K)
        array of coeffients for Q matrix of model, S = #states, K = #basis functions
    """
    S = max(states) + 1
    K = len(xi)
    num = N_val(states, times, xi)
    num[:,:,:] += 1
    den = D_val(states, times, xi)
    # k = k_values(times, xi)
    # for i in range(1,len(states)):
    #     num[states[i-1],states[i],k[i]] += 1.0
    #     den[states[i-1],:,:] += np.outer(np.ones(S),time_in_segments(times[i-1], times[i], xi))
        
    #In case den is zero, posterior is improper. We default a to small positive value
    a = np.divide(num,den)
    a[den == 0] = 10**(-8)
    for i in range(S):
        for k in range(K):
            a[i,i,k] = -np.sum(a[i,:,k])
    return a

def xi_weights(m,M,c,al):
    times = np.array(range(0,M-m+1))
    weights = np.zeros(M-m+1)
    weights[:c-m] = np.power(times[:c-m]/(c-m),al)
    weights[c-m:] = np.power((((M-m)*np.ones_like(times[c-m:])) - times[c-m:])/(M-c),al)
    return weights


def xi_update(states,times,a,xi_old,sample=30,al=1):
    """
    Function to update xi, given the previous xi, observations and a
    Parameters
    ----------
    states : List
        Sequence of observed states, assumed from {0,1,..S-1}
        
    times : List
        Sequence of observed jump times (in minutes from initial time 0)
        
    a : np array with shape (S,S,K)
        array of coeffients for Q matrix of model, S = #states, K = #basis functions
        
    xi_old : np.array with shape (K)
        array of partition times for piecewise constant basis functions
        
    sample : int 
        number of sampled times to maximise over, default=30
    
    
    Returns
    -------
    xi_new : np.array with shape (K)
        array of partition times for piecewise constant basis functions
    
    """
    K = a.shape[2]
    xi_new = xi_old.copy()
    ind = random.randint(0,K-1)
    extended_xi = [xi_old[-1] - 1440] + list(xi_old) + [xi_old[0] + 1440]
    low = max(extended_xi[ind],0)
    high = min(extended_xi[ind + 2],1439)
    all_times = list(range(low,high+1))
    weights = xi_weights(low,high,xi_old[ind],al)
    test_times = random.choices(all_times,weights=weights,k=min(sample,len(all_times)))
    test_times.append(xi_old[ind])
    test_times = list(np.unique(test_times))
    liks = -np.inf*np.ones(len(test_times))
    for i, t in enumerate(test_times):
        xi = xi_old
        xi[ind] = t
        liks[i] = log_l(states,times,a,xi)
    xi_new[ind] = test_times[np.argmax(liks)]
    return xi_new

def xi_mobility(i,N):
    #return 50*np.tanh((2.6*i)/N)
    return 10**((3.4*i/N) - 1.7)

# %% Simple tests

times = [0,10,300,400,550,570,1700]
states = [0,1,0,1,2,1,2]
xi_0 = [360,1080]

plt.step(times,states,where='post')
plt.show()

a = a_MLE(states,times,xi_0)

xi_old = xi_0
a_old = a
N=30
print(f'Using MLE, N={N}')
print(f'Baseline l: {log_l(states,times,a_old,xi_old)}')

for i in range(N):
    #print(f'Iteration {i+1}')
    xi_new = xi_update(states,times,a_old,xi_old,al=xi_mobility(i, N))
    #print(f'Updated xi l: {log_l(states,times,a_old,xi_new)}')
    a_new = a_MLE(states, times, xi_new)
    # print(log_l(states,times,a_old,xi_new))
    # print(a_old[:,:,0])
    # print(a_new[:,:,0])
    #print(f'Updated a l: {log_l(states,times,a_new,xi_new)}')
    print(f'xi: {xi_new}, l: {log_l(states,times,a_new,xi_new)}, al: {xi_mobility(i, N)}')
    xi_old = xi_new
    a_old = a_new
    
    
xi_0 = [360,1080]
a = a_PM(states,times,xi_0)

xi_old = xi_0
a_old = a

print(f'Using PM, N={N}')
print(f'Baseline l: {log_l(states,times,a_old,xi_old)}')
for i in range(N):
    #print(f'Iteration {i+1}')
    xi_new = xi_update(states,times,a_old,xi_old,al=xi_mobility(i, N))
    #print(f'Updated xi l: {log_l(states,times,a_old,xi_new)}')
    a_new = a_PM(states, times, xi_new)
    #print(f'Updated a l: {log_l(states,times,a_new,xi_new)}')
    # print(log_l(states,times,a_old,xi_new))
    # print(a_old[:,:,0])
    # print(a_new[:,:,0])
    print(f'xi: {xi_new}, l: {log_l(states,times,a_new,xi_new)}, al: {xi_mobility(i, N)}')
    xi_old = xi_new
    a_old = a_new