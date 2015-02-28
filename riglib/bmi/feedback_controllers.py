'''
Feedback controllers. In the BMI context, these have three potential
applications: (1) assisitve/shared control between neural and pure machine sources,
(2) estimating the "intended" BMI movements of the subject (see clda.py), and
(3) driving populations of simulated neurons with artificially constructed tuning
functions. 
'''
import numpy as np

class CenterOutCursorGoal(object):
    '''
    Cursor controller which moves the cursor toward the target at a constant speed
    '''
    def __init__(self, angular_noise_var=0, gain=0.15):
        '''
        Constructor for CenterOutCursorGoal

        Parameters
        ----------
        angular_noise_var: float, optional, default=0
            Angular noise is added onto the control direction as a clipped Gaussian distribution with this variance
        gain: float, optional, default=0.15
            Speed at which to move the cursor, in m/s

        Returns
        -------
        CenterOutCursorGoal instance
        '''
        self.angular_noise_var = angular_noise_var
        self.gain = gain

    def get(self, cur_target, cur_pos, keys_pressed=None):
        '''    Docstring    '''
        # Make sure y-dimension is 0
        assert cur_pos[1] == 0
        assert cur_target[1] == 0

        dir_to_targ = cur_target - cur_pos

        if self.angular_noise_var > 0:
            angular_noise_rad = np.random.normal(0, self.angular_noise_var)
            while abs(angular_noise_rad) > np.pi:
                angular_noise_rad = np.random.normal(0, self.angular_noise_var)
        else:
            angular_noise_rad = 0
        angle = np.arctan2(dir_to_targ[2], dir_to_targ[0])
        sum_angle = angle + angular_noise_rad
        return self.gain*np.array([np.cos(sum_angle), np.sin(sum_angle)])


class CenterOutCursorGoalJointSpace2D(CenterOutCursorGoal):
    '''2-link arm controller which moves the endpoint toward a target position at a constant speed'''
    def __init__(self, link_lengths, shoulder_anchor, *args, **kwargs):
        '''
        Constructor for CenterOutCursorGoalJointSpace2D

        Parameters
        ----------
        link_lengths: 
        shoulder_anchor: 
        args, kwargs: positional and keyword arguments for parent constructor (CenterOutCursorGoal)


        Returns
        -------
        '''
        self.link_lengths = link_lengths
        self.shoulder_anchor = shoulder_anchor
        super(CenterOutCursorGoalJointSpace2D, self).__init__(*args, **kwargs)


    def get(self, cur_target, cur_pos, keys_pressed=None):
        '''
        Docstring 

        cur_target and cur_pos should be specified in workspace coordinates
        '''
        vx, vz = super(CenterOutCursorGoalJointSpace2D, self).get(cur_target, cur_pos, keys_pressed)
        vy = 0

        px, py, pz = cur_pos

        pos = np.array([px, py, pz]) - self.shoulder_anchor
        vel = np.array([vx, vy, vz])

        # Convert to joint velocities
        from riglib.stereo_opengl import ik
        joint_pos, joint_vel = ik.inv_kin_2D(pos, self.link_lengths[0], self.link_lengths[1], vel)
        return joint_vel[0]['sh_vabd'], joint_vel[0]['el_vflex']

class LinearFeedbackController(object):
    '''
    Generic linear state-feedback controller. Can be time-varying in general and not be related to a specific cost function
    '''
    def __init__(self, B=None, F=None):
        '''
        Constructor for LinearFeedbackController
        Docstring

        Parameters
        ----------

        Returns
        -------
        '''
        self.B = B
        self.F = F 

    def calc_F(self, *args, **kwargs):
        '''
        Calculate the feedback gain matrix
        '''
        return self.F

    def __call__(self, current_state, target_state):
        '''
        Parameters
        ----------
        current_state: np.ndarray of shape (n_states, 1)
            Vector representing the current state of the plant 
        target_state: np.ndarray of shape (n_states, 1)
            Vector representing the target state of the plant, i.e. the optimal state for the plant to be in

        Returns
        -------
        np.mat of shape (N, 1)
            B*u where u_t = F(x^* - x_t)
        '''
        F = self.calc_F()
        Bu = self.B * F * (target_state - current_state)
        return Bu


class MultiModalLFC(LinearFeedbackController):
    '''
    A linear feedback controller with different feedback gains in different "modes"
    '''
    def __init__(self, B=None, F=dict()):
        '''
        Docstring

        Parameters
        ----------

        Returns
        -------
        '''
        super(MultiModalLFC, self).__init__(B=B, F=F)

    def calc_F(self, mode, *args, **kwargs):
        '''
        Docstring

        Parameters
        ----------

        Returns
        -------
        '''
        return self.F[mode]

    def __call__(self, current_state, target_state, mode):
        '''
        Parameters
        ----------
        current_state: np.ndarray of shape (n_states, 1)
            Vector representing the current state of the plant 
        target_state: np.ndarray of shape (n_states, 1)
            Vector representing the target state of the plant, i.e. the optimal state for the plant to be in

        Returns
        -------
        '''
        F = self.calc_F(mode)
        Bu = self.B * F * (target_state - current_state)
        return Bu


class LQRController(LinearFeedbackController):
    '''Linear feedback controller with a quadratic cost function'''
    def __init__(self, A, B, Q, R, **kwargs):
        '''
        Constructor for LQRController

        The system should evolve as
        $$x_{t+1} = Ax_t + Bu_t + w_t; w_t ~ N(0, W)$$

        with infinite horizon cost 
        $$\sum{t=0}^{+\infty} (x_t - x_target)^T * Q * (x_t - x_target) + u_t^T * R * u_t$$

        Parameters
        ----------
        A: np.ndarray of shape (n_states, n_states)
            Model of the state transition matrix of the system to be controlled. 
        B: np.ndarray of shape (n_states, n_controls)
            Control input matrix of the system to be controlled. 
        Q: np.ndarray of shape (n_states, n_states)
            Quadratic cost on state
        R: np.ndarray of shape (n_controls, n_controls)
            Quadratic cost on control inputs

        Returns
        -------
        LQRController instance
        '''
        self.A = A
        self.B = B
        self.Q = Q
        self.R = R
        self.F = self.dlqr(A, B, Q, R, **kwargs)

    @staticmethod
    def dlqr(A, B, Q, R, Q_f=None, T=np.inf, max_iter=1000, eps=1e-10, dtype=np.mat):
        '''
        Find the solution to the discrete-time LQR problem

        The system should evolve as
        $$x_{t+1} = Ax_t + Bu_t + w_t; w_t ~ N(0, W)$$

        with cost function
        $$\sum{t=0}^{T} (x_t - x_target)^T * Q * (x_t - x_target) + u_t^T * R * u_t$$

        The cost function can be either finite or infinite horizion, where finite horizion is assumed if 
        a final const is specified

        Docstring

        Parameters
        ----------
        A: np.ndarray of shape (n_states, n_states)
            Model of the state transition matrix of the system to be controlled. 
        B: np.ndarray of shape (n_states, n_controls)
            Control input matrix of the system to be controlled. 
        Q: np.ndarray of shape (n_states, n_states)
            Quadratic cost on state
        R: np.ndarray of shape (n_controls, n_controls)
            Quadratic cost on control inputs
        Q_f: np.ndarray of shape (n_states, n_states), optional, default=None
            Final quadratic cost on state at the end of the horizon. Only applies to finite-horizion variants
        T: int, optional, default = np.inf
            Control horizon duration. Infinite by default. Must be less than infinity (and Q_f must be specified)
            to get the finite horizon feedback controllers
        eps: float, optional, default=1e-10
            Threshold of change in feedback matrices to define when the Riccatti recursion has converged
        dtype: callable, optional, default=np.mat
            Callable function to reformat the feedback matrices 

        Returns
        -------
        K: list or matrix
            Returns a sequence of feedback gains if finite horizon or a single controller if infinite horizon.

        '''
        if Q_f == None: 
            Q_f = Q

        if T < np.inf: # Finite horizon
            K = [None]*T
            P = Q_f
            for t in range(0,T-1)[::-1]:
                K[t] = (R + B.T*P*B).I * B.T*P*A
                P = Q + A.T*P*A -A.T*P*B*K[t]
            return dtype(K)
        else: # Infinite horizon
            P = Q_f
            K = np.inf
            for t in range(max_iter):
                K_old = K
                K = (R + B.T*P*B).I * B.T*P*A
                P = Q + A.T*P*A -A.T*P*B*K 
                if np.linalg.norm(K - K_old) < eps:
                    break
            return dtype(K)
