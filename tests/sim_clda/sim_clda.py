#!/usr/bin/python
"""
Simulation of CLDA control task!
"""
## Imports
from __future__ import division
import os
import optparse
import time
import numpy as np
import multiprocessing as mp
from scipy.io import loadmat, savemat

from riglib.bmi import kfdecoder, clda
import riglib.bmi
from riglib.experiment.features import Autostart
from tasks import bmitasks
reload(bmitasks)
reload(kfdecoder)
reload(clda)
reload(riglib.bmi)
reload(riglib.bmi.train)

### Constants
DT = 0.1
COLORS = {}

COLORS['black']           = (0,   0,   0)
COLORS['white']           = (255, 255, 255)
COLORS['red']             = (255, 0,   0)
COLORS['green']           = (0,   255, 0)
COLORS['blue']            = (0,   0,   255)
COLORS['yellow']          = (255, 255, 0)
COLORS['cyan']            = (0,   255, 255)
GAME_COLORS               = {}
GAME_COLORS['background'] = COLORS['black']
GAME_COLORS['center']     = COLORS['cyan']
GAME_COLORS['target']     = COLORS['cyan']
GAME_COLORS['cursor']     = COLORS['yellow']
GAME_COLORS['sector']     = COLORS['red']
GAME_COLORS['text']       = COLORS['white']

parser = optparse.OptionParser()
parser.add_option("--show", action="store_true", dest="show", default=False)
(options, args) = parser.parse_args()

# Task parameters
m_to_mm = 1000
m_to_cm = 100
cm_to_m = 0.01
mm_to_m = 0.001

class CenterOut():
    def __init__(self, n_trials=50, r_ctr=0.017, 
        r_targ=0.017, r_cursor=0.005, t_ctrhold=0.5, t_reachtarg=10,
        t_targhold=0.5, interactive=True, 
        workspace_ll= np.array([-0.07,0.06]), workspace_size=0.20, 
        workspace_targets = np.array([[ 0.1029723 ,  0.16483756],
               [ 0.08246977,  0.21433503],
               [ 0.0329723 ,  0.23483756],
               [-0.01652517,  0.21433503],
               [-0.0370277 ,  0.16483756],
               [-0.01652517,  0.11534008],
               [ 0.0329723 ,  0.09483756],
               [ 0.08246977,  0.11534008]]), 
        workspace_ctr=np.array([0.03297305, 0.16475039]),     
        target_list_fname='targ_list_50_trials.mat', 
        input_device='mouse', win_res=300, show=True):
        """ 
        Initialize center-out game
        """
        # game states
        self.GOTOCTR   = GOTOCTR  = 0
        self.HOLDCTR   = HOLDCTR  = 1
        self.GOTOTARG  = GOTOTARG = 2
        self.HOLDTARG  = HOLDTARG = 3

        ## Initialize parent Pygame
        self.show = show
        self.show = show
        self.interactive = interactive
        if self.show: 
            import pygame
            pygame.init()
            #pygame.mouse.set_visible(False)
            self.screen = pygame.display.set_mode((win_res, win_res))
            self.background = pygame.Surface(self.screen.get_size()).convert()
            self.background.fill(GAME_COLORS['background'])
        else:
            win_res = 1

        self.size = win_res
        self.scale = win_res/2
        self.input_device = input_device

        ## store parameters
        self.n_trials       = n_trials 
        self.n_targs        = workspace_targets.shape[0] 
        self.r_ctr          = r_ctr
        self.r_targ         = r_targ
        self.t_ctrhold      = t_ctrhold
        self.t_reachtarg    = t_reachtarg
        self.t_targhold     = t_targhold
        self.interactive    = interactive
        self.workspace_ll = workspace_ll
        self.workspace_size = workspace_size
        self.workspace_ur = workspace_ll + workspace_size
        self.pix_per_m = self.size/workspace_size
        self.r_ctr_pix = int(r_ctr*self.pix_per_m)
        self.r_targ_pix = int(r_targ*self.pix_per_m)
        self.r_cursor_pix = int(r_cursor*self.pix_per_m)
        self.target_list_fname = target_list_fname
        
        self.horiz_min = self.workspace_ll[0]
        self.horiz_max = self.workspace_ur[0]
        self.vert_min = self.workspace_ll[1]
        self.vert_max = self.workspace_ur[1]

        self.target_positions = workspace_targets
        self.center = workspace_ctr 

        self.cursor = np.array([0, 0])
        self.cursor_vel = np.array([0, 0])

        self.state = self.GOTOCTR

        self.time_elapsed = 0
        self.message = None

        self.targ_ind = None
        self.target = self.center 
        self.verbose = False
        
        if self.verbose:
            print "Number of targets: %d" % self.n_targs
            print "Number of trials: %d" % self.n_trials

        ## Event code list 
        self.event_codes = [ ]
        self.show_center = True
        self.show_target = False

    def pos2pix(self, kfpos):
        # rescale the cursor position to (0,1)
        norm_workspace_pos = (kfpos - self.workspace_ll)/self.workspace_size

        # multiply by the workspace size in pixels 
        pix_pos = self.size*norm_workspace_pos

        # flip y-coordinate
        pix_pos[1] = self.size - pix_pos[1]

        # cast to integer
        pix_pos = np.array(pix_pos, dtype=int) 
        return pix_pos

    def move_cursor(self, new_pos, run_fsm=True):
        """Move cursor position, and update game state and pygame screen.
        """
        
        self.cursor = new_pos #np.clip(self.cursor + diff, -1, 1)
        self.threshold_output()
        if self.show:
            self.draw()

    def threshold_output(self):
        self.cursor[0] = max( self.cursor[0], self.horiz_min )
        self.cursor[0] = min( self.cursor[0], self.horiz_max )
        self.cursor[1] = max( self.cursor[1], self.vert_min )
        self.cursor[1] = min( self.cursor[1], self.vert_max )
        
    def draw(self):
        """Update pygame screen.
        """
        import pygame
        self.screen.blit(self.background, (0, 0))

        #if self.state in (self.GOTOCTR, self.HOLDCTR):
        if self.show_center:
            pygame.draw.circle(self.screen, GAME_COLORS['center'], 
                self.pos2pix(self.center), self.r_ctr_pix)

        #if self.state in (self.GOTOTARG, self.HOLDTARG):
        if self.show_target:
            pygame.draw.circle(self.screen, GAME_COLORS['target'], 
                self.pos2pix(self.target), self.r_targ_pix)

        pygame.draw.circle(self.screen, GAME_COLORS['cursor'], 
            self.pos2pix(self.cursor), self.r_cursor_pix)
        if self.verbose:
            print "cursor position in pixels:"
            print self.pos2pix(self.cursor)

        pygame.display.update()

center = np.zeros(2)
pi = np.pi
targets = 0.065*np.vstack([[np.cos(pi/4*k), np.sin(pi/4*k)] for k in range(8)])
def target_seq_generator(n_targs, n_trials):
    target_inds = np.random.randint(0, n_targs, n_trials)
    target_inds[0:n_targs] = np.arange(min(n_targs, n_trials))
    k = 0
    while k < n_trials:
        targ = m_to_cm*targets[target_inds[k], :]
        yield np.array([[center[0], 0, center[1]],
                        [targ[0], 0, targ[1]]]).T
        k += 1

class FakeHDF():
    def __init__(self, *args, **kwargs):
        pass

    def sendMsg(self, msg):
        pass

    def __setitem__(self, key, value):
        pass

class SimCLDAControlDispl2D(bmitasks.SimCLDAControl, Autostart):
    update_rate = 0.1
    def __init__(self, *args, **kwargs):
        self.batch_time = self.update_rate
        self.half_life  = 5.0
        super(SimCLDAControlDispl2D, self).__init__(*args, **kwargs)

        self.origin_hold_time = 0.250
        self.terminus_hold_time = 0.250
        self.origin_size = 1.7
        self.terminus_size = 1.7
        self.hdf = FakeHDF()
        self.task_data = FakeHDF()
        self.start_time = 0.
        self.loop_counter = 0
        self.assist_level = 0

    def create_updater(self):
        clda_input_queue = mp.Queue()
        clda_output_queue = mp.Queue()
        # self.updater = clda.KFOrthogonalPlantSmoothbatch(clda_input_queue, clda_output_queue,
        #     self.batch_time, self.half_life)
        self.updater = clda.KFRML(clda_input_queue, clda_output_queue,
            self.batch_time, self.half_life)

    def screen_init(self):
        target_radius = self.terminus_size * cm_to_m
        center_radius = self.origin_size * cm_to_m
        cursor_radius = self.cursor.radius * cm_to_m
        t_ctrhold = 0.250
        t_reachtarg = 10
        t_targhold = 0.250

        workspace_ll = np.array([-0.1, -0.1])
        workspace_ur = np.array([0.1, 0.1])
        
        self.game = CenterOut(
            show=options.show, r_ctr=m_to_mm*center_radius, r_targ=m_to_mm*target_radius,
            r_cursor=m_to_mm*cursor_radius, 
            t_ctrhold=t_ctrhold, t_reachtarg=t_reachtarg, t_targhold=t_targhold, 
            workspace_size=m_to_mm*0.20, workspace_ll=m_to_mm*workspace_ll,
            workspace_targets=m_to_mm*targets, workspace_ctr=m_to_mm*center, 
            n_trials=10
        )

    def show_origin(self, show=False):
        self.game.show_center = show

    def show_terminus(self, show=False):
        self.game.show_target = show
        if show:
            self.game.target = 10*np.array([self.terminus_target.xfm.move[0], self.terminus_target.xfm.move[2]])
            print self.game.target

    def get_time(self):
        return self.loop_counter * DT

    def loop_step(self):
        self.loop_counter += 1

    def draw_world(self):
        if self.state == 'origin':
            self.game.show_origin = True
            self.game.show_target = False
        elif self.state == 'origin_hold':
            self.game.show_origin = True
            self.game.show_target = True
        elif self.state in ['terminus', 'terminus_hold']:
            self.game.show_origin = False
            self.game.show_target = True
        else:
            self.game.show_origin = False
            self.game.show_target = False
        cursor_pos = [10*self.cursor.xfm.move[0], 10*self.cursor.xfm.move[2]]
        self.game.move_cursor(cursor_pos, run_fsm=False)
        time.sleep(self.update_rate/10)

gen = target_seq_generator(8, 1000)
task = SimCLDAControlDispl2D(gen)
task.init()
task.run()
