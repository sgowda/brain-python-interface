'''
HTML rendering 'view' functions for Django web interface. Retreive data from database to put into HTML format.
'''

import json

from django.template import RequestContext
from django.shortcuts import render_to_response, render
from django.http import HttpResponse

from .models import TaskEntry, Task, Subject, Feature, Generator

from config import namelist
from . import exp_tracker

import datetime

def main(request):
    return render(request, "main.html", dict())

def list_exp_history(request):
    '''
    Top-level view called when browser pointed at webroot

    Parameters
    ----------
    request: HTTPRequest instance
        No data needs to be extracted from this request

    Returns 
    -------
    Django HTTPResponse instance
    '''
    print("views.list: new root request received")
    td = datetime.timedelta(days=60)
    start_date = datetime.date.today() - td
    # entries = TaskEntry.objects.filter(visible=True).order_by('-date') # date__gt=start_date, 
    # entries = TaskEntry.objects.all()[:200][::-1]
    entries = TaskEntry.objects.filter(visible=True).order_by('-date')[:200]

    
    for k in range(0, len(entries)):
        ent = entries[k]
        if k == 0 or not entries[k].date.date() == entries[k-1].date.date():
            ent.html_date = ent.date.date()
        else:
            ent.html_date = None
        ent.html_time = ent.date.time()

    ## Determine how many rows the date should span
    last = -1
    for k, ent in enumerate(entries[::-1]):
        if ent.html_date:
            ent.rowspan = k - last
            last = k

    tasks = Task.objects.filter(visible=True).order_by("name")

    epoch = datetime.datetime.utcfromtimestamp(0)
    for entry in entries:
        tdiff = entry.date - epoch
        if tdiff.days % 2 == 0:
            entry.bgcolor = '#E1EEf4'
        else:
            entry.bgcolor = '#FFFFFF'

    subjects = Subject.objects.all().order_by("name")
    features = Feature.objects.filter(visible=True).order_by("name")
    generators = Generator.objects.filter(visible=True).order_by("name")
    hostname = request.get_host()

    fields = dict(
        entries=entries, 
        subjects=subjects, 
        tasks=tasks, 
        features=features, 
        generators=generators,
        hostname=hostname,
        bmi_update_rates=namelist.bmi_update_rates,
        state_spaces=namelist.bmi_state_space_models,
        bmi_algorithms=namelist.bmi_algorithms,
        extractors=namelist.extractors,
        default_extractor=namelist.default_extractor,
        pos_vars=namelist.bmi_training_pos_vars,      # 'pos_vars' indicates which column of the task HDF table to look at to extract kinematic data 
        kin_extractors=namelist.kin_extractors,       # post-processing methods on the selected kinematic variable
        n_blocks=len(entries),
        #zscores=namelist.zscores,
    )

    # this line is important--this is needed so the Track object knows if the task has ended in an error
    # TODO there's probably some better way of doing this within the multiprocessing lib (some code to run after the process has terminated)
    tracker = exp_tracker.get()
    tracker.update_alive()

    if tracker.task_proxy is not None:
        fields['running'] = tracker.task_proxy.saveid

    resp = render_to_response('list.html', fields, RequestContext(request))

    print("views.list: resp done!")
    return resp

def listall(request):
    '''
    Top-level view called when browser pointed at WEBROOT/all

    Parameters
    ----------
    request: HTTPRequest instance
        No data needs to be extracted from this request

    Returns 
    -------
    Django HTTPResponse instance
    '''
    entries = TaskEntry.objects.all().order_by("-date")

    epoch = datetime.datetime.utcfromtimestamp(0)
    for entry in entries:
        tdiff = entry.date - epoch
        if tdiff.days % 2 == 0:
            entry.bgcolor = '#E1EEf4'
        else:
            entry.bgcolor = '#FFFFFF'#'#dae5f4'


    fields = dict(
        entries=entries, 
        subjects=Subject.objects.all().order_by("name"), 
        tasks=Task.objects.filter(visible=True).order_by("name"), 
        features=Feature.objects.filter(visible=True).order_by("name"), 
        generators=Generator.objects.filter(visible=True).order_by("name"),
        hostname=request.get_host(),
        bmi_update_rates=namelist.bmi_update_rates,
        state_spaces=namelist.bmi_state_space_models,
        bmi_algorithms=namelist.bmi_algorithms,
        extractors=namelist.extractors,
        default_extractor=namelist.default_extractor,
        pos_vars=namelist.bmi_training_pos_vars,
        n_blocks=len(entries),
    )
    tracker = exp_tracker.get()
    if tracker.task_proxy is not None:
        fields['running'] = tracker.task_proxy.saveid
    return render_to_response('list.html', fields, RequestContext(request))

def listdb(request, dbname='default', subject=None, task=None):
    '''
    Top-level view called when browser pointed at WEBROOT/dbname/DBNAME, 
    to list the task entries in a particular database

    Parameters
    ----------
    request: HTTPRequest instance
        No data needs to be extracted from this request

    Returns 
    -------
    Django HTTPResponse instance
    '''
    filter_kwargs = dict(visible=True)
    if not (subject is None) and isinstance(subject, str):
        filter_kwargs['subject__name'] = subject
    if not (task is None) and isinstance(task, str):
        filter_kwargs['task__name'] = task

    print(filter_kwargs)

    entries = TaskEntry.objects.using(dbname).filter(**filter_kwargs).order_by("-date")
    _color_entries(entries)

    fields = dict(
        entries=entries, 
        subjects=Subject.objects.using(dbname).all().order_by("name"), 
        tasks=Task.objects.using(dbname).filter(visible=True).order_by("name"), 
        features=Feature.objects.using(dbname).filter(visible=True).order_by("name"), 
        generators=Generator.objects.using(dbname).filter(visible=True).order_by("name"),
        hostname=request.get_host(),
        bmi_update_rates=namelist.bmi_update_rates,
        state_spaces=namelist.bmi_state_space_models,
        bmi_algorithms=namelist.bmi_algorithms,
        extractors=namelist.extractors,
        default_extractor=namelist.default_extractor,
        pos_vars=namelist.bmi_training_pos_vars,
        n_blocks=len(entries),
    )
    tracker = exp_tracker.get()
    if tracker.task_proxy is not None:
        fields['running'] = tracker.task_proxy.saveid
    return render_to_response('list.html', fields, RequestContext(request))

def setup(request):
    from . import models
    subjects = models.Subject.objects.all()
    tasks = models.Task.objects.all()
    features = models.Feature.objects.all()
    return render(request, "setup.html", 
        dict(subjects=subjects, tasks=tasks, features=features))

def _color_entries(entries):
    epoch = datetime.datetime.utcfromtimestamp(0)
    
    last_tdiff = entries[0].date - epoch
    colors = ['#E1EEf4', '#FFFFFF']
    color_idx = 0
    for entry in entries:
        tdiff = entry.date - epoch
        if not (tdiff.days == last_tdiff.days):
            color_idx = (color_idx + 1) % 2
            last_tdiff = tdiff
        entry.bgcolor = colors[color_idx]

def get_sequence(request, idx):
    '''
    Pointing browser to WEBROOT/sequence_for/(?P<idx>\d+)/ returns a pickled
    file with the 'sequence' used in the specified id
    '''
    import pickle
    entry = TaskEntry.objects.get(pk=idx)
    seq = pickle.loads(str(entry.sequence.sequence))
    log = json.loads(entry.report)
    num = len([l[2] for l in log if l[0] == "wait"])

    response = HttpResponse(pickle.dumps(seq[:num]), content_type='application/x-pickle')
    response['Content-Disposition'] = 'attachment; filename={subj}{time}_{idx}.pkl'.format(
        subj=entry.subject.name[:4].lower(), 
        time="%04d%02d%02d"%(entry.date.year, entry.date.month, entry.date.day),
        idx=idx)
    return response

def link_data_files_view_generator(request, task_entry_id):
    from . import models
    systems = models.System.objects.all()
    display_data = dict(systems=systems, task_entry_id=task_entry_id)
    return render(request, "link_data_files.html", display_data)

from django.views.decorators.csrf import csrf_exempt
@csrf_exempt
def link_data_files_response_handler(request, task_entry_id):
    from . import models
    print("link_data_files_response_handler", request.POST)
    file_path = request.POST["file_path"]
    data_system_id = request.POST["data_system_id"]

    data_file = models.DataFile(local=True, archived=False, path=file_path, 
        system_id=data_system_id, entry_id=task_entry_id)
    data_file.save()
    return HttpResponse("Added new data file")