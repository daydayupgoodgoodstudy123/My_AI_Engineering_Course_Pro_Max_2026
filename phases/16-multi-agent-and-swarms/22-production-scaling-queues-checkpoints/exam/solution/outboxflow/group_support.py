"""Complete full-UID endpoint/mailbox binding and typed origin intake. Given, not a route solver."""
from .models import BoundMessage

class GroupCatalog:
    def __init__(self,root,messages):
        messages=tuple(messages)
        self.root=root
        self.groups={}
        self.endpoints={}
        self.mailboxes={}
        def walk(group,path):
            path=path+(group.uid,)
            if group.uid in self.groups:raise ValueError('tree group UID must be unique')
            self.groups[group.uid]=(group,path)
            for uid,role in ((group.admin,'admin'),*((uid,'leaf') for uid in group.agents)):
                if uid in self.endpoints:raise ValueError('complete endpoint UID must be unique')
                self.endpoints[uid]=(path,role)
                self.mailboxes[uid]=[]
            for child in group.children:walk(child,path)
        walk(root,())
        self.messages={m.uid:m for m in messages}
        if len(self.messages)!=len(tuple(messages)):raise ValueError('unique message UID required')
        assigned=[]
        for group,path in self.groups.values():
            for uid in group.messages:
                m=self.messages[uid]
                if self.endpoints[m.source][0]!=path:raise ValueError('own declaration must bind own source group')
                assigned.append(uid)
            if any(uid not in self.messages for uid in group.exports):raise ValueError('known declared export required')
        if len(assigned)!=len(self.messages) or len(set(assigned))!=len(assigned):raise ValueError('one own group per message required')
    def bind(self,uid):
        m=self.messages[uid]
        source,role=self.endpoints[m.source]
        destination,_=self.endpoints[m.destination]
        valid=(m.kind=='leaf' and role=='leaf')or(m.kind=='summary' and role=='admin')
        return BoundMessage(m,source,destination,valid)
    def admin(self,path):
        group,bound=self.groups[path[-1]]
        assert bound==path
        return group.admin
    def group(self,path):
        return self.groups[path[-1]][0]
    def deliver(self,uid):
        m=self.messages[uid]
        self.mailboxes[m.destination].append(m)
    def local(self,group_uid,local_name):
        """Full scoped binding helper keeps same local name independent across groups."""
        group,path=self.groups[group_uid]
        candidates=[uid for uid in (group.admin,*group.agents) if uid.rsplit('/',1)[-1]==local_name]
        if len(candidates)!=1:raise ValueError('one declared scoped endpoint required')
        return candidates[0]


def deliver_audit(catalog,audit,run):
    """Complete execution driver consumes the candidate route audit, without deciding any route. Given."""
    for row in audit.own:
        if row.accepted and row.run==run:
            catalog.deliver(row.uid)
    for child in audit.children:
        deliver_audit(catalog,child,run)
