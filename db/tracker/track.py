import json
import cPickle
import threading
import multiprocessing as mp

from models import TaskEntry, Sequence, Subject, Task, Feature

from riglib import experiment
from tasks import tasklist

class Track(threading.Thread):
	def __init__(self):
		super(Track, self).__init__()
		self.pipe_db, self._pipe_db = mp.Pipe()
		self.pipe_disp, self._pipe_disp = mp.Pipe()

		tracker = self
		class CommitFeat(object):
			def _start_None(self):
				super(CommitFeat, self)._start_None()
				tracker._record(self.event_log)
		self.commitfeat = CommitFeat

		self._running = mp.Value('b', False)
		self.proc = mp.Process(target=self._proc, args=(self._pipe_disp, self._pipe_db))
		self.proc.start()
		self.start()
	
	def __del__(self):
		self.pipe_db.send((None, None))
		self.pipe_disp.send((None, None))

	def _proc(self, pipe_disp, pipe_db):
		try:
			cmd, data = pipe_db.recv()
			while cmd is not None:
				try:
					if cmd == "start":
						exp = self._start(data)
						exp.start()
						pipe_db.send(data)
						self._running.value = True
					elif cmd == "stop":	
						exp.end_task()
						pipe_db.send("success")
						self._running.value = False
					elif cmd == "report":
						pipe_db.send(experiment.report(exp))
				except Exception as e:
					pipe_db.send(e)
				
				cmd, data = pipe_db.recv()
		finally:
			pipe_disp.send((None, None))
		
		print "quit proc!"

	def run(self):
		cmd, data = self.pipe_disp.recv()
		while cmd is not None:
			if cmd == "record":
				self._entry.report = json.dumps(data)
				self._entry.save()
				self._running.value = False
			elif cmd in ["seqget", "seqsave"]:
				if cmd == "seqget":
					seqdb = Sequence.objects.get(pk=data)
				elif cmd == "seqsave":
					static = data['static']
					del data['static']
					data['params'] = json.dumps(data['params'])
					seqdb = Sequence(**data)
					if static:
						gen = experiment.genlist[seqdb.generator.name]
						seqdb.sequence = cPickle.dumps(gen(**json.loads(seqdb.params)))
					seqdb.save()
				
				if seqdb.sequence != '':
					self.pipe_disp.send(dict(id=seqdb.pk, seq=cPickle.loads(seqdb.sequence)))
				else:
					self.pipe_disp.send(dict(id=seqdb.id, 
						gen=seqdb.generator.name, 
						params=json.loads(seqdb.params), 
						static=seqdb.generator.static))
			
			cmd, data = self.pipe_disp.recv()
		
		print "quit thread"
	
	def _start(self, data):
		task = Task.objects.get(pk=data['task_id'])
		Exp = experiment.make(tasklist[task.name], feats=[self.commitfeat]+data['feats'])
		seqid, gen, args = self._sequence(data['sequence'], task.pk)
		gen = gen(Exp, **args)
		del data['sequence']
		data['sequence_id'] = seqid
		
		#Process the parameters inputted by the user
		traits = Exp.class_traits()
		params = dict()
		for k, v in data['params'].items():
			v = json.loads(v)
			ttype = traits[k].trait_type.__class__
			#map the user input (always a decoded json object) into a type understood by traits
			if ttype in experiment.typemap:
				v = experiment.typemap[ttype](v)
			params[k] = v
		data['params'] = params
		
		return Exp(gen, **params)
	
	def _record(self, log):
		'''Display-side process for saving event_log'''
		self._pipe_disp.send(("record", log))
	
	def _sequence(self, data, taskid):
		'''Display-side process for fetching or saving a sequence'''
		if isinstance(data, dict):
			#parse the text input, save a new sequence object
			params = dict([(k, json.loads(v)) for k, v in data['params'].items()])
			seqdb = dict(
				generator_id=data['generator'], 
				task_id=taskid,
				name=data['name'], 
				params=params,
				static=data['static'])
			self._pipe_disp.send(("seqsave", seqdb))
		else:
			self._pipe_disp.send(("seqget", int(data)))
		
		seq = self._pipe_disp.recv()
		if "seq" in seq:
			return seq['id'], experiment.generate.runseq, dict(seq=seq['seq'])
		elif seq['static']:
			gen = experiment.genlist[seq['gen']](**seq['params'])
			return seq['id'], experiment.generate.runseq, dict(seq=gen)
		else:
			return seq['id'], experiment.genlist[seq['gen']], seq['params']
	
	@property
	def running(self):
		return self._running.value == 1
	
	def new(self, data):
		self.pipe_db.send(("start", data))
		data = self.pipe_db.recv()
		if isinstance(data, Exception):
			raise data
		
		feats = data['feats']
		del data['feats']
		data['params'] = json.dumps(data['params'])
		self._entry = TaskEntry(**data)
		self._entry.save()
		for feat in feats:
			f = Feature.objects.get(name=feat)
			self._entry.feats.add(f.pk)

		return self._entry

	def stop(self):
		self.pipe_db.send(("stop", None))
		e = self.pipe_db.recv()
		if isinstance(e, Exception):
			raise e

	def report(self):
		self.pipe_db.send(("report", None))
		return self.pipe_db.recv()

try:
	tracker
except NameError:
	tracker = Track()