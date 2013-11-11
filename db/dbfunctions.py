import os
import sys
import json
import numpy as np
import datetime
import pickle
import cPickle
import db.paths
import tables
import matplotlib.pyplot as plt
import time, datetime
from scipy.stats import nanmean

os.environ['DJANGO_SETTINGS_MODULE'] = 'db.settings'
sys.path.append(os.path.expanduser("~/code/bmi3d/db/"))
from tracker import models
from db import paths

def get_task_entry(entry_id):
    '''
    Returns the task entry object from the database with the specified entry_id.
    entry_id = int
    '''
    return models.TaskEntry.objects.get(pk=entry_id)

def lookup_task_entries(*task_entry):
    '''
    Enable multiple ways to specify a task entry, e.g. by primary key or by
    object
    '''
    if len(task_entry) == 1:
        task_entry = task_entry[0]
        if isinstance(task_entry, models.TaskEntry):
            pass
        elif isinstance(task_entry, int):
            task_entry = get_task_entry(task_entry)
        return task_entry
    else:
        return [lookup_task_entries(x) for x in task_entry]


def get_task_id(name):
    '''
    Returns the task ID for the specified task name.
    '''
    return models.Task.objects.get(name=name).pk


def get_decoder_entry(entry):
    '''Returns the database entry for the decoder used in the session. Argument can be a task entry
    or the ID number of the decoder entry itself.
    '''
    if isinstance(entry, int):
        return models.Decoder.objects.get(pk=entry)
    else:
        params = json.loads(entry.params)
        if 'bmi' in params:
            return models.Decoder.objects.get(pk=params['bmi'])
        else:
            return None

def get_decoder_name(entry):
    ''' 
    Returns the filename of the decoder used in the session.
    Takes TaskEntry object.
    '''
    entry = lookup_task_entries(entry)
    decid = json.loads(entry.params)['bmi']
    return models.Decoder.objects.get(pk=decid).path

def get_decoder_name_full(entry):
    entry = lookup_task_entries(entry)
    decoder_basename = get_decoder_name(entry)
    return os.path.join(paths.data_path, 'decoders', decoder_basename)

def get_decoder(entry):
    entry = lookup_task_entries(entry)
    filename = get_decoder_name_full(entry)
    dec = pickle.load(open(filename, 'r'))
    dec.db_entry = get_decoder_entry(entry)
    dec.name = dec.db_entry.name
    return dec

def get_params(entry):
    '''
    Returns a dict of all task params for session.
    Takes TaskEntry object.
    '''
    return json.loads(entry.params)

def get_task_name(entry):
    '''
    Returns name of task used for session.
    Takes TaskEntry object.
    '''
    return models.Task.objects.get(pk=entry.task_id).name
    
def get_date(entry):
    '''
    Returns date and time of session (as a datetime object).
    Takes TaskEntry object.
    '''
    return entry.date
    
def get_notes(entry):
    '''
    Returns notes for session.
    Takes TaskEntry object.
    '''
    return entry.notes
    
def get_subject(entry):
    '''
    Returns name of subject for session.
    Takes TaskEntry object.
    '''
    return models.Subject.objects.get(pk=entry.subject_id).name
    
def get_length(entry):
    '''
    Returns length of session in seconds.
    Takes TaskEntry object.
    '''
    report = json.loads(entry.report)
    return report[-1][2]-report[0][2]
    
def get_success_rate(entry):
    '''
    Returns (# of trials rewarded)/(# of trials intiated).
    Takes TaskEntry object.
    '''
    report = json.loads(entry.report)
    total=0.0
    rew=0.0
    for s in report:
        if s[0]=='reward':
            rew+=1
            total+=1
        if s[0]=='hold_penalty' or s[0]=='timeout_penalty':
            total+=1
    return rew/total

def get_initiate_rate(entry):
    '''
    Returns average # of trials initated per minute.
    Takes TaskEntry object.
    '''
    length = get_length(entry)
    report = json.loads(entry.report)
    count=0.0
    for s in report:
        if s[0]=='reward' or s[0]=='hold_penalty' or s[0]=='timeout_penalty':
            count+=1
    return count/(length/60.0)

def get_reward_rate(entry):
    '''
    Returns average # of trials completed per minute.
    Takes TaskEntry object.
    '''
    length = get_length(entry)
    report = json.loads(entry.report)
    count=0.0
    for s in report:
        if s[0]=='reward':
            count+=1
    return count/(length/60.0)
    
def get_completed_trials(entry):
    '''
    Returns # of trials rewarded.
    Takes TaskEntry object.
    '''
    report = json.loads(entry.report)
    count1=0.0
    for s in report:
        if s[0]=='reward':
            count1+=1
    return count1
    
def get_param(entry, name):
    '''
    Returns the value of a specific parameter in the param list. Takes
    TaskEntry object and string for exact param name.
    '''
    params = get_params(entry)
    return params[name]
    
def session_summary(entry):
    '''
    Prints a summary of info about session.
    Takes TaskEntry object.
    '''
    entry = lookup_task_entries(entry)
    print "Subject: ", get_subject(entry)
    print "Task: ", get_task_name(entry)
    print "Date: ", str(get_date(entry))
    hours = np.floor(get_length(entry)/3600)
    mins = np.floor(get_length(entry)/60) - hours*60
    secs = get_length(entry) - mins*60
    print "Length: " + str(int(hours))+ ":" + str(int(mins)) + ":" + str(int(secs))
    try:
        print "Assist level: ", get_param(entry,'assist_level')
    except:
        print "Assist level: 0"
    print "Completed trials: ", get_completed_trials(entry)
    print "Success rate: ", get_success_rate(entry)*100, "%"
    print "Reward rate: ", get_reward_rate(entry), "trials/minute"
    print "Initiate rate: ", get_initiate_rate(entry), "trials/minute"
    
def query_daterange(startdate, enddate=datetime.date.today()):
    '''
    Returns QuerySet for task entries within date range (inclusive). startdate and enddate
    are date objects. End date is optional- today's date by default.
    '''
    return models.TaskEntry.objects.filter(date__gte=startdate).filter(date__lte=enddate)
    
def get_hdf_file(entry):
    '''
    Returns the name of the hdf file associated with the session.
    '''
    hdf = models.System.objects.get(name='hdf')
    q = models.DataFile.objects.filter(entry_id=entry.id).filter(system_id=hdf.id)
    if len(q)==0:
        return None
    else:
        try:
            return os.path.join(db.paths.rawdata_path, hdf.name, q[0].path)
        except:
            return q[0].path

def get_hdf(entry):
    '''
    Return hdf opened file
    '''
    entry = lookup_task_entries(entry)
    hdf_filename = get_hdf_file(entry)
    hdf = tables.openFile(hdf_filename)
    return hdf

def get_plx_file(entry):
    '''
    Returns the name of the plx file associated with the session.
    '''
    entry = lookup_task_entries(entry)
    plexon = models.System.objects.get(name='plexon')
    q = models.DataFile.objects.filter(entry_id=entry.id).filter(system_id=plexon.id)
    if len(q)==0:
        return None
    else:
        try:
            import db.paths
            return os.path.join(db.paths.data_path, plexon.name, q[0].path)
        except:
            return q[0].path
        
def get_plx2_file(entry):
    '''
    Returns the name of the plx2 file associated with the session.
    '''
    plexon = models.System.objects.get(name='plexon2')
    q = models.DataFile.objects.filter(entry_id=entry.id).filter(system_id=plexon.id)
    if len(q)==0:
        return None
    else:
        try:
            import db.paths
            return os.path.join(db.paths.data_path, plexon.name, q[0].path)
        except:
            return q[0].path
        
def get_bmiparams_file(entry):
    '''
    Returns the name of the bmi parameter update history file associated with the session.
    '''
    entry = lookup_task_entries(entry)
    bmi_params = models.System.objects.get(name='bmi_params')
    q = models.DataFile.objects.filter(entry_id=entry.id).filter(system_id=bmi_params.id)
    if len(q)==0:
        return None
    else:
        try:
            import db.paths
            return os.path.join(db.paths.data_path, bmi_params.name, q[0].path)
        except:
            return q[0].path


def get_decoder_parent(decoder):
    '''
    decoder = database record of decoder object
    '''
    entryid = decoder.entry_id
    te = get_task_entry(entryid)
    return get_decoder_entry(te)

def get_decoder_sequence(decoder):
    '''
    decoder = database record of decoder object
    ''' 
    parent = get_decoder_parent(decoder)
    if parent is None:
        return [decoder]
    else:
        return [decoder] + get_decoder_sequence(parent)

def search_by_date(date, subj=None):
    '''
    Get all the task entries for a particular date
    '''
    kwargs = dict(date__year=date.year, date__month=date.month, 
                  date__day=date.day)
    if isinstance(subj, str) or isinstance(subj, unicode):
        kwargs['subject__name__startswith'] = str(subj)
    elif subj is not None:
        kwargs['subject__name'] = subj.name
    return models.TaskEntry.objects.filter(**kwargs)

def search_by_decoder(decoder):
    '''
    Returns task entries that used specified decoder. Decoder argument can be
    decoder entry or entry ID.
    '''
    if isinstance(decoder, int):
        decid = decoder
    else:
        decid = decoder.id
    return models.TaskEntry.objects.filter(params__contains='"bmi": '+str(decid))

def search_by_units(unitlist, decoderlist = None, exact=False):
    '''
    Returns decoder entries that contain the specified units. If exact is True,
    returns only decoders whose unit lists match unitlist exactly, otherwise
    returns decoders that contain units in unitlist in addition to others. If
    given a list of decoder entries, only searches within those, otherwise searches
    all decoders in database.
    '''
    if decoderlist is not None:
        all_decoders = decoderlist
    else:
        all_decoders = models.Decoder.objects.all()
    subset = set(tuple(unit) for unit in unitlist)
    dec_list = []
    for dec in all_decoders:
        try:
            decobj = cPickle.load(open(db.paths.data_path+'/decoders/'+dec.path))
            decset = set(tuple(unit) for unit in decobj.units)
            if subset==decset:
                dec_list = dec_list + [dec]
            elif not exact and subset.issubset(decset):
                dec_list = dec_list + [dec]
        except:
            pass
    return dec_list



def get_code_version():
    import os
    git_version_hash = os.popen('bmi3d_git_hash').readlines()
    git_version_hash = git_version_hash[0].rstrip('\n')
    return git_version_hash

def get_task_entries_by_date(subj=None, date=datetime.date.today()):
    '''
    Get all the task entries for a particular date
    '''
    if isinstance(date, datetime.date):
        kwargs = dict(date__year=date.year, date__month=date.month,
                      date__day=date.day)
    elif isinstance(date, tuple) and len(date) == 3:
        kwargs = dict(date__year=date[0], date__month=date[1],
                      date__day=date[2])
    elif isinstance(date, tuple) and len(date) == 2:
        kwargs = dict(date__year=2013, date__month=date[0],
                      date__day=date[1])
    if isinstance(subj, str) or isinstance(subj, unicode):
        kwargs['subject__name__startswith'] = str(subj)
    elif subj is not None:
        kwargs['subject__name'] = subj.name
    return map(TaskEntry, models.TaskEntry.objects.filter(**kwargs))

def load_decoder_from_record(rec):
    full_path = os.path.join(paths.data_path, 'decoders', rec.path)
    dec = pickle.load(open(full_path))
    dec.db_entry = rec
    dec.name = rec.name
    return dec

def load_last_decoder():
    '''
    Returns the decoder object corresponding to the last decoder trained and
    added to the database
    '''
    all_decoder_records = models.Decoder.objects.all()
    record = all_decoder_records[len(all_decoder_records)-1]
    return load_decoder_from_record(record)

def get_decoders_trained_in_block(task_entry):
    task_entry = lookup_task_entries(task_entry)
    records = models.Decoder.objects.filter(entry_id=task_entry.id)
    decoder_objects = map(load_decoder_from_record, records)
    if len(decoder_objects) == 1: decoder_objects = decoder_objects[0]
    return decoder_objects

class TaskEntry(object):
    '''
    Wrapper class for the TaskEntry django class
    '''
    def __init__(self, task_entry_id):
        self.id = task_entry_id
        self.record = lookup_task_entries(task_entry_id)
        self.params = json.loads(self.record.params)
        self.date = self.record.date
        self.notes = self.record.notes
        self.subject = models.Subject.objects.get(pk=self.record.subject_id).name

    @property
    def hdf(self):
        try:
            return self.hdf_file
        except:
            hdf_filename = get_hdf_file(self.record)
            self.hdf_file = tables.openFile(hdf_filename)
            return self.hdf_file

    @property
    def task(self):
        return self.record.task

    @property
    def decoder(self):
        if not hasattr(self, '_decoder_obj'):
            self._decoder_obj = get_decoder(self.record)
        return self._decoder_obj

    @property
    def clda_param_hist(self):
        if not hasattr(self, '_clda_param_hist'):
            self._clda_param_hist = np.load(get_bmiparams_file(self.record))
        return self._clda_param_hist

    @property
    def length(self):
        return get_length(self.record)
    
    @property
    def plx_file(self):
        return get_plx_file(self.record)

    @property
    def plx2_file(self):
        return get_plx2_file(self.record)

    @property
    def name(self):
        # TODO this needs to be hacked because the current way of determining a 
        # a filename depends on the number of things in the database, i.e. if 
        # after the fact a record is removed, the number might change. read from
        # the file instead
        return str(os.path.basename(self.plx_file).rstrip('.plx'))

    def __str__(self):
        return self.record.__str__()

    def __repr__(self):
        return self.record.__repr__()
