"""Stable logical event calendar. Public events are not comparable objects."""
import heapq
from .support import event_order
class CompletionCalendar:
    def __init__(self,events=()):
        self._events=[(*event_order(event),event)for event in events]
        heapq.heapify(self._events)
    def __bool__(self):return bool(self._events)
    def push(self,event):heapq.heappush(self._events,(*event_order(event),event))
    def peek_time(self):return self._events[0][0]
    def pop(self):return heapq.heappop(self._events)[2]
