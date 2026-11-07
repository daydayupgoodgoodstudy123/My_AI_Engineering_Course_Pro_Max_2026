"""Owned inspectable shared message pool; no scheduler or agent policy is stored here."""
from copy import deepcopy
from threading import RLock

class SharedState:
    def __init__(self,messages=()):
        self._messages=[];self._latest={};self._lock=RLock()
        for message in messages:self.append(message)

    def append(self,message):
        """Own a completed message and retain the latest occurrence for its canonical sender."""
        with self._lock:
            owned=deepcopy(message)
            self._messages.append(owned)

    def snapshot(self):
        """Return an independent complete message pool, including nested payloads."""
        with self._lock:return deepcopy(self._messages)

    def last_by(self,name):
        """Return an owned latest message for this sender, or None if the sender is absent."""
        with self._lock:
            for message in reversed(self._messages):
                if message['from']==name:return deepcopy(message)
            return None
