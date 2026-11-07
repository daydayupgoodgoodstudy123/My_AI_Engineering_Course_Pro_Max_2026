"""Complete global identity resolution, occurrence expansion and leaf dispatch."""
from .models import GroupEntry,Occurrence,ReviewBundle
class ReviewCatalog:
    """Finite typed bundle with globally unique file, issue and group IDs.

    Lookup, all ordered shared membership occurrences, and canonical unique
    issue collection include every declared canonical issue, even if unreferenced.
    Membership counts instead include every declared group reference.
    Domain schema/file/line checks are not here.
    """
    def __init__(self,bundle):
        self.bundle=bundle;self.files={f.path:f for f in bundle.files};self.issues={i.issue_id:i for i in bundle.issues};self._groups=[];self._occurrences=[]
        if len(self.files)!=len(bundle.files)or len(self.issues)!=len(bundle.issues):raise ValueError('unique global file and issue identities')
        seen=set()
        def walk(group,path):
            if group.group_id in seen:raise ValueError('unique global group identities')
            seen.add(group.group_id);here=path+(group.group_id,);self._groups.append(GroupEntry(here,group))
            for identity in group.issues:self._occurrences.append(Occurrence(here+(identity,),group,self.issues[identity]))
            for child in group.children:walk(child,here)
        for group in bundle.groups:walk(group,('artifact',))
    def group_entries(self):return tuple(self._groups)
    def occurrences(self):return tuple(self._occurrences)
    def own_occurrences(self,group_id):return tuple(o for o in self._occurrences if o.group.group_id==group_id)
    def canonical_issues(self):return tuple(self.bundle.issues)
    def file(self,path):return self.files.get(path)
def review_leaf(artifact):
    """Tag-aware local leaf dispatch. Text is opaque even if it resembles JSON."""
    if artifact.type=='text':
        if not isinstance(artifact.data,str):raise ValueError('text leaf')
        return 'text',artifact.data
    if artifact.type=='structured'and isinstance(artifact.data,ReviewBundle):return 'structured',ReviewCatalog(artifact.data)
    raise ValueError('typed nested review leaf required')

def all_group_findings(groups):
    return tuple(finding for group in groups for finding in (*group.findings,*all_group_findings(group.children)))
