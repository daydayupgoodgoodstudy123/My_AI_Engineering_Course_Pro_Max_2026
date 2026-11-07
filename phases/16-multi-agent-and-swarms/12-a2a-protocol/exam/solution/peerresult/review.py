"""Nested file/span validation and hierarchical reports over resolved review memberships."""
from .models import Finding,GroupAudit,ReviewAudit
from .review_support import review_leaf,all_group_findings
def audit_review(artifact):
    """Build a nested domain report over the supplied global catalog.

    Declared file line counts and issue/group coordinates are non-bool integers.
    A child group stays in its parent's file and declared span. Each issue stays
    within its own group's file/span and the declared file's physical line range.
    Shared issue identities and all membership paths are fully resolved Given.
    """
    mode,value=review_leaf(artifact)
    if mode=='text':return ReviewAudit(mode,0,0,(),value)
    root_findings=[]
    if value.bundle.schema!='review-tree-v1':root_findings.append(Finding(('artifact',),'schema'))
    def audit_group(group,path,parent=None):
        findings=[];file=value.file(group.file)
        if group.schema!='issue-group-v1':findings.append(Finding(path,'schema'))
        if file is None:findings.append(Finding(path,'group-file'))
        elif not(1<=group.start<=group.end<=file.lines):findings.append(Finding(path,'group-lines'))
        if parent is not None and not(group.file==parent.file and parent.start<=group.start<=group.end<=parent.end):findings.append(Finding(path,'child-span'))
        for occurrence in value.own_occurrences(group.group_id):
            issue=occurrence.issue;issue_file=value.file(issue.file)
            if issue_file is None or issue.file!=group.file:findings.append(Finding(occurrence.path,'issue-file'))
            if issue_file is not None and not(1<=issue.start<=issue.end<=issue_file.lines):findings.append(Finding(occurrence.path,'issue-lines'))
            if not(group.start<=issue.start<=issue.end<=group.end):findings.append(Finding(occurrence.path,'group-membership'))
        children=tuple(audit_group(child,path+(child.group_id,),group)for child in group.children)
        return GroupAudit(group.group_id,path,tuple(findings),children)
    groups=tuple(audit_group(group,('artifact',group.group_id))for group in value.bundle.groups)
    findings=tuple(root_findings)+all_group_findings(groups)
    return ReviewAudit(mode,len(value.canonical_issues()),len(value.occurrences()),findings,groups=groups)
