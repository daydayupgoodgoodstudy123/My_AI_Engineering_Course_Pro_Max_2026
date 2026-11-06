"""Verify every new pack and the existing Phase 13 references, with bounded parallelism."""
import argparse
import ast
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from zoneinfo import ZoneInfo

from build import REPO, build, inventory


def command(pack,flags):
    with tempfile.TemporaryDirectory(prefix="coderpad-report-") as directory:
        report=Path(directory)/"report.json"
        result=subprocess.run([sys.executable,"run_tests.py",*flags,"-q","--json-report",str(report)],
                              cwd=pack,capture_output=True,text=True,timeout=20)
        score=json.loads(report.read_text()) if report.exists() else None
        return result,score


def check_pack(row,target,timestamp):
    pack=target/row["path"]/"coderpad"
    for p in pack.rglob("*.py"):
        ast.parse(p.read_text(),filename=str(p),feature_version=(3,10))
    for p in pack.rglob("*.md"):
        opened=False
        for line in p.read_text().splitlines():
            if line.startswith("```"):
                if not opened and not line[3:].strip():raise AssertionError(f"Untagged fence: {p}")
                opened=not opened
        if opened:raise AssertionError(f"Unclosed fence: {p}")
    before=hashlib.sha256((pack/"starter/main.py").read_bytes()).hexdigest()
    collect=subprocess.run([sys.executable,"run_tests.py","--list"],cwd=pack,capture_output=True,text=True,timeout=20)
    if collect.returncode or collect.stdout.count(".CoreTests.")!=6 or collect.stdout.count(".BonusTests.")!=2:
        raise AssertionError("Collection: "+collect.stdout+collect.stderr)
    ref,score=command(pack,["--solution"])
    if ref.returncode!=0 or score is None or not score["success"]:
        raise AssertionError("Reference: "+ref.stdout+ref.stderr)
    initial,baseline=command(pack,[])
    if initial.returncode!=1 or baseline is None or baseline["success"] or baseline["counts"]["core"]["passed"]!=0:
        raise AssertionError("Invalid TODO baseline: "+initial.stdout+initial.stderr)
    after=hashlib.sha256((pack/"starter/main.py").read_bytes()).hexdigest()
    if before!=after:raise AssertionError("Learner source changed")
    metadata={"verified_at":timestamp,"python":sys.version.split()[0],
              "reference_sha256":hashlib.sha256((pack/"solution/main.py").read_bytes()).hexdigest(),
              "starter_sha256":before,"reference":score,"starter_baseline":baseline}
    (pack/"verification.txt").write_text("Command: python3 run_tests.py --solution -q\n"+json.dumps({k:v for k,v in metadata.items() if k!="starter_baseline"},indent=2)+"\n"+ref.stdout+ref.stderr)
    (pack/"starter_baseline.txt").write_text("Command: python3 run_tests.py -q\nExpected exit: 1 (unfinished TODOs)\n"+json.dumps({"verified_at":timestamp,"python":metadata["python"],"starter_sha256":before,"result":baseline},indent=2)+"\n")
    return {"path":row["path"],"reference":score["counts"],"starter":baseline["counts"],"unchanged":True}


def existing_reference(pack):
    before=hashlib.sha256((pack/"starter/main.py").read_bytes()).hexdigest()
    result,score=command(pack,["--solution"])
    if result.returncode or score is None or not score["success"]:
        raise AssertionError("Existing reference failed "+str(pack)+": "+result.stdout+result.stderr)
    if hashlib.sha256((pack/"starter/main.py").read_bytes()).hexdigest()!=before:
        raise AssertionError("Existing learner code changed")
    return {"path":str(pack.parent.relative_to(REPO)),"reference":score["counts"],"existing":True,"unchanged":True}


def verify(target,workers=4):
    if not build(target,check=True):return 1
    rows=inventory();timestamp=datetime.now(ZoneInfo("America/New_York")).isoformat(timespec="seconds")
    results=[];failures=[];done=0
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures={executor.submit(check_pack,r,target,timestamp):r["path"] for r in rows}
        existing=sorted((REPO/"phases/13-tools-and-protocols").glob("[0-9][0-9]-*/coderpad"))
        if len(existing)!=31:raise ValueError("Expected 31 existing Phase 13 packs")
        futures.update({executor.submit(existing_reference,p):str(p) for p in existing})
        for future in as_completed(futures):
            try:results.append(future.result())
            except Exception as exc:failures.append({"path":futures[future],"error":str(exc)});print("FAIL",futures[future],str(exc)[:180],flush=True)
            done+=1
            if done%40==0 or done==len(futures):print(f"Verified {done}/{len(futures)} packs; failures {len(failures)}",flush=True)
    core=sum(r["reference"]["core"]["total"] for r in results)
    bonus=sum(r["reference"]["bonus"]["total"] for r in results)
    summary={"verified_at":timestamp,"python":sys.version.split()[0],"packs":len(results),
             "new_packs":sum(not r.get("existing",False) for r in results),"existing_phase13_packs":sum(r.get("existing",False) for r in results),
             "core_cases":core,"bonus_cases":bonus,"total_cases":core+bonus,
             "learner_sources_unchanged_by_tests":all(r["unchanged"] for r in results),
             "failures":failures,"packs_detail":sorted(results,key=lambda r:r["path"])}
    (target/"CODERPAD_VALIDATION.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n")
    display={k:v for k,v in summary.items() if k not in ("packs_detail","failures")}
    display["failure_count"]=len(failures)
    display["first_failures"]=failures[:3]
    print(json.dumps(display,ensure_ascii=False,indent=2),flush=True)
    return 1 if failures else 0


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target",type=Path,help="Verify generated files and write logs under this root")
    parser.add_argument("--workers",type=int,default=4,choices=range(1,9))
    args=parser.parse_args()
    if args.target:raise SystemExit(verify(args.target.resolve(),args.workers))
    with tempfile.TemporaryDirectory(prefix="curriculum-coderpad-") as tmp:
        target=Path(tmp)
        if not build(target):raise SystemExit(1)
        raise SystemExit(verify(target,args.workers))
