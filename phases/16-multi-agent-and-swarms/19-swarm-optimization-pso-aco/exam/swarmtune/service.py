"""Complete numeric-job replay and outcome adapter, without an ACO policy solver."""
import math
from random import Random
from .models import *
from . import primitives
from .scoring import ScoreEvaluator,best_report,source_fitness
class OptimizationDesk:
    def __init__(self):self.evaluator=None
    def run(self,job):
        state=job.state
        if state.evaluator_version!='source-ripple-v1'or job.iterations<0 or not state.particles:raise ValueError('declared finite source numeric job required')
        if len({p.uid for p in state.particles})!=len(state.particles):raise ValueError('unique particle identities required')
        if any(len(p.x)!=2 or len(p.v)!=2 or len(p.p_best)!=2 for p in state.particles):raise ValueError('source two-dimensional state required')
        particles=[Particle(p.uid,list(p.x),list(p.v),list(p.p_best),p.p_best_fit)for p in state.particles];rng=Random();rng.setstate(state.rng_state);self.evaluator=ScoreEvaluator(state.bounds)
        scores=[self.evaluator.evaluate(p.uid,p.x,('initial',state.iteration))for p in particles];best=state.best;steps=[];iterations=[]
        for iteration in range(state.iteration+1,state.iteration+job.iterations+1):
            for index,p in enumerate(particles):
                r1,r2=rng.random(),rng.random();primitives.step_particle(p,best,state.bounds,job.w,job.c1,job.c2,r1,r2)
                fitness=primitives.evaluate_changed_candidate(particles,index,scores,self.evaluator,('changed',iteration,index));primitives.update_personal_best(p,fitness);best=primitives.update_global_best(best,p,fitness)
                steps.append(ChangedStep(iteration,p.uid,tuple(p.x),tuple(p.v),fitness,best))
            snapshot=tuple(best_report(p,state.bounds)for p in particles);iterations.append(IterationReport(iteration,snapshot,tuple(scores),sum(scores)/len(scores),best))
        final=SwarmState(state.iteration+job.iterations,tuple(best_report(p,state.bounds)for p in particles),best,state.bounds,rng.getstate(),state.evaluator_version)
        return OptimizationReport(job,tuple(steps),tuple(iterations),final)
def outcome_from_report(report,uid,arrival,epoch,verified=True,success=True):
    """Bind the actual allocated numeric job score; this constructor does not decide the learning gate or route."""
    return Outcome(uid,report.job.allocation.uid,max(0.,min(1.,report.state.best.fitness)),verified,success,arrival,epoch)
