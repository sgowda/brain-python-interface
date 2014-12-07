'''
HDF-saving features
'''

import time
import tempfile
import random
import traceback
import numpy as np
import fnmatch
import os
import subprocess
from riglib import calibrations, bmi
from riglib.bmi import extractor
from riglib.experiment import traits

###### CONSTANTS
sec_per_min = 60


class SaveHDF(object):
    '''
    Saves data from registered sources into tables in an HDF file
    '''
    def init(self):
        '''
        Secondary init function. See riglib.experiment.Experiment.init()
        Prior to starting the task, this 'init' starts an HDFWriter sink and 
        creates a data variable 'task_data' for the different parts of the task class to use as
        transport to the HDF file
        '''
        import tempfile
        from riglib import sink
        self.sinks = sink.sinks
        self.h5file = tempfile.NamedTemporaryFile()
        self.hdf = sink.sinks.start(self.hdf_class, filename=self.h5file.name)

        # Run the rest of the .init() functions of the custom experiment class
        # NOTE: this MUST happen before the rest of the code executes. Otherwise,
        # the dtype used to determine the task data attributes to be stored
        # to the HDF file will be incorrect/incomplete
        super(SaveHDF, self).init()    

    @property
    def hdf_class(self):
        ''' Docstring '''
        from riglib import hdfwriter
        return hdfwriter.HDFWriter

    def run(self):
        '''
        Code to execute immediately prior to the beginning of the task FSM executing, or after the FSM has finished running. 
        See riglib.experiment.Experiment.run(). This 'run' method stops the HDF sink after the FSM has finished running        
        '''
        try:
            super(SaveHDF, self).run()
        finally:
            self.hdf.stop()
    
    def join(self):
        '''
        Re-join any spawned process for cleanup
        '''
        self.hdf.join()
        super(SaveHDF, self).join()

    def set_state(self, condition, **kwargs):
        '''
        Save task state transitions to HDF

        Parameters
        ----------
        condition: string
            Name of new state to transition into. The state name must be a key in the 'status' dictionary attribute of the task

        Returns
        -------
        None
        '''
        self.hdf.sendMsg(condition)
        super(SaveHDF, self).set_state(condition, **kwargs)

    def cleanup(self, database, saveid, **kwargs):
        '''
        Docstring

        Parameters
        ----------

        Returns
        -------
        '''
        super(SaveHDF, self).cleanup(database, saveid, **kwargs)
        print "Beginning HDF file cleanup"
        print "#################%s"%self.h5file.name
        try:
            self.cleanup_hdf()
        except:
            print "\n\n\n\n\nError cleaning up HDF file!"
            import traceback
            traceback.print_exc()

        dbname = kwargs['dbname'] if 'dbname' in kwargs else 'default'
        if dbname == 'default':
            database.save_data(self.h5file.name, "hdf", saveid)
        else:
            database.save_data(self.h5file.name, "hdf", saveid, dbname=dbname)

    def _cycle(self):
        super(SaveHDF, self)._cycle()