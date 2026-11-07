"""GIVEN complete immutable trusted-artifact verifier workload and independent expected output."""
from .models import Case,Spec,Artifact,CriticReport,CaseEvidence,VerifierReport,Bundle
from .trusted import artifact_digest

def verifier_fixture(count=600):
    """Every table entry is a real function case; setup/expectation are outside timing."""
    cases=tuple(Case(f'case-{i:04d}',(i-count//2,i%37-18),(i-count//2)+(i%37-18))for i in range(count))
    table={case.args:case.expected for case in cases}
    source='TABLE='+repr(table)+'\ndef add_two(a,b):\n    return TABLE[(a,b)]\n'
    spec=Spec('table-spec',0,'add_two','add_two(a,b)','Exact declared finite addition cases',cases)
    artifact=Artifact('table-artifact',0,spec.spec_id,0,source)
    c=CriticReport(spec.spec_id,0,artifact.artifact_id,0,True,())
    evidence=tuple(CaseEvidence(case.case_id,case.args,case.expected,case.expected,'passed')for case in cases)
    v=VerifierReport(spec.spec_id,0,artifact.artifact_id,0,artifact_digest(artifact),True,True,evidence)
    return (spec,artifact),Bundle(spec,artifact,c,v)
