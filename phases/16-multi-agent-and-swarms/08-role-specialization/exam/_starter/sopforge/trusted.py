"""GIVEN complete trusted-code execution and per-case outcome primitives.

This executes only declared local trusted fixtures. It is NOT a sandbox: no
untrusted input, process isolation, resource limit or security claim is made.
"""
import hashlib
from dataclasses import dataclass
from .models import CaseEvidence,VerifierReport

def artifact_digest(artifact):return hashlib.sha256(artifact.code.encode('utf-8')).hexdigest()
class TrustedLoadError(Exception):
    def __init__(self,error):
        self.error_type=type(error).__name__;self.error_message=str(error)
        super().__init__(self.error_message)
@dataclass(frozen=True)
class CompiledArtifact:
    artifact_key:tuple
    source_digest:str
    code:object

def compile_trusted_artifact(artifact):
    """Compile the actual trusted module and bind its source identity; do not execute it."""
    try:program=compile(artifact.code,'<trusted-local-artifact>','exec')
    except Exception as error:raise TrustedLoadError(error)from error
    return CompiledArtifact((artifact.artifact_id,artifact.revision,artifact.spec_id,artifact.spec_revision),artifact_digest(artifact),program)

class ExecutionSession:
    """Complete one-verification namespace lifecycle with real source binding and once-exec."""
    def __init__(self,artifact):
        self.artifact_key=(artifact.artifact_id,artifact.revision,artifact.spec_id,artifact.spec_revision)
        self.source_digest=artifact_digest(artifact);self.namespace=None
    def accept(self,program):
        if program.artifact_key!=self.artifact_key or program.source_digest!=self.source_digest:raise ValueError('compiled artifact source binding mismatch')
        if self.namespace is None:
            namespace={}
            try:exec(program.code,namespace,namespace)
            except Exception as error:raise TrustedLoadError(error)from error
            self.namespace=namespace
        return self.namespace

def callable_lookup(program,name,session):
    """Consume a critic-approved named definition from this verification's bound namespace."""
    namespace=session.accept(program);fn=namespace[name]
    if not callable(fn):raise ValueError('declared artifact binding is not callable')
    return fn

def run_case(fn,case):
    try:got=fn(*case.args)
    except Exception as error:return CaseEvidence(case.case_id,case.args,case.expected,None,'error',type(error).__name__,str(error))
    kind='passed' if got==case.expected and type(got) is type(case.expected) else 'failure'
    return CaseEvidence(case.case_id,case.args,case.expected,got,kind)

def make_verifier_report(spec,artifact,cases,executed=True):
    return VerifierReport(spec.spec_id,spec.revision,artifact.artifact_id,artifact.revision,artifact_digest(artifact),executed,executed and all(c.kind=='passed' for c in cases),tuple(cases))

def outcome_kind(case):
    """Complete outcome classification; empty exception text is still an error."""
    if case.kind not in ('passed','failure','error'):raise ValueError('unknown case outcome')
    return case.kind

def make_load_failure(spec,artifact,error):
    return VerifierReport(spec.spec_id,spec.revision,artifact.artifact_id,artifact.revision,artifact_digest(artifact),False,False,(),(error.error_type,error.error_message))
