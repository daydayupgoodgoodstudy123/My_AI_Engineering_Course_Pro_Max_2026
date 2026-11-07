"""Complete service intake; terminal schemas stay independent of review adaptation."""
from .polling import poll_pending
class PollDesk:
    def __init__(self,transport):self.transport=transport
    def run(self,requests):
        if len({r.task_id for r in requests})!=len(requests):raise ValueError('unique task IDs')
        if any(type(r.deadline)is not int or r.deadline<0 for r in requests):raise ValueError('nonnegative integer deadlines')
        return poll_pending(tuple(requests),self.transport)
