"""Given correctly bound local async probe driver and finite TAP13 report subset."""
import asyncio,json
async def completed_probes(probes):
    async def run(probe):
        try:result=await probe.run()
        except Exception as exc:result={"error":True,"message":str(exc)}
        return probe,result
    tasks=[asyncio.create_task(run(probe)) for probe in probes]
    try:
        for task in asyncio.as_completed(tasks):yield await task
    finally:
        for task in tasks:
            if not task.done():task.cancel()
        await asyncio.gather(*tasks,return_exceptions=True)
def is_failure(result):return isinstance(result,dict) and result.get("error") is True
def tap_header(count):return "TAP version 13\n1.."+str(count)+( " # SKIP no probes" if count==0 else "")+"\n"
def tap_result(number,label,result,failed):
    label=label.replace("\r","\\r").replace("\n","\\n")
    status="not ok" if failed else "ok"
    return f"{status} {number} - {label}\n  ---\n  result: "+json.dumps(result,ensure_ascii=False,separators=(",",":"))+"\n  ...\n"
