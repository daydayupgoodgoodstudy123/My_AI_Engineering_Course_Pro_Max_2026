"""Given in-process state adapter and per-user lock primitive, without admission policy."""
from contextlib import contextmanager
from threading import RLock,local
class MemoryStore:
    def __init__(self):
        self.states={};self._locks={};self._registry=RLock();self._local=local()
    @contextmanager
    def atomic(self,user):
        with self._registry:lock=self._locks.setdefault(user,RLock())
        with lock:
            held=getattr(self._local,"held",())
            self._local.held=held+(user,)
            try:yield
            finally:self._local.held=held
    def held(self,user):return user in getattr(self._local,"held",())
    def load(self,user):return self.states.get(user)
    def save(self,user,state):self.states[user]=state
