import numpy as np
import _psth as psth

class Filter(object):
    def __init__(self, cells, binlen=.1):
        self.chans = np.array(cells).astype(np.int32)
        self.len = len(self.chans)
        psth.set_channels(self.chans.data)
        self.binlen = binlen

    def __call__(self, data):
        return psth.binspikes(self.binlen, data.data, self.len)