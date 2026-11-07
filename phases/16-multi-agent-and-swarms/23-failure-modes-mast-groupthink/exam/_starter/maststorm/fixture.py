from .models import ReplayReport

def breaker_fixture(count=40000,window=20000):
    if count<window or count%2 or window%2:raise ValueError('even complete performance stream required')
    outcomes=tuple(i%2==0 for i in range(count))
    rows=tuple((i,True,'CLOSED',min(i+1,window),((i+1)//2 if i<window else window//2))for i in range(count))
    return outcomes,window,ReplayReport(rows,outcomes[max(0,count-window):],'CLOSED',count//2 if count<window else window//2)
