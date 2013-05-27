import numpy as np
import tables

from plexon import plexfile, psth
from riglib.nidaq import parse

def load(decoder_fname):
    """Re-load decoder from pickled object"""
    decoder = pickle.load(open(decoder_fname, 'rb'))
    return decoder


class BMI(object):
    '''A BMI object, for filtering neural data into BMI output. Should be called decoder, not BMI.'''

    def __init__(self, cells, binlen=.1, **kwargs):
        '''All BMI objects must be pickleable objects with two main methods -- the init method trains
        the decoder given the inputs, and the call method actually does real time filtering'''
        self.files = kwargs
        self.binlen = binlen
        self.units = np.array(cells).astype(np.int32)

        self.psth = psth.SpikeBin(self.units, binlen)

    def __call__(self, data, task_data=None):
        psth = self.psth(data)
        if task_data is not None:
            task_data['bins'] = psth
        return psth

    def __setstate__(self, state):
        self.psth = psth.SpikeBin(state['cells'], state['binlen'])
        del state['cells']
        self.__dict__.update(state)

    def __getstate__(self):
        state = dict(cells=self.units)
        exclude = set(['plx', 'psth'])
        for k, v in self.__dict__.items():
            if k not in exclude:
                state[k] = v
        return state

    def get_data(self):
        raise NotImplementedError


import kfdecoder
import train

class MotionBMI(BMI):
    '''Decoder object which is trained from motion data'''

    def __init__(self, cells, tslice=(None, None), **kwargs):
        super(MotionBMI, self).__init__(cells, **kwargs)
        assert 'hdf' in self.files and 'plexon' in self.files
        self.tslice = tslice

    def get_data(self):
        plx = plexfile.openFile(str(self.files['plexon']))
        rows = parse.rowbyte(plx.events[:].data)[0][:,0]
        lower, upper = 0 < rows, rows < rows.max()+1
        l, u = self.tslice
        if l is not None:
            lower = l < rows
        if u is not None:
            upper = rows < u
        self.tmask = np.logical_and(lower, upper)

        #Trim the mask to have exactly an even multiple of 4 worth of data
        if sum(self.tmask) % 4 != 0:
            midx, = np.nonzero(self.tmask)
            self.tmask[midx[-(len(midx) % 4):]] = False

        #Grab masked data, filter out interpolated data
        motion = tables.openFile(self.files['hdf']).root.motiontracker
        t, m, d = motion.shape
        motion = motion[np.tile(self.tmask, [d,m,1]).T].reshape(-1, 4, m, d)
        invalid = np.logical_or(motion[...,-1] == 4, motion[...,-1] < 0)
        motion[invalid] = 0
        kin = motion.sum(1)

        neurows = rows[self.tmask][3::4]
        neurons = np.array(list(plx.spikes.bin(neurows, self.psth)))
        if len(kin) != len(neurons):
            raise ValueError('Training data and neural data are the wrong length: %d vs. %d'%(len(kin), len(neurons)))
        return kin, neurons

class ManualBMI(MotionBMI):
    def __init__(self, states=['origin_hold', 'terminus', 'terminus_hold', 'reward'], *args, **kwargs):
        super(ManualBMI, self).__init__(*args, **kwargs)
        self.states = states

    def get_data(self):
        h5 = tables.openFile(self.files['hdf'])
        states = h5.root.motiontracker_msgs[:]
        names = dict((n, i) for i, n in enumerate(np.unique(states['msg'])))
        target = np.array([names[n] for n in self.states])
        seq = np.array([(names[n], t) for n, t, in states])

        idx = np.convolve(target, target, 'valid')
        found = np.convolve(seq[:,0], target, 'valid') == idx
        times = states[found]['time']
        if len(times) % 2 == 1:
            times = times[:-1]
        slices = times.reshape(-1, 2)
        t, m, d = h5.root.motiontracker.shape
        mask = np.ones((t/4, m, d), dtype=bool)
        for s, e in slices:
            mask[s/4:e/4] = False
        kin, neurons = super(ManualBMI, self).get_data()
        return np.ma.array(kin, mask=mask[self.tmask[3::4]]), neurons

class VelocityBMI(MotionBMI):
    def get_data(self):
        kin, neurons = super(VelocityBMI, self).get_data()
        kin[(kin[...,:3] == 0).all(-1)] = np.ma.masked
        kin[kin[...,-1] < 0] = np.ma.masked
        velocity = np.ma.diff(kin[...,:3], axis=0)
        kin = np.ma.hstack([kin[:-1,:,:3], velocity])
        return kin, neurons[:-1]

class AdaptiveBMI(object):
    def __init__(self, decoder, learner):
        self.decoder = decoder
        self.learner = learner
        self.reset()

        self.clda_input_queue = mp.Queue()
        self.clda_output_queue = mp.Queue()
        self.updater = clda.KFSmoothbatch(self.clda_input_queue, self.clda_output_queue, 
            batch_time, half_life)
        self.updater.start()

    def reset(self):
        self.decoder.reset()
        self.learner.reset()

    def is_clda_enabled(self):
        return self.learner.clda_enabled 

    def disable_clda(self):
        self.learner.disable()

    def __call__(self, spike_obs, target_pos):
        prev_state = decoder.get_state()

        # run the decoder
        decoder.predict(spike_obs, assist_level=0)
        decoded_state = decoder.get_state()
        
        # send data to learner
        if isinstance(spike_obs, np.ndarray):
            spike_counts = spike_obs
        else:
            spike_counts = decoder.bin_spikes(spike_obs)
        self.learner(spike_counts, prev_state, decoded_state, target_pos)

        try:
            new_params = self.clda_output_queue.get_nowait()
            self.decoder.update_params(new_params)
            self.learner.enable()
            print "updated params"
        except:
            pass

        if learner.is_full():
            intended_kin, spike_counts = learner.get_batch()
            rho = self.updater.rho
            clda_data = (intended_kin, spike_counts, rho, self.decoder.kf.C, self.decoder.kf.Q, drives_neurons)

            if 0:
                new_params = self.updater.calc(*clda_data)
                self.decoder.update_params(new_params)
            else:
                self.clda_input_queue.put(clda_data)
                self.learner.disable()

    def __del__(self):
        self.updater.stop()
