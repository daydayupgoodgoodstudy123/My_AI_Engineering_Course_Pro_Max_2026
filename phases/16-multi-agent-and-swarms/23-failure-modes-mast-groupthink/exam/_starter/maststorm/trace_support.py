"""Complete immutable sealed-trace shape and parent/effect binding. No accounting or recursive totals. Given."""
from .models import NodeTrace
class TraceCatalog:
    def __init__(self,context,report):
        self.report=report
        def validate(trace):
            if not isinstance(trace,NodeTrace)or trace.uid not in context.catalog:raise ValueError('bound sealed node required')
            node=context.catalog[trace.uid]
            if trace.service!=node.service:raise ValueError('sealed service binding')
            for attempt in trace.tries:
                if tuple(x.uid for x in attempt.children)!=tuple(x.uid for x in node.children):raise ValueError('sealed parent binding')
                for child in attempt.children:validate(child)
        for trace in report.nodes:validate(trace)
