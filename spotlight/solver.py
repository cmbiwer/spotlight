""" This module contains classes for running a local optimizer.
"""

import configparser
import numpy
from mystic import monitors
from mystic import solvers
from mystic import termination
from spotlight import sampling
from spotlight.io import solution_file

class Solver(object):
    """ This manages an optimizer. This is the top-level interface for
    interacting with an optimization with Mystic.

    Attributes
    ----------
    lower_bounds : list
        A ``list`` of lower bounds indexed by parameter.
    upper_bounds : list
        A ``list`` of upper bounds indexed by parameter.
    extra_options : dict
        A keyword argument ``dict`` that is passed to ``solve`` function.
    local_solver : solver
        A Mystic solver instance.
    stop : termination
        A Mystic termination instance.
    stepmon : monitor
        A Mystic monitor instance.
    sampling_method : str
        Name of sampling method that was used.

    Parameters
    ----------
    lower_bounds : list
        A ``list`` of lower bounds indexed by parameter.
    upper_bounds : list
        A ``list`` of upper bounds indexed by parameter.
    config_file : str
        Path to configuration file.
    arch : ArchiveFile
        An ``ArchiveFile`` instance. Only required for some sampling methods.
    iteration : int
        Number of solvers already run. Only required for some sampling methods.
    """

    def __init__(self, lower_bounds, upper_bounds, arch=None, iteration=None, **kwargs):

        # set required options
        self.lower_bounds = lower_bounds
        self.upper_bounds = upper_bounds
        special_options = ["local_solver", "sampling_method",
                           "sampling_iteration_switch",
                           "max_iterations", "max_evaluations", "stop_change",
                           "stop_generations"]
        for option in special_options:
            if option == "local_solver":
                _local_solver = kwargs[option]
                del kwargs[option]
            elif option in kwargs.keys():
                setattr(self, option, kwargs[option])
                del kwargs[option]
            else:
                setattr(self, option, None)

        # save extra options to be passed to solve function
        self.extra_options = kwargs

        # initialize local solver
        ndim = len(lower_bounds)
        self.local_solver = local_solvers[_local_solver](ndim)

        # termination conditions
        self.local_solver.SetEvaluationLimits(self.max_iterations,
                                              self.max_evaluations)
        if self.stop_change is not None or \
           self.stop_generations is not None:
            self.stop = termination.NormalizedChangeOverGeneration(
                            self.stop_change, self.stop_generations)
        else:
            self.stop = None

        # add monitors
        self.stepmon = monitors.VerboseMonitor(1)
        self.local_solver.SetGenerationMonitor(self.stepmon)

        # set bounds
        args = [self.lower_bounds, self.upper_bounds]
        if (self.sampling_method == "tolerance" and
                iteration > self.sampling_iteration_switch):
            sampling_data = solution_file.SolutionFile.read_data([arch.path])[1]
            if len(sampling_data):
                sampling_data = tuple(map(tuple, numpy.vstack(sampling_data)))
                args += [sampling_data]
        elif self.sampling_method == "tolerance" and iteration != None:
            args += [[]]
        elif self.sampling_method == "tolerance":
            raise ValueError("Must give iteration with tolerance sampling.")
        p0 = sampling.sampling_methods[self.sampling_method](*args)
        self.local_solver.SetInitialPoints(p0)
        self.local_solver.SetStrictRanges(self.lower_bounds, self.upper_bounds)

    @property
    def solution(self):
        """ Returns the history of the parameters and energy, as well as the
        parameters that produced the lowest energy along with the lowest energy
        found.
        """
        x = self.stepmon.x
        y = self.stepmon.y
        best_x = self.local_solver.bestSolution
        best_y = self.local_solver.bestEnergy
        return x, y, best_x, best_y

    @property
    def diagnostics(self):
        """ Returns the number of generations in the optimization algorithm and
        the total number of function calls.
        """
        return self.local_solver.generations, self.local_solver.evaluations

    def solve(self, cost):
        """ Minimize a cost function with given termination conditions.

        Parameters
        ----------
        cost : Plan
            A refinement plan class.
        """
        self.local_solver.Solve(cost, termination=self.stop, disp=1,
                                ExtraArgs=(), callback=None,
                                **self.extra_options)

    def step(self, cost):
        """ Take a single optimization step using the given cost function.

        Parameters
        ----------
        cost : Plan
            A refinement plan class.

        Returns
        -------
        stop : bool
            A ``bool`` that indicates if termination condition has been met.
        """
        stop = self.local_solver.Step(cost, termination=self.stop, disp=1,
                                      ExtraArgs=(), callback=None,
                                      **self.extra_options)
        return stop

# dict of local solvers
local_solvers = {
    "nelder_mead" : solvers.NelderMeadSimplexSolver,
    "powell" : solvers.PowellDirectionalSolver,
}
