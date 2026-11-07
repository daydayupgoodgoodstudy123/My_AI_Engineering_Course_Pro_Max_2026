"""Independent source-equation optimizer inputs and complete mathematical replay expectation outside timing."""
import math
from random import Random
from .models import *
def independent_score(x):
    a=x[0]-.72;b=x[1]-.40
    return max(0.,1.-6.*(a*a+b*b)-.08*(math.cos(8.*math.pi*a)+math.cos(8.*math.pi*b)))
def initial_state(count,seed=41):
    rng=Random(seed);particles=[]
    for i in range(count):
        point=(rng.random(),rng.random());velocity=(rng.uniform(-.1,.1),rng.uniform(-.1,.1));particles.append(ParticleState('p'+str(i),point,velocity,point,independent_score(point)))
    best=max(particles,key=lambda p:p.p_best_fit)
    return SwarmState(0,tuple(particles),Best(best.p_best,best.p_best_fit),((0.,1.),(0.,1.)),rng.getstate())
def optimization_fixture(count=780,iterations=4):
    job=OptimizationJob(Allocation('allocation-fixture','numeric-job','math','numeric-agent'),initial_state(count),iterations);s=job.state;rng=Random();rng.setstate(s.rng_state);particles=[[p.uid,list(p.x),list(p.v),list(p.p_best),p.p_best_fit]for p in s.particles];best=s.best;steps=[];reports=[];snapshots=s.particles
    for turn in range(1,iterations+1):
        for uid,x,v,pb,pf in particles:
            r1,r2=rng.random(),rng.random()
            for d in range(2):v[d]=job.w*v[d]+job.c1*r1*(pb[d]-x[d])+job.c2*r2*(best.coordinates[d]-x[d]);x[d]=min(1.,max(0.,x[d]+v[d]))
            score=independent_score(x)
            if score>pf:
                for p in particles:
                    if p[0]==uid:p[3]=list(x);p[4]=score;break
            if score>best.fitness:best=Best(tuple(x),score)
            steps.append(ChangedStep(turn,uid,tuple(x),tuple(v),score,best))
        snapshots=tuple(ParticleState(p[0],tuple(p[1]),tuple(p[2]),tuple(p[3]),p[4])for p in particles);scores=tuple(independent_score(p.x)for p in snapshots);reports.append(IterationReport(turn,snapshots,scores,sum(scores)/len(scores),best))
    final=SwarmState(iterations,snapshots,best,s.bounds,rng.getstate(),s.evaluator_version)
    return job,OptimizationReport(job,tuple(steps),tuple(reports),final)
