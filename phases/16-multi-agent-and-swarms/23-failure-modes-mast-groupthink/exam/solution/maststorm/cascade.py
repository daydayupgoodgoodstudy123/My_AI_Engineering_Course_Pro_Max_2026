from .models import Invocation,AttemptTrace,NodeTrace,CascadeReport

def invoke_attempt(context,node):
    now=context.clock.tick()
    if context.remaining==0:
        return Invocation(node.uid,node.service,'budget-exhausted',False,None,now,context.remaining)
    breaker=context.breakers[node.service]
    if not breaker.allow(now):
        return Invocation(node.uid,node.service,'short-circuit',False,None,now,context.remaining)
    context.used+=1
    success=context.provider.invoke(node)
    breaker.record(success,now)
    return Invocation(node.uid,node.service,'invoked',True,success,now,context.remaining)

def execute_retry_tree(context,node):
    if node.uid in context.effects:return NodeTrace(node.uid,node.service,'cached',())
    tries=[];success=False
    for ordinal in range(1,node.attempts+1):
        children=tuple(execute_retry_tree(context,child)for child in node.children)
        if all(child.status in ('success','cached')for child in children):
            invocation=invoke_attempt(context,node)
        else:
            invocation=Invocation(node.uid,node.service,'dependency-failed',False,None,context.clock.tick(),context.remaining)
        tries.append(AttemptTrace(ordinal,children,invocation))
        if invocation.actual and invocation.success:
            context.effects[node.uid]=True;success=True;break
    return NodeTrace(node.uid,node.service,'success'if success else'failed',tuple(tries))

def replay_cascade(context):
    nodes=tuple(execute_retry_tree(context,node)for node in context.nodes)
    return CascadeReport(context.record.root,context.record.uid,nodes,context.used,context.remaining,tuple(context.provider.calls),tuple(context.effects))
