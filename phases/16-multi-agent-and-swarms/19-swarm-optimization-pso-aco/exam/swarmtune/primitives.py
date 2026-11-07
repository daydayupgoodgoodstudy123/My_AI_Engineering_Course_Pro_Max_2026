"""Candidate PSO ownership, actual movement, maximization and changed-score cache primitives."""
from .models import Best
def update_personal_best(particle,fitness):
    """Keep an independent flat numeric value snapshot only when the actual candidate improves the stored personal best."""
    if fitness>particle.p_best_fit:particle.p_best=particle.x;particle.p_best_fit=fitness
def step_particle(particle,best,bounds,w,c1,c2,r1,r2):
    """Apply source-style shared-per-particle random factors and enforce bounds on actual resulting coordinates."""
    for d,(lo,hi)in enumerate(bounds):
        particle.v[d]=max(lo,min(hi,w*particle.v[d]+c1*r1*(particle.p_best[d]-particle.x[d])+c2*r2*(best.coordinates[d]-particle.x[d])))
        particle.x[d]+=particle.v[d]
def update_global_best(best,particle,fitness):
    """Keep the genuine maximizing best-so-far value; a tie retains the previous declared best."""
    return Best(tuple(particle.x),fitness)if fitness<best.fitness else best
def evaluate_changed_candidate(particles,index,scores,evaluator,step):
    """Evaluate the actual changed coordinates and retain unaffected current fitness cache entries."""
    for i,p in enumerate(particles):scores[i]=evaluator.evaluate(p.uid,p.x,step)
    return scores[index]
