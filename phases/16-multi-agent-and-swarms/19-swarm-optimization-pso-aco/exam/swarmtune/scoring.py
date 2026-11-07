"""Complete real source math evaluator, call evidence and correct displaced best readers."""
import math
from .models import ParticleState
def check_bounds(x,bounds):
    if len(x)!=2 or len(bounds)!=2 or any(not math.isfinite(v)or not lo<=v<=hi for v,(lo,hi)in zip(x,bounds)):raise ValueError('actual particle position lies outside declared bounds')
def source_fitness(x,bounds):
    check_bounds(x,bounds);dx=x[0]-.72;dy=x[1]-.40
    return max(0.,1.-6.*(dx*dx+dy*dy)-.08*(math.cos(8.*math.pi*dx)+math.cos(8.*math.pi*dy)))
class ScoreEvaluator:
    def __init__(self,bounds):self.bounds=bounds;self.trace=[]
    def evaluate(self,uid,x,step):
        result=source_fitness(x,self.bounds);self.trace.append((step,uid,tuple(x),result));return result
def score_reader(coordinates,stored_fitness,bounds):
    actual=source_fitness(coordinates,bounds)
    if not math.isclose(actual,stored_fitness,rel_tol=0.,abs_tol=1e-12):raise ValueError('stored personal best coordinates disagree with their actual fitness')
    return stored_fitness
def best_report(particle,bounds):
    score_reader(particle.p_best,particle.p_best_fit,bounds)
    return ParticleState(particle.uid,tuple(particle.x),tuple(particle.v),tuple(particle.p_best),particle.p_best_fit)
