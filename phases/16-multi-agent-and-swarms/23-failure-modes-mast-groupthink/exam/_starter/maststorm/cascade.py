def invoke_attempt(context,node):
    raise NotImplementedError('share actual invocation budget and breaker admission')

def execute_retry_tree(context,node):
    raise NotImplementedError('resume causal effects without replaying successful siblings')

def replay_cascade(context):
    raise NotImplementedError('retain root-wide budget and complete actual outcome trace')
