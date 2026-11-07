"""GIVEN complete report/source/spec link checks, shared by storage and SOP audit."""
from .trusted import artifact_digest

def bundle_link_issues(bundle):
    s,a,c,v=bundle.spec,bundle.artifact,bundle.critic,bundle.verifier;issues=[]
    if (a.spec_id,a.spec_revision)!=(s.spec_id,s.revision):issues.append('artifact-spec-link')
    expected=(s.spec_id,s.revision,a.artifact_id,a.revision)
    if (c.spec_id,c.spec_revision,c.artifact_id,c.artifact_revision)!=expected:issues.append('critic-artifact-link')
    if (v.spec_id,v.spec_revision,v.artifact_id,v.artifact_revision)!=expected or v.source_digest!=artifact_digest(a):issues.append('verifier-artifact-link')
    if v.executed and tuple(e.case_id for e in v.cases)!=tuple(c.case_id for c in s.cases):issues.append('verifier-case-link')
    return tuple(issues)

def require_bundle_links(bundle):
    issues=bundle_link_issues(bundle)
    if issues:raise ValueError(','.join(issues))
