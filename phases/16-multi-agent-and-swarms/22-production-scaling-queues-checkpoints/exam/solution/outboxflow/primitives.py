from collections import deque

class CheckpointStore:
    """Read a declared immutable checkpoint log, choosing numeric latest within a run."""
    def __init__(self, checkpoints):
        self.records = tuple(checkpoints)
    def latest(self, run):
        rows = [x for x in self.records if x.run == run]
        return max(rows, key=lambda x: x.step) if rows else None

class BurstMailbox:
    """FIFO input ownership; drain returns every actual queued Envelope in order."""
    def __init__(self, messages=()):
        self._queue = deque(messages)
    def enqueue(self, message):
        self._queue.append(message)
    def receive(self):
        return self._queue.popleft()
    def __bool__(self):
        return bool(self._queue)
    def drain(self):
        out = []
        while self._queue:
            out.append(self._queue.popleft())
        return tuple(out)

class AgentQueue:
    """An actual dequeued message stays in RESPONSE until its exact UID is acknowledged."""
    def __init__(self):
        self.inbox = BurstMailbox()
        self.state = 'idle'
        self.response = None
    def enqueue(self, message):
        self.inbox.enqueue(message)
    def step(self):
        if self.state == 'idle' and self.inbox:
            self.state = 'processing'
        elif self.state == 'processing':
            self.response = self.inbox.receive()
            self.state = 'response'
        elif self.state == 'response':
            return self.response
        return self.response
    def acknowledge(self, uid):
        if self.state != 'response' or self.response.uid != uid:
            raise ValueError('acknowledgement must name the pending input')
        self.response = None
        self.state = 'idle'
