from .models import Envelope, BurstReport

def burst_fixture(count=150000):
    messages = tuple(Envelope('m'+str(i), 'run'+str(i % 4), i % 7 - 3, 'task:'+str(i)) for i in range(count))
    counts = tuple(('run'+str(k), len(range(k, count, 4))) for k in range(min(4,count)))
    total = sum(i % 7 - 3 for i in range(count))
    return messages, BurstReport(messages, counts, total)
