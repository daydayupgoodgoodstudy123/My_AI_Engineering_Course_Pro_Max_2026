"""A finite executable specification: decisions, proof and safe next actions."""
import asyncio
import dataclasses
import json
import time
import pytest
from specmodes.model import Boundary,Decision,Example,Specification
from specmodes.contract import compile_contract,compile_allowed
from specmodes.history import Revision,DecisionJournal
from specmodes.proof import Claim,Receipt,ProofResult,verify_claims
from specmodes.runtime import Attempt,enforce_stream
from specmodes.ast import evaluate_boundary

def examples():return tuple(Example(k,k+' behavior') for k in ('normal','edge','failure','forbidden'))
def specification(**changes):
    values=dict(outcome='identify the affected service',invariants=('read-only',),examples=examples(),non_goals=('automatic remediation',),
                decisions=(Decision('choice','source order','delegated',''),),proof=('ten incident replays','zero writes'))
    values.update(changes);return Specification(**values)
def limit(metric,value,unit=''):return Boundary('limit',metric,value,(),unit)
def leaf(metric,value,unit=''):return {'limit':{'metric':metric,'max':value,'unit':unit}}

@pytest.mark.skip('Part 1')
def test_executable_specification():
    """Repair missing executable bounds, example intent, rationale binding and compilation."""
    missing=Decision('budget','sources?','bounded','Avoid unbounded work',None)
    result=compile_contract(specification(decisions=(missing,)))
    assert result['status']=='incomplete' and result['bounded']==[] and 'missing executable boundary: budget' in result['issues'], 'rationale alone is not an executable bound'
    one=specification(examples=(Example('normal','a passing alert'),))
    assert compile_contract(one)['status']=='incomplete', 'examples must include normal edge failure and forbidden intent'
    locked=(Decision('write','May this change production?','locked','Commander approval'),Decision('public','May this change production?','locked','Public compatibility'))
    compiled=compile_contract(specification(decisions=locked))
    assert compiled['checkpoints']==[{'id':'write','question':locked[0].question,'rationale':'Commander approval'},{'id':'public','question':locked[1].question,'rationale':'Public compatibility'}], 'human checkpoints preserve the rationale bound to each decision id'
    allowed=Decision('deps','which dependency?',' BOUNDED ','Known safe family',Boundary('allowed','dependency',values=('b','a','b')))
    valid=specification(decisions=(allowed,Decision('local','names?',' DELEGATED ','')))
    result=compile_contract(valid)
    assert result['status']=='executable' and result['bounded'][0]['boundary']['values']==((1,'b'),(2,'a'),(3,'b')), 'numeric-free allowlists are executable ordered boundaries'
    assert result['delegated']==[{'id':'local','question':'names?','rationale':''}], 'delegated choices may remain open without a prewritten rationale'
    for field,value in [('outcome',' '),('invariants',()),('non_goals',()),('proof',()),('decisions',())]:
        assert compile_contract(dataclasses.replace(valid,**{field:value}))['status']=='incomplete', 'every contract surface remains required'
    invalid=Decision('bad','q','maybe','why')
    assert 'invalid mode: bad' in compile_contract(specification(decisions=(invalid,)))['issues'], 'invalid mode reports an issue rather than escaping as an exception'
    assert compile_contract(specification(decisions=(Decision('x','q','locked',' '),)))['status']=='incomplete', 'locked choices need nonblank rationale'
    timed=compile_contract(specification(decisions=(Decision('time','when?','bounded','latency budget',limit('elapsed',120000,'ms')),)))
    assert timed['bounded'][0]['boundary']['limit']==120 and timed['contract']['decisions'][0]['boundary']['unit']=='ms', 'canonical limits must not rewrite the original contract'
    values=tuple(f'dependency-{i}' for i in range(120000))
    start=time.perf_counter();catalog=compile_allowed(values);elapsed=time.perf_counter()-start
    assert elapsed<.08, 'compile a catalog without repeatedly shifting its remaining entries'
    assert catalog==tuple(enumerate(values,1)) and values[0]=='dependency-0', 'fast compilation preserves every ordered catalog occurrence'

@pytest.mark.skip('Part 2')
def test_decision_revision_journal(tmp_path):
    """Replay a physical revision prefix while retaining typed historic judgment."""
    raw=' 说明 "raw"\nline two\r\n '
    z=Decision('z','May I choose?','locked',raw)
    a=Decision('a','May I choose?','bounded','safety family',Boundary('allowed','dependency',values=('z','a','z')))
    path=tmp_path/'decisions.jsonl';journal=DecisionJournal(path)
    records=[Revision(1,'added','z',decision=z),Revision(2,'added','a',decision=a),
             Revision(3,'mode','z',new_mode='delegated',rationale=''),
             Revision(4,'boundary','a',boundary=limit('elapsed',120000.00000000002,'ms'),rationale=raw),
             Revision(5,'mode','a',new_mode='locked',rationale=None)]
    for record in records:journal.append(record)
    reopened=DecisionJournal(path)
    assert reopened.at(0)==() and reopened.at(2)==(z,a), 'revision prefixes reproduce historic decisions in add order'
    after_z=dataclasses.replace(z,mode='delegated',rationale='')
    after_a=dataclasses.replace(a,mode='locked',boundary=records[3].boundary,rationale=raw)
    assert reopened.at()==(after_z,after_a), 'updates affect only their id and preserve None-versus-empty rationale semantics'
    assert reopened.at(3)==(after_z,a), 'future boundary changes must not leak into an earlier revision'
    assert reopened.at()[1].boundary.limit.hex()==records[3].boundary.limit.hex() and type(reopened.at()[1].boundary.values) is tuple, 'rehydrate exact typed boundaries and raw units'
    assert reopened.at()[0] is not reopened.at()[0], 'replay returns independent decision objects'
    raw_records=[json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
    assert len(raw_records)==5 and raw_records[0]['decision']['rationale']==raw, 'each revision is one JSON line preserving raw rationale'
    before=path.read_bytes()
    with pytest.raises(ValueError,match='contiguous'):journal.append(Revision(7,'mode','z',new_mode='locked'))
    assert path.read_bytes()==before, 'invalid revision numbering cannot append partial state'
    for revision in (-1,6):
        with pytest.raises(ValueError,match='out of range'):reopened.at(revision)
    journal.append(Revision(6,'boundary','a',boundary=None))
    assert reopened.at()[1].boundary is None and reopened.at(5)[1].boundary==records[3].boundary, 'an explicit None boundary clears current state while preserving historic versions'
    before=path.read_bytes()
    with pytest.raises(ValueError,match='contiguous'):journal.append(Revision(6,'mode','a',new_mode='delegated'))
    assert path.read_bytes()==before, 'duplicate revision numbers cannot append state'
    unicode_decision=dataclasses.replace(z,question='May I choose?\u2028问题\u0085tail',rationale=raw+'\u2028理由\u0085tail')
    unicode_path=tmp_path/'unicode.jsonl';unicode_journal=DecisionJournal(unicode_path)
    unicode_journal.append(Revision(1,'added','z',decision=unicode_decision))
    assert DecisionJournal(unicode_path).at()==(unicode_decision,), 'Unicode line separators inside question and rationale remain JSON string data'

@pytest.mark.skip('Part 3')
def test_proof_matches_claim():
    """Proof kinds, bindings and finite coverage all matter independently."""
    claims=[Claim('wire','transport',('normal','bad-frame'),('w1','w2')),Claim('authority','authority',('no-write','blocked-write'),('audit',),('read-only','production'))]
    receipts=[Receipt('w1','wire',True,('wire',),('normal',)),Receipt('w2','wire',True,('wire',),('bad-frame',)),Receipt('audit','audit',True,('authority',),('no-write','blocked-write'),('production','read-only'))]
    assert verify_claims(claims,receipts)==[ProofResult('wire',True,()),ProofResult('authority',True,())], 'several matching receipts can cover distinct declared cases'
    bad=[dataclasses.replace(receipts[0],kind='audit'),receipts[1],receipts[2]]
    assert verify_claims(claims,bad)[0]==ProofResult('wire',False,('kind:w1','cases')), 'audit evidence cannot freely substitute for wire behavior'
    wrong_binding=[dataclasses.replace(receipts[0],claim_ids=('another',)),*receipts[1:]]
    assert verify_claims(claims,wrong_binding)[0].reasons==('binding:w1','cases'), 'receipt names must explicitly bind the actual claim'
    assert verify_claims(claims,receipts[:2])[1].reasons==('missing:audit','cases'), 'every named required receipt must exist'
    assert verify_claims(claims,[*receipts[:2],dataclasses.replace(receipts[2],passed=False)])[1].reasons==('failed:audit','cases'), 'failed receipts contribute no coverage'
    assert verify_claims(claims,[*receipts[:2],dataclasses.replace(receipts[2],authority_scope=('production',))])[1].reasons==('scope:audit','cases'), 'authority proof must cover exactly the declared authority boundary'
    assert verify_claims(claims,[*receipts[:2],dataclasses.replace(receipts[2],cases=('no-write',))])[1].reasons==('cases',), 'one passing example cannot stand in for every declared case'
    dual=[dataclasses.replace(receipts[0],kind='audit',passed=False),*receipts[1:]]
    assert verify_claims(claims,dual)[0].reasons==('failed:w1','cases'), 'a failed receipt reports failed before kind when several checks fail'
    wider=[*receipts[:2],dataclasses.replace(receipts[2],authority_scope=('production','read-only','write'))]
    assert verify_claims(claims,wider)[1].reasons==('scope:audit','cases'), 'authority scope must be exact rather than a superset'
    all_covered=dataclasses.replace(receipts[0],cases=('normal','bad-frame'))
    assert verify_claims(claims,[all_covered,dataclasses.replace(receipts[1],passed=False),receipts[2]])[0].reasons==('failed:w2',), 'another good receipt cannot excuse an invalid required receipt'
    for kind,receipt_kind in [('local','unit'),('interface','browser'),('representative','replay')]:
        c=Claim(kind,kind,('case',),('r',));r=Receipt('r',receipt_kind,True,(kind,),('case','extra'))
        assert verify_claims([c],[r])==[ProofResult(kind,True,())], 'each proof kind has its own matching claim surface'
    assert verify_claims([],receipts)==[], 'no claims produce no proof conclusions'
    with pytest.raises(ValueError):verify_claims([Claim('empty','local',(),())],[])

@pytest.mark.skip('Part 4')
def test_private_policy_stream():
    """Gate controlled attempts before fake effects and future source pulls."""
    async def scenario():
        decisions=[Decision('sources','queries','bounded','query budget',limit('sources',5)),Decision('time','duration','bounded','time budget',limit('elapsed',120000,'ms')),
                   Decision('deps','dependency','bounded','safe family',Boundary('allowed','dependency',values=('stdlib','approved'))),
                   Decision('local','names','delegated',''),Decision('write','production write','locked','commander approves')]
        pulled=[];effects=[]
        async def source():
            for a in [Attempt('local',1,10),Attempt('deps',4,119,dependency='stdlib'),Attempt('local',5,120)]:pulled.append(a);yield a
            raise AssertionError('terminal policy must not pull future attempts')
        stream=enforce_stream(decisions,source(),effects.append);first=await anext(stream)
        assert json.loads(first)=={'event':'continue','decision':'local','reasons':[]} and len(pulled)==len(effects)==1, 'apply a delegated choice before emitting without prefetch'
        rest=[json.loads(x) async for x in stream]
        assert rest==[{'event':'continue','decision':'deps','reasons':[]},{'event':'stop','decision':'local','reasons':['sources','time']}], 'either budget stops and simultaneous violations form one ordered packet'
        assert len(pulled)==3 and len(effects)==2, 'stop happens before the blocked fake effect and any future attempt'
        async def locked():
            yield Attempt('write',5,120)
            raise AssertionError('a checkpoint must stop before future attempts')
        effects.clear();locked_lines=[x async for x in enforce_stream(decisions,locked(),effects.append)]
        assert len(locked_lines)==1 and locked_lines[0].endswith('\n') and json.loads(locked_lines[0])=={'event':'checkpoint','decision':'write','reasons':['commander approves']} and effects==[], 'locked checkpoint outranks simultaneous budgets and prevents the effect'
        async def denied():yield Attempt('deps',1,1,dependency='unapproved')
        assert [json.loads(x) async for x in enforce_stream(decisions,denied(),effects.append)]==[{'event':'stop','decision':'deps','reasons':['deps']}], 'numeric-free allowed dependencies are enforced as bounded choices'
        for attempt,reason in [(Attempt('local',5,10),'sources'),(Attempt('local',1,120),'time')]:
            async def one(): yield attempt
            effects.clear()
            assert [json.loads(x) async for x in enforce_stream(decisions,one(),effects.append)]==[{'event':'stop','decision':'local','reasons':[reason]}] and effects==[], 'each individual budget independently prevents the next effect'
        iface=Decision('iface','protocol','bounded','approved family',Boundary('allowed','interface',values=('http',)))
        async def accepted_interface(): yield Attempt('iface',interface='http')
        effects.clear()
        assert [json.loads(x) async for x in enforce_stream([iface],accepted_interface(),effects.append)]==[{'event':'continue','decision':'iface','reasons':[]}] and len(effects)==1, 'an allowed interface family can authorize a bounded choice'
        async def denied_interface(): yield Attempt('iface',interface='grpc')
        effects.clear()
        assert [json.loads(x) async for x in enforce_stream([iface],denied_interface(),effects.append)]==[{'event':'stop','decision':'iface','reasons':['iface']}] and effects==[], 'interface choices obey their own numeric-free allowlist'
        retry=Decision('retry','retries','bounded','retry budget',limit('retries',2))
        async def exhausted_retry():yield Attempt('local',retries=2)
        effects.clear()
        assert [json.loads(x) async for x in enforce_stream([decisions[3],retry],exhausted_retry(),effects.append)]==[{'event':'stop','decision':'local','reasons':['retry']}] and effects==[], 'a global retry budget prevents the next fake effect too'
        pulled.clear();effects.clear();stream=enforce_stream(decisions,source(),effects.append);await anext(stream);await stream.aclose()
        assert len(pulled)==len(effects)==1, 'closing after a packet must not read or execute another attempt'
    asyncio.run(scenario())

@pytest.mark.skip('Part 5')
def test_boundary_ast():
    """Boundary AST returns a permission and its actual blocking leaf occurrences."""
    context={'sources':5,'elapsed':120,'retries':1,'dependency':'stdlib','interface':'http'}
    sources=leaf('sources',5);time_limit=leaf('elapsed',120000,'ms');dependency={'allowed':{'metric':'dependency','values':['stdlib']}}
    assert evaluate_boundary({'all':[sources,time_limit]},context)=={'allowed':False,'blocked':((0,),(1,))}, 'reaching either stop threshold blocks the next action and reports both limits'
    assert evaluate_boundary({'any':[sources,dependency]},context)=={'allowed':True,'blocked':()}, 'a passing ANY hides failed sibling constraints'
    nested={'all':[{'any':[sources,time_limit]},dependency,{'all':[leaf('retries',1),sources]}]}
    assert evaluate_boundary(nested,context)=={'allowed':False,'blocked':((0,0),(0,1),(2,0),(2,1))}, 'failing groups collect every blocking occurrence in depth-first path order'
    before=json.dumps(nested,sort_keys=True);evaluate_boundary(nested,context)
    assert json.dumps(nested,sort_keys=True)==before, 'boundary evaluation cannot rewrite the specification'
    assert evaluate_boundary({'all':[dependency,leaf('retries',2)]},context)=={'allowed':True,'blocked':()}, 'ALL permits a choice when every child permits it'
    assert evaluate_boundary(dependency,context)=={'allowed':True,'blocked':()}, 'a numeric-free allowlist leaf can authorize a choice'
    assert evaluate_boundary({'allowed':{'metric':'interface','values':['grpc']}},context)=={'allowed':False,'blocked':((),)}, 'a failing root leaf uses the empty index path'
    assert evaluate_boundary(time_limit,{**context,'elapsed':119.999})['allowed'], 'milliseconds and seconds share the supplied canonical conversion'
    for malformed in ({'all':[]},{'limit':{'metric':'unknown','max':2}},{'allowed':{'metric':'dependency','values':[]}}):
        with pytest.raises(ValueError):evaluate_boundary(malformed,context)
