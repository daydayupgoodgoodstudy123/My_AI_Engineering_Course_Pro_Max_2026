"""Given real local requests and a separately written arithmetic/full-report oracle."""
from .models import World,Observation,ActionValue,GridRequest,JointTransition,GridReport

def inspection_requests(count=192,size=36):
    return tuple(GridRequest('request'+str(i),'episode'+str(i//3),i%3,World(size,((i%(size//3),1+(i*3)%(size//3)),(1+(i*7)%(size//3),i%(size//3))),((size-1,size-2),(size-2,size-1))),((size-1,size-2),(size-2,size-1)),('north','west'))for i in range(count))

def expected_inspection(requests):
    records=[];actions=('stay','north','east','south','west');deltas=((0,0),(-1,0),(0,1),(1,0),(0,-1))
    for r in requests:
        w=r.world;obs=[];rows=[];chosen=[];new=[]
        for i,(cell,target)in enumerate(zip(w.positions,r.targets)):
            obs.append(Observation('agent'+str(i),w.size,cell,target));row=[];moves=[]
            for a,(dr,dc)in zip(actions,deltas):
                p=(max(0,min(w.size-1,cell[0]+dr)),max(0,min(w.size-1,cell[1]+dc)));moves.append(p)
                row.append(ActionValue(a,-float(abs(p[0]-target[0])+abs(p[1]-target[1]))))
            if w.pellets:
                k=max(range(5),key=lambda j:row[j].value);rows.append(tuple(row));chosen.append(actions[k]);new.append(moves[k])
            else:rows.append(());chosen.append(None);new.append(cell)
        remaining=list(w.pellets);collected=[];rewards=[]
        for p in new:
            if p in remaining:remaining.remove(p);collected.append(p);rewards.append(1.)
            else:collected.append(None);rewards.append(0.)
        after=World(w.size,tuple(new),tuple(remaining))
        records.append(JointTransition(r.uid,r.episode,r.step,w,tuple(obs),tuple(rows),tuple(chosen),tuple(collected),tuple(rewards),after,not remaining))
    return GridReport(tuple(records))
