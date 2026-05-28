# -*- coding: utf-8 -*-
"""
Created on Fri Apr  3 19:42:11 2026

@author: thecd
"""


import random
import numpy as np
import scipy as sp
import bisect

class CTMC:
    def __init__(self):
        self.S = 0
        self.K = 0
        self.xi = []
        self.a = np.ones((1,1,1))
        self.states = []
        self.times = []
        self.coeff_struct = None
    
    def N_val(self):
        #Function compuiting number of observed jumps between each pair of states and in each time window

        k = self.k_values(self.times)
        num = np.zeros((self.S,self.S,self.K))
        for i in range(1,len(self.states)):
            num[self.states[i-1],self.states[i],k[i]] += 1.0
            
        return num
    
    
    def D_val(self):
        #Function computing total time spent in each state for each time window

        den = np.zeros((self.S,self.S,self.K))
        for i in range(1,len(self.states)):
            den[self.states[i-1],:,:] += np.outer(np.ones(self.S),self.time_in_segments(self.times[i-1], self.times[i]))
            
        return den
    
    
    def k_values(self,times):
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
        for i in range(len(times)):
            k_indices[i] = (bisect.bisect(self.xi,times[i] % 1440) - 1) % self.K
            
        return k_indices
    
    
    def time_in_segments(self,T_0,T_1):
        """
        Function computing how much time between T_0 and T_1 spent in each segment
        Parameters
        ----------
        T_0 : float
            start time
        
        T_1 : float
            end time
        

        Returns
        -------
        seg_times : np.array with shape (K)
            array of times spent in each segment
        """
        seg_times = np.zeros(self.K)
        t = T_0
        while t < T_1:
            current_k = self.k_values([t])[0]
            if current_k == self.K-1:
                new_t = t + (self.xi[0] - (t%1440))
                if (t%1440) > self.xi[0]:
                    new_t += 1440
            else:
                new_t = t + (self.xi[current_k + 1] - (t%1440))
            time = min([new_t - t,T_1 - t])
            seg_times[current_k] += time
            if new_t <= t:
                break
            t = new_t
            
        return seg_times
    
    
    def log_l(self):
        """
        Function to compute the log likelihood of the model

        Returns
        -------
        l : float
            Log likelihood of the model

        """
        num = self.N_val()
        den = self.D_val()
        #eliminating negative diagonal terms
        num[num < 0] = 0
        a1 = self.a.copy()
        a1[num==0] = 1
        
        term_1 = np.multiply(num,np.log(a1))
        #Dealing with special case where no jumps are observed
        term_1[num == 0] = 0
        term_2 = np.multiply(self.a,den)
        return np.sum(term_1 - term_2)
    
    
    def a_MLE(self):
        """
        Function to find the MLE estimator for the coefficients a, given the observations and xi
        Parameters
        ----------
        states : List
            Sequence of observed states, assumed from {0,1,..S-1}
            
        times : List
            Sequence of observed jump times (in minutes from initial time 0)
        """

        num = self.N_val()
        den = self.D_val()
        #If applicable, create pooled estimates using coeff_struct array
        if np.any(self.coeff_struct):
            vs = np.unique(self.coeff_struct)
            for v in vs:
                inds = np.where(self.coeff_struct==v)
                if v == 0:
                    num[inds[0],inds[1],:] = 0
                else:
                    num[inds[0],inds[1],:] = np.outer(np.ones(len(inds[0])),np.sum(num[inds[0],inds[1],:],axis=(0)))
                    den[inds[0],inds[1],:] = np.outer(np.ones(len(inds[0])),np.sum(den[inds[0],inds[1],:],axis=(0)))
        a = np.divide(num,den)
        #In case den is zero, we set the corresponding a coefficient to 0  
        a[den == 0] = 0
        #Setting diagonal entry, which is determined by rest of the parameters
        for i in range(self.S):
            for k in range(self.K):
                a[i,i,k] = -np.sum(a[i,:,k])
                
        self.a = a
        return None
    
    
    def a_PM(self):
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
        """
        num = self.N_val()
        den = self.D_val()
        
        if np.any(self.coeff_struct):
            vs = np.unique(self.coeff_struct)
            for v in vs:
                inds = np.where(self.coeff_struct==v)
                if v == 0:
                    num[inds] = 0
                else:
                    num[inds[0],inds[1],:] = np.outer(np.ones(len(inds[0])),np.sum(num[inds[0],inds[1],:],axis=(0))) + np.ones((len(inds[0]),self.K))
                    den[inds[0],inds[1],:] = np.outer(np.ones(len(inds[0])),np.sum(den[inds[0],inds[1],:],axis=(0)))
        else:
            num[:,:,:] += 1
            
        a = np.divide(num,den)
        #In case den is zero, posterior is improper. We default a to 0
        a[den == 0] = 0
        for i in range(self.S):
            for k in range(self.K):
                a[i,i,k] = -np.sum(a[i,:,k])
                
        self.a = a
    
    
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
    
    
    def xi_update(self,sample=30,al=1):
        """
        Function to update xi, given the previous xi, observations and a
        Parameters
        ----------
        sample : int 
            number of sampled times to maximise over, default=30
            
        al : float
            parameter dictating how much the value is encouraged to move, default=1
        

        
        """
        ind = random.randint(0,self.K-1)
        extended_xi = [self.xi[-1] - 1440] + list(self.xi) + [self.xi[0] + 1440]
        low = max(extended_xi[ind],0)
        high = min(extended_xi[ind + 2],1439)
        all_times = list(range(low,high+1))
        weights = self.xi_weights(low,high,self.xi[ind],al)
        test_times = random.choices(all_times,weights=weights,k=min(sample,len(all_times)))
        test_times.append(self.xi[ind])
        test_times = list(np.unique(test_times))
        liks = -np.inf*np.ones(len(test_times))
        for i, t in enumerate(test_times):
            self.xi[ind] = t
            liks[i] = self.log_l()
        self.xi[ind] = test_times[np.argmax(liks)]
    
    
    def fit(self,states,times,xi,a_optim='MLE',xi_optim='anneal',N=50,coeff_struct=None):
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
            
        xi_optim : 'anneal', 'fixed', 'random'
            Which algorithm to use for xi optimisation
            
        N : int
            Number of iterations to perform for anneal optimisation
        
        """
        if a_optim == 'MLE':
            a_step = self.a_MLE
        elif a_optim == 'PM':
            a_step = self.a_PM
        else:
            print('Error: invalid value for a_optim')
            return None
    
        #Set object parameters
        #observed states and times
        self.states = states
        self.times = times
        #time partition points
        self.xi = xi
        #number of states and time partitions
        self.S = max(states) + 1
        self.K = len(xi)
        #coefficient structure, if any (i.e. which are set to zero or to be equal)
        self.coeff_struct = coeff_struct
        
        a_step()
        
        #fixed xi_optim means we treat xi as fixed, not to be optimised
        if xi_optim == 'fixed':
            pass
            
        
        #anneal xi_optim uses stochastic search with simulated annealing idea to slowly reduce 
        #mobility of the xi
        elif xi_optim == 'anneal':
            for i in range(N):
                self.xi_update(al=self.xi_mobility(i, N))
                a_step()
                #err = self.model_error()
                print(f'Iteration {i+1}: log l: {self.log_l()}')#, expected L1 error: {err[0]} +- {err[1]}')
        
        #uses brute force random search and selects best xi
        elif xi_optim == 'random':
            #Include given xi, allows for keeping track of best so far over multiple calls of fit
            xi_list = [self.xi]
            #err_list = [self.model_error()]
            log_l_list = [self.log_l()]
            for i in range(N):
                self.xi = np.sort(random.sample(list(range(0,1440)),k=self.K))
                a_step()
                xi_list.append(self.xi)
                #err_list.append(self.model_error())
                log_l_list.append(self.log_l())
                print(f'Iteration {i+1}: log l: {self.log_l()}')
            self.xi = xi_list[np.argmax(log_l_list)]
            a_step()
        else:
            print('Error: invalid value for xi_optim')
            return None
        
        
        return self.model_error(), self.log_l()
        
    def q(self,i,j,t):
        #Function computing intensity function q_ij at time t, a list of times
        k_vals = self.k_values(t)
        return self.a[i,j,k_vals]
    
    def integrate_step(self,values,partition):
        #Function computing the integral of a (left cts) step function
        #integral range determined by partition points
        #values is values at each partition point
        return np.tensordot(np.diff(partition,n=1),np.delete(values,-1,axis=0),axes=1)
        
    def integrate_q(self,lower,upper,i,j):
        #Function computing integral of q_ij from a to b
        #Inbuilt using scipy possible, but for step function better to do by hand
        #assume lower always single value by upper could be array
        partition = np.array([lower,np.max(upper)])
        for n in range(int(np.min(lower) // 1440),int(np.max(upper) // 1440) + 1):
            partition = np.append(partition,np.array([n*1440 + x for x in self.xi]))
        partition = np.sort(partition)
        values = np.outer(self.q(i,j,partition),np.ones_like(upper))
        #Set values outside intended range to zero to get correct integral
        m = np.meshgrid(upper,partition)
        values[(lower > np.outer(partition,np.ones_like(upper))) | (m[1] > m[0])] = 0
        return self.integrate_step(values,partition)
        
    
    
    def jump_time(self,state,time):
        #Function to compute time of next jump. Using custom sampling procedure as both inverse cdf and rejection sampling don't work in this case
        probs = []
        partitions = [time]
        int_q = 0
        chosen = False
        #to replace by some max number of iterations
        for i in range(len(self.xi)*3):
            q = self.q(state,state,[partitions[-1]])[0]
            n = int(partitions[-1] // 1440)
            next_parts = sorted([float(n*1440 + x) for x in self.xi] + [float((n+1)*1440 + x) for x in self.xi])
            less = [p > partitions[-1] for p in next_parts]
            partitions.append(next_parts[less.index(True)])
            int_add = q*(partitions[-1] - partitions[-2])
            p = (1-np.exp(int_add))*np.exp(int_q)
            probs.append(p)
            int_q += int_add
            
            
            if random.random() <= p/(1-sum(probs[:-1])):
                chosen = True
                break
            
        if not chosen:
            print('Jump time exceeds 3 days, set to inf')
            return np.inf
        
        u = random.random()
        return partitions[-2] + np.log(1 - u + u*np.exp(int_add))/q

    def sample_jump(self,start_state,start_time):
        #Generates next jump of the process, assuming we start in start_state at start_time
        # rv = Custom_RV(start_time, lambda x : self.integrate_q(start_time, x, start_state, start_state))
        # new_time = rv.rvs()
        # del rv
        if np.all(self.q(start_state,start_state,self.xi) == 0):
            print('Hit absorbing state')
            return start_state, np.inf
        new_time = self.jump_time(start_state, start_time)
        if new_time == np.inf:
            return start_state, np.inf
       
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
        return np.mean(errors), np.std(errors,ddof=1)/np.sqrt(N)
    
    
    def solve_forward_eq(self,t_0,t_1,P_0):
        #Solves backwards equation for transition semi-group using implicit Euler scheme
        #Array of all xi times plus start and end time
        discon = sorted([t_0,t_1] + [1440*n + x for x in self.xi for n in range(t_0//1440,t_1//1440 + 1)])
        discon = discon[bisect.bisect(discon,t_0) - 1:bisect.bisect_left(discon,t_1)+1]
        #times where we estimate solution
        sol_times = [t_0]
        P = np.array(P_0).reshape((self.S,1))
        #Loop over each time interval where Q is constant
        for i in range(len(discon) - 1):
            #time step
            h = (discon[i+1] - discon[i])/(np.ceil(discon[i+1] - discon[i])*5)
            steps = int((discon[i+1] - discon[i])/h)
            sol_times += [discon[i] + (n+1)*h for n in range(steps)]
            k_val = self.k_values([discon[i]])[0]
            M = np.identity(self.S) - h*self.a[:,:,k_val]
            #Using QR decomposition as we solve system many times
            Q, R = np.linalg.qr(M.T)
            for k in range(steps):
                P_step = sp.linalg.solve_triangular(R,Q.T @ P[:,-1]).reshape((self.S,1))
                P = np.hstack([P,P_step])
                
        return sol_times, P
            
            
            
            
        
