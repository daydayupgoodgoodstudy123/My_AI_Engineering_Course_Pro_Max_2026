"""Stable logical event calendar. Public events are not comparable objects."""
from .support import event_order
class CompletionCalendar:
    def __init__(self,events=()):self._events=list(events)
    def __bool__(self):return bool(self._events)
    def push(self,event):self._events.append(event)
    def peek_time(self):return min(self._events,key=event_order).time_us
    def pop(self):
        event=min(self._events,key=event_order)
        self._events.remove(event)
        return event
