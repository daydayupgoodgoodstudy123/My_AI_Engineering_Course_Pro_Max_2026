"""GIVEN complete finite stage/handle identity catalog and report link validation."""
from .bindings import bundle_link_issues
from .models import Bundle
ROLE_INPUTS={'planner':{},'executor':{'spec':('planner','spec')},'critic':{'spec':('planner','spec'),'artifact':('executor','artifact')},'verifier':{'spec':('planner','spec'),'artifact':('executor','artifact')}}
ROLE_OUTPUT={'planner':('spec','spec'),'executor':('artifact','artifact'),'critic':('critique','critic-report'),'verifier':('verification','verifier-report')}
class SOPCatalog:
    def __init__(self,root,records):
        self.records={r.handle:r for r in records};self.stages={}
        if len(self.records)!=len(records):raise ValueError('duplicate full record handle')
        def visit(stage,path,active):
            if id(stage) in active:raise ValueError('stage cycle')
            if stage.role not in ROLE_INPUTS:raise ValueError('unknown role')
            if len({c.name for c in stage.children})!=len(stage.children):raise ValueError('duplicate child name')
            self.stages[path]=stage
            for child in stage.children:visit(child,path+(child.name,),active|{id(stage)})
        visit(root,(root.name,),set())
    def record(self,handle):
        if handle not in self.records:raise ValueError('unknown full record handle')
        return self.records[handle]
    def child_path(self,path,child):return path+(child.name,)
    def payload_kind(self,record):
        from .models import Spec,Artifact,CriticReport,VerifierReport
        for cls,kind in ((Spec,'spec'),(Artifact,'artifact'),(CriticReport,'critic-report'),(VerifierReport,'verifier-report')):
            if isinstance(record.payload,cls):return kind
        return 'unrecognized'
    def payload_issues(self,record):
        from .models import Spec,Artifact,CriticReport,VerifierReport
        from .trusted import artifact_digest
        value=record.payload;all_values=tuple(r.payload for r in self.records.values())
        if isinstance(value,Artifact):
            return ()if any(isinstance(s,Spec)and(s.spec_id,s.revision)==(value.spec_id,value.spec_revision)for s in all_values)else('artifact-spec-link',)
        if isinstance(value,(CriticReport,VerifierReport)):
            artifacts=tuple(a for a in all_values if isinstance(a,Artifact)and(a.artifact_id,a.revision,a.spec_id,a.spec_revision)==(value.artifact_id,value.artifact_revision,value.spec_id,value.spec_revision))
            if not artifacts:return ('report-artifact-link',)
            if isinstance(value,VerifierReport)and not any(artifact_digest(a)==value.source_digest for a in artifacts):return ('verifier-source-link',)
        return ()
    def stage_link_issues(self,stage):
        from .models import Spec,Artifact,CriticReport,VerifierReport
        inputs={port:self.record(handle).payload for port,handle in stage.inputs}
        outputs={port:self.record(handle).payload for port,handle in stage.outputs}
        spec=inputs.get('spec');artifact=inputs.get('artifact');issues=[]
        if stage.role=='executor' and isinstance(spec,Spec):
            value=outputs.get('artifact')
            if isinstance(value,Artifact)and(value.spec_id,value.spec_revision)!=(spec.spec_id,spec.revision):issues.append(('stage-artifact-spec-link','artifact'))
        if stage.role in ('critic','verifier')and isinstance(spec,Spec)and isinstance(artifact,Artifact):
            port='critique'if stage.role=='critic'else'verification';value=outputs.get(port)
            if isinstance(value,(CriticReport,VerifierReport))and(value.spec_id,value.spec_revision,value.artifact_id,value.artifact_revision)!=(spec.spec_id,spec.revision,artifact.artifact_id,artifact.revision):issues.append(('stage-report-artifact-link',port))
        return tuple(issues)
