#!/usr/bin/python
"""
Collection of modules to simulate neural activity
"""
from __future__ import division
import os
import numpy as np

from scipy.io import loadmat

import numpy as np
from numpy.random import poisson, rand
from scipy.io import loadmat, savemat
from itertools import izip


from scipy.integrate import trapz, simps

ts_dtype = [('ts', float), ('chan', np.int32), ('unit', np.int32)]
ts_dtype_new = [('ts', float), ('chan', np.int32), ('unit', np.int32), ('arrival_ts', np.float64)]
class CosEnc(object):
    def __init__(self, n_neurons=25, mod_depth=14./0.2, baselines=10, 
        unit_inds=None, fname='', return_ts=False, DT=0.1):
        """Create neurons cosine-tuned to random directions."""

        self.return_ts = return_ts
        self.fname = fname
        self.DT = DT
        if unit_inds == None:
            unit_inds = np.arange(1, n_neurons+1)
        if fname and os.path.exists(fname):
            print "Reloading encoder from file: %s" % fname
            data = loadmat(fname)
            try:
                self.n_neurons = data['n_neurons'][0,0]
            except:
                self.n_neurons = int(data['n_neurons'])
            self.angles = data['angles'].reshape(-1)
            self.baselines = data['baselines']
            self.mod_depth = data['mod_depth']
            self.unit_inds = data['unit_inds'].ravel()
            if self.mod_depth.shape == (1,1):
                self.mod_depth = self.mod_depth[0,0]
            if self.baselines.shape == (1,1):
                self.baselines = self.baselines[0,0]
            self.pds = data['pds']
        else:
            self.n_neurons = n_neurons
            self.baselines = baselines
            self.angles = 2 * np.pi * np.random.rand(n_neurons)
            self.mod_depth = mod_depth
            self.pds = np.array([[np.cos(a), np.sin(a)] for a in self.angles])
            self.unit_inds = unit_inds
            self.save()

    def get_units(self):
        return np.array([ (int(ind/4)+1, ind % 4) for ind in self.unit_inds ])

    def __call__(self, user_input):
        """ Encode two-dimensional user input into firing rates.
        """
        if isinstance(self.baselines, np.ndarray):
            baselines = self.baselines.ravel()
        else:
            baselines = self.baselines
        rates = self.mod_depth * np.dot(self.pds, user_input) + baselines
        rates = np.array([max(r, 0) for r in rates])
        counts = poisson(rates * self.DT)

        if self.return_ts:
            ts = []
            n_neurons = self.n_neurons
            for k, ind in enumerate(self.unit_inds):
                # separate spike counts into individual time-stamps
                n_spikes = int(counts[k])
                fake_time = (self.call_count + 0.5)* 1./60
                if n_spikes > 0:
                    spike_data = [(fake_time, int(ind/4)+1, ind % 4) for m in range(n_spikes)] 
                    ts += (spike_data)

            ts = np.array(ts, dtype=ts_dtype)
            return ts
        else:
            return counts

    def save(self):
        savemat(self.fname, {'n_neurons':self.n_neurons, 'baselines':self.baselines,
            'angles':self.angles, 'pds':self.pds, 'mod_depth':self.mod_depth,
            'unit_inds':self.unit_inds})

class CLDASimCosEnc(CosEnc):
    def __init__(self, *args, **kwargs):
        super(CLDASimCosEnc, self).__init__(*args, **kwargs)
        self.call_count = 0

    def __call__(self, user_input):
        if self.call_count % 6 == 0: # TODO this assumes the neurons cannot change faster than 10 Hz
            ts_data = super(CLDASimCosEnc, self).__call__(user_input)
        elif self.return_ts:
            ts_data = np.array([])
        else:
            ts_data = np.zeros(self.n_neurons)
        self.call_count += 1
        return ts_data


class CosEncJoints(CosEnc):
    def __init__(self, link_lengths, *args, **kwargs):
        mod_depth = kwargs.pop('mod_depth', 14/0.2)
        kwargs['mod_depth'] = mod_depth/max(link_lengths)
        super(CosEncJoints, self).__init__(*args, **kwargs)

# TODO the class below is completely redundant!
class CLDASimCosEncJoints(CosEncJoints):
    def __init__(self, *args, **kwargs):
        super(CLDASimCosEncJoints, self).__init__(*args, **kwargs)
        self.call_count = 0

    def __call__(self, user_input):
        if self.call_count % 6 == 0: # TODO this assumes the neurons cannot change faster than 10 Hz
            ts_data = super(CLDASimCosEncJoints, self).__call__(user_input)
        elif self.return_ts:
            ts_data = np.array([])
        else:
            ts_data = np.zeros(self.n_neurons)
        self.call_count += 1
        return ts_data

class PointProcess():
    def __init__(self, beta, dt, tau_samples=[], K=0, eps=1e-3):
        self.beta = beta.reshape(-1, 1)
        self.dt = dt
        self.tau_samples = tau_samples
        self.K = K
        self.eps = eps
        self.i = 0
        self.j = self.i + 1
        self.X = np.zeros([0, len(beta)])
        self._reset_res()
        self.tau = np.inf
        self.rate = np.nan

    def _exp_sample(self):
        if len(self.tau_samples) > 0:
            self.tau = self.tau_samples.pop(0)
        else:
            u = np.random.rand()
            self.tau = np.log(1 - u);

    def _reset_res(self):
        self.resold = 1000
        self.resnew = np.nan

    def _integrate_rate(self):
        # integrate rate
        loglambda = np.dot(self.X[self.last_spike_ind:self.j+1, :], self.beta) #log of lambda delta
        self.rate = np.ravel(np.exp(loglambda)/self.dt)

        if len(self.rate) > 2:
            self.resnew = self.tau + simps(self.rate, dx=self.dt, even='first')
        else:
            self.resnew = self.tau + trapz(self.rate, dx=self.dt)

    def _decide(self):
        if (self.resold > 0) and (self.resnew > self.resold):
            return True
        else:
            #self.j = self.j + 1;
            self.resold = self.resnew;
            return False

    def _push(self, x_t):
        self.X = np.vstack([self.X, x_t])

    def __call__(self, x_t):
        self._push(x_t)
        if np.abs(self.resold) < self.eps:
            spiking_bin = True
        else:
            self._integrate_rate()
            spiking_bin = self._decide()

        # Handle the spike
        if spiking_bin:
            self.last_spike_ind = self.j - 1
            self._reset_res()
            self._exp_sample()
            self._integrate_rate()
            self.resold = self.resnew;

        self.j += 1
        return spiking_bin

    def _init_sampling(self, x_t):
        self._push(x_t) # initialize the observed extrinsic covariates
        self._reset_res()
        self._exp_sample()
        self.j = 1
        self.last_spike_ind = 0 # initialization

    def sim_batch(self, X, verbose=False):
        framelength = X.shape[0]
        spikes = np.zeros(framelength);

        self._init_sampling(X[0,:])
    
        while self.j < framelength:
            #spiking_bin = self(X[self.j, :])
            spiking_bin = self.__call__(X[self.j, :])
            if self.j < framelength and spiking_bin:
                spikes[self.last_spike_ind] = 1;

        return spikes


class PointProcessEnsemble(object):
    def __init__(self, beta, dt, init_state=None, tau_samples=None, eps=1e-3, 
                 hist_len=0, units=None):
        '''
        Initialize a point process ensemble
        '''
        self.n_neurons, n_covariates = beta.shape
        if init_state == None:
            init_state = np.hstack([np.zeros(n_covariates - 1), 1])
        if tau_samples == None:
            tau_samples = [[]]*self.n_neurons
        point_process_units = []
        for k in range(self.n_neurons):
            point_proc = PointProcess(beta[k,:], dt, tau_samples=tau_samples[k])
            #point_proc = PointProcess(beta[:,k], dt, tau_samples=tau_samples[k])
            point_proc._init_sampling(init_state)
            point_process_units.append(point_proc)
        self.point_process_units = point_process_units
        if units == None:
            self.units = np.vstack([(x, 1) for x in range(self.n_neurons)])
        else:
            self.units = units

    def get_units(self):
        return self.units

    def __call__(self, x_t):
        x_t = np.hstack([x_t, 1])
        counts = np.array(map(lambda unit: unit(x_t), self.point_process_units)).astype(int)
        return counts

class CLDASimPointProcessEnsemble(PointProcessEnsemble):
    '''
    PointProcessEnsemble intended to be called at 60 Hz and return simulated
    spike timestamps at 180 Hz
    '''
    def __init__(self, *args, **kwargs):
        super(CLDASimPointProcessEnsemble, self).__init__(*args, **kwargs)
        self.call_count = -1

    def __call__(self, x_t):
        '''
        Ensemble is called at 60 Hz but expects the timestamps to reflect spike
        bins determined at 180 Hz
        '''
        ts_data = []
        for k in range(3):
            counts = super(CLDASimPointProcessEnsemble, self).__call__(x_t)
            nonzero_units, = np.nonzero(counts)
            fake_time = self.call_count * 1./60 + (k + 0.5)*1./180
            for unit_ind in nonzero_units:
                ts = (fake_time, self.units[unit_ind, 0], self.units[unit_ind, 1], fake_time)
                ts_data.append(ts)

        self.call_count += 1
        return np.array(ts_data, dtype=ts_dtype_new)
        

def load_ppf_encoder_2D_vel_tuning(fname, dt=0.005):
    data = loadmat(fname)
    beta = data['beta']
    beta = np.vstack([beta[1:, :], beta[0,:]]).T
    n_neurons = beta.shape[0]

    init_state = np.array([0., 0, 1])

    try:
        tau_samples = [data['tau_samples'][0][k].ravel().tolist() for k in range(n_neurons)]
    except:
        tau_samples = []
    encoder = PointProcessEnsemble(beta, dt, init_state=init_state, tau_samples=tau_samples)
    return encoder

def load_ppf_encoder_2D_vel_tuning_clda_sim(fname, dt=0.005):
    data = loadmat(fname)
    beta = data['beta']
    beta = np.vstack([beta[1:, :], beta[0,:]]).T
    encoder = CLDASimPointProcessEnsemble(beta, dt)
    return encoder

def min_jerk_movement(vel, time, starting_pos, ending_pos, t0, D):
    A = ending_pos - starting_pos
    thisrng, = np.nonzero(np.logical_and(time > t0, time < t0+D))
    t = time[thisrng]
    nt = (t-t0)/D
    vel[thisrng, 0:3] = starting_pos + np.outer(A, 6*nt**5 - 15*nt**4 + 10*nt**3).T
    vel[thisrng, 3:6] = np.outer(A, 1./D * (30 * nt**4 -60 * nt**3 + 30 * nt**2)).T
    return vel

def sim_endpt_traj(targets, durations, DT=0.1, inter_target_delay=0.3):
    n_targets = len(targets - 1)
    total_time = n_targets*inter_target_delay + sum(durations[:n_targets])
    T = total_time / DT
    time = np.arange(T) * DT
    vel = np.zeros([T, 6])
    t0 = 0
    for starting_pos, ending_pos, D in izip(targets[:-1], targets[1:], durations):
        vel = min_jerk_movement(vel, time, starting_pos, ending_pos, t0, D)
        t0 += D + inter_target_delay
    
    return vel

def rec_to_normal(arr):
    '''
    Helper function to convert a numpy record array to a normal array
    '''
    new_dtype = (np.float64, len(arr.dtype))
    return arr.view(new_dtype).reshape(-1, len(arr.dtype))

def sim_joint_traj(targets, durations, link_lengths, shoulder_anchor, DT=0.1, inter_target_delay=0.3):
    kin = sim_endpt_traj(targets, durations)
    
    # calculate joint velocities
    from riglib.stereo_opengl import ik
    joint_angles, joint_vel = ik.inv_kin_2D(kin[:,0:3] - shoulder_anchor, 
        link_lengths[1], link_lengths[0], kin[:,3:6])
    
    joint_kin = np.hstack([rec_to_normal(joint_angles), rec_to_normal(joint_vel)])
    return joint_kin
    
