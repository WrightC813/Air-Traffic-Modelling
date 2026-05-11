# -*- coding: utf-8 -*-
"""
Created on Fri Apr  3 19:42:11 2026

@author: thecd
"""


import random
import numpy as np
import scipy as sp

class CTMC:
    def __init__(self):
        pass
    
    def N_val(self,states,times,xi):
        #Function compuiting number of observed jumps between each pair of states and in each time window

        S = max(states) + 1
        K = len(xi)
        k = self.k_values(times,xi)
        num = np.zeros((S,S,K))
        for i in range(1,len(states)):
            num[states[i-1],states[i],k[i]] += 1.0
            
        return num
    
    
    def D_val(self,states,times,xi):
        #Function computing total time spent in each state for each time window
        S = max(states) + 1
        K = len(xi)
        den = np.zeros((S,S,K))
        for i in range(1,len(states)):
            den[states[i-1],:,:] += np.outer(np.ones(S),self.time_in_segments(times[i-1], times[i], xi))
            
        return den
    
    
    def k_values(self,times,xi):
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
    
    
    def time_in_segments(self,T_0,T_1,xi):
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
            current_k = self.k_values([t], xi)[0]
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
    
    
    def log_l(self,states,times,a,xi):
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
        num = self.N_val(states, times, xi)
        den = self.D_val(states, times, xi)
        #eliminating negative diagonal terms
        num[num < 0] = 0
        
        term_1 = np.multiply(num,np.log(a))
        #Dealing with special case where no jumps are observed
        term_1[num == 0] = 0
        term_2 = np.multiply(a,den)
        return np.sum(term_1 - term_2)
    
    
    def a_MLE(self,states,times,xi):
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
        num = self.N_val(states, times, xi)
        den = self.D_val(states, times, xi)
        
        #In case den is zero, we set the corresponding a coefficient to 0
        a = np.divide(num,den)
        a[den == 0] = 0
        for i in range(S):
            for k in range(K):
                a[i,i,k] = -np.sum(a[i,:,k])
        return a
    
    
    def a_PM(self,states,times,xi):
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
        num = self.N_val(states, times, xi)
        num[:,:,:] += 1
        den = self.D_val(states, times, xi)
            
        #In case den is zero, posterior is improper. We default a to 0
        a = np.divide(num,den)
        a[den == 0] = 0
        for i in range(S):
            for k in range(K):
                a[i,i,k] = -np.sum(a[i,:,k])
        return a
    
    
    def xi_weights(self,m,M,c,al):
        #Function determining distribution of random search for optimal xi value
        times = np.array(range(0,M-m+1))
        weights = np.zeros(M-m+1)
        weights[:c-m] = np.power(times[:c-m]/(c-m),al)
        weights[c-m:] = np.power((((M-m)*np.ones_like(times[c-m:])) - times[c-m:])/(M-c),al)
        return weights
    
    
    def xi_mobility(self,i,N):
        #Function detetermining parameter al in computing xi weights, inspired by simulated annealing 
        #so that initially xi allowed to move far from current value but over time has less mobility
        #return 50*np.tanh((2.6*i)/N)
        return 10**((2.7*i/N) - 1.7)
    
    
    def xi_update(self,states,times,a,xi_old,sample=30,al=1):
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
        weights = self.xi_weights(low,high,xi_old[ind],al)
        test_times = random.choices(all_times,weights=weights,k=min(sample,len(all_times)))
        test_times.append(xi_old[ind])
        test_times = list(np.unique(test_times))
        liks = -np.inf*np.ones(len(test_times))
        for i, t in enumerate(test_times):
            xi = xi_old
            xi[ind] = t
            liks[i] = self.log_l(states,times,a,xi)
        xi_new[ind] = test_times[np.argmax(liks)]
        return xi_new
    
    
    def fit(self,states,times,xi,a_optim='MLE',xi_optim='anneal',N=50):
        """
        Function to fit CTMC parameters to observed states and times
        Parameters
        ----------
        states : List
            Sequence of observed states, assumed from {0,1,..S-1}
            
        times : List
            Sequence of observed jump times (in minutes from initial time 0)
            
        xi : np.array with shape (K)
            array of partition times for piecewise constant basis functions
            
        a_optim : 'MLE' or 'PM' 
            Which estimator to use for the parameters a
        xi_optim : 'anneal', fixed
            Which algorithm to use for xi optimisation
        N : int
            Number of iterations to perform
        
        """
        if a_optim == 'MLE':
            a_step = self.a_MLE
        elif a_optim == 'PM':
            a_step = self.a_PM
        else:
            print('Error: invalid value for a_optim')
            return None
        self.states = states
        self.times = times
        self.xi = xi
        self.S = max(states) + 1
        self.K = len(xi)
        self.a = a_step(self.states,self.times,self.xi)
        
        #fixed xi_optim means we treat xi as fixed, not to be optimised
        if xi_optim == 'fixed':
            print('Fitted with given xi')
            print(f'log l: {self.log_l(self.states,self.times,self.a,self.xi)}')
            err = self.model_error()
            print(f'expected L1 error: {err[0]} +- {err[1]}')
        
        #anneal xi_optim uses stochastic search with simulated annealing idea to slowly reduce 
        #mobility of the xi
        if xi_optim == 'anneal':
            for i in range(N):
                self.xi = self.xi_update(self.states,self.times,self.a,self.xi,al=self.xi_mobility(i, N))
                self.a = a_step(self.states, self.times, self.xi)
                err = self.model_error()
                print(f'Iteration {i+1}: log l: {self.log_l(self.states,self.times,self.a,self.xi)}, expected L1 error: {err[0]} +- {err[1]}')
        
        
    def q(self,i,j,t):
        #Function computing intensity function q_ij at time t, a list of times
        k_vals = self.k_values(t, self.xi)
        return self.a[i,j,k_vals]
    
    def integrate_step(self,values,partition):
        #Function computing the integral of a (left cts) step function
        #integral range determined by partition points
        #values is values at each partition point
        return np.tensordot(np.diff(partition,n=1),np.delete(values,-1,axis=0),axes=(-1,-1))
        # if len(np.shape(partition)) == 1:
        #     return np.inner(np.diff(partition,n=1),values[:-1])
        # else:
        #     diffs = np.diff(partition,n=1, axis=2)
        #     return np.matmul(diffs,values[:-1])
        
        
    def integrate_q(self,lower,upper,i,j):
        #Function computing integral of q_ij from a to b
        #Inbuilt using scipy possible, but for step function better to do by hand
        #assume lower always single value by upper could be array
        partition = np.array([lower,np.max(upper)])
        for n in range(int(np.min(lower) // 1440),int(np.max(upper) // 1440) + 1):
            partition = np.append(partition,np.array([n*1440 + x for x in self.xi]))
        partition = np.sort(partition)
        values = self.q(i,j,partition)
        #Set values outside intended range to zero to get correct integral
        values[(lower >= partition) | (partition >= upper)] = 0
        return self.integrate_step(values,partition)
        


    def sample_jump(self,start_state,start_time):
        #Generates next jump of the process, assuming we start in start_state at start_time
        rv = Custom_RV(start_time, lambda x : self.integrate_q(start_time, x, start_state, start_state))
        new_time = rv.rvs()
        del rv
        
        # if np.all(self.a[start_state,start_state,:] == 0):
        #     return start_state, np.inf
        # u = random.random()
        # new_time = sp.optimize.root_scalar(lambda t: np.log(1-u) - self.integrate_q(start_time, t, start_state, start_state),x0 = start_time, x1 = start_time + 10).root
        q = [self.q(start_state,j,[new_time])[0] for j in range(self.S)]
        if np.all(q == 0):
            return start_state, new_time
        else:
            q[start_state] = 0
            new_state = random.choices(list(range(self.S)),weights=q,k=1)[0]
            return new_state, new_time
        
    def generate_path(self, start_state, T_0, T_1):
        #Generates sample path starting in start state from time T_0 up to time T_1
        states = [start_state]
        times = [T_0]
        while times[-1] < T_1:
            s,t = self.sample_jump(states[-1], times[-1])
            states.append(s)
            times.append(t)
        return np.array(states), np.array(times[:-1] + [T_1])
    
    
    def model_error(self,N=25):
        errors = []
        for i in range(N):
            s,t = self.generate_path(self.states[0], 0, self.times[-1])
            #All partion points for the differences
            partitions = np.union1d(self.times, t)
            #Computing mask to find data values at partition times
            m_data = np.meshgrid(self.times,partitions)
            mask_data = (np.sum(m_data[1] >= m_data[0],axis=1) - np.ones_like(partitions)).astype(int)
            #Computing mask to find simulated values at partition times
            m_sim = np.meshgrid(t,partitions)
            mask_sim = (np.sum(m_sim[1] >= m_sim[0],axis=1) - np.ones_like(partitions)).astype(int)
            values = np.abs(self.states[mask_data] - s[mask_sim])
            errors.append(self.integrate_step(values, partitions)/partitions[-1])
        return np.mean(errors), np.std(errors)
            
    
class Custom_RV(sp.stats.rv_continuous):
    def __init__(self,t_0,q_int):
        sp.stats.rv_continuous.__init__(self,a=t_0)
        self.q_int = q_int
    
    def _cdf(self,x):
        return 1 - np.exp(self.q_int(x))
