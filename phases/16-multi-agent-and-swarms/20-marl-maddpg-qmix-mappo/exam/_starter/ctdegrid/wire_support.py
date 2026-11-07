"""Given complete CSV cell codec, async iteration and publication/close lifecycle, no domain row."""
import csv,json
FIELDS=('episode','step','obs0','q0','action0','reward0','obs1','q1','action1','reward1','done','training_state','policy')
def cell(value):return json.dumps(value,ensure_ascii=False,separators=(',',':'),allow_nan=False)
class CSVWriter:
    def __init__(self,handle):self.handle=handle;self.writer=csv.DictWriter(handle,fieldnames=FIELDS);self.writer.writeheader();self.closed=False
    async def write(self,row):
        if self.closed:raise ValueError('closed CSV publication')
        self.writer.writerow(row)
    async def close(self):self.closed=True
async def publish(source,project,writer):
    try:
        async for transition in source:await writer.write(project(transition))
    finally:
        await source.aclose();await writer.close()
