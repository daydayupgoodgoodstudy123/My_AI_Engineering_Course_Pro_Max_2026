"""Build remaining Phase 00–20 interview packs; never overwrite existing learner work.

Sources: routes.py, kernels/*.py, notes.py and local lesson docs/code metadata.
python3 build.py --check validates published authored material without writing.
python3 build.py --output /tmp/coderpad-preview builds an independent preview.
"""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import re
import sys

from kernels import load
from notes import NOTES
from routes import PHASE_ZH, ROUTES

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SHARED_RUNNER = REPO / "scripts/coderpad_phase13/runner_template.py"

IMPORTS = {"math":"import math", "re":"import re", "json":"import json", "hashlib":"import hashlib",
           "itertools":"import itertools", "copy":"import copy", "Counter":"from collections import Counter",
           "deque":"from collections import deque"}


def inventory():
    kernels = load()
    if set(kernels) != set(NOTES):
        raise ValueError(f"Missing notes: {set(kernels)-set(NOTES)}; extra: {set(NOTES)-set(kernels)}")
    rows = []
    for phase_id, selections in sorted(ROUTES.items()):
        phases = sorted((REPO / "phases").glob(phase_id + "-*"))
        if len(phases) != 1:
            raise ValueError(f"Ambiguous phase: {phase_id}")
        phase = phases[0]
        lessons = sorted(p for p in phase.glob("[0-9][0-9]-*") if p.is_dir())
        pairs = [pair.split("/") for pair in selections.split()]
        if len(lessons) != len(pairs):
            raise ValueError(f"Phase {phase_id}: {len(lessons)} lessons vs {len(pairs)} selections")
        for lesson, (core, bonus) in zip(lessons, pairs):
            if core == bonus or core not in kernels or bonus not in kernels:
                raise ValueError(f"Invalid selection {lesson}: {core}/{bonus}")
            source = lesson / "docs/en.md"
            objectives = []
            title = lesson.name
            if source.exists():
                lines = source.read_text(encoding="utf-8").splitlines()
                title = next((line[2:] for line in lines if line.startswith("# ")), title)
                active = False
                for line in lines:
                    if line.startswith("## Learning Objectives"):
                        active = True
                    elif active and line.startswith("## "):
                        break
                    elif active and line.startswith("- "):
                        objectives.append(line[2:])
            else:
                sources = sorted((lesson / "code").glob("*.py"))
                source = next((p for p in sources if p.name == "main.py"), sources[0] if sources else None)
                if source is None:
                    raise ValueError(f"No lesson source: {lesson}")
            k, b = kernels[core], kernels[bonus]
            valid = [c for c in b["cases"] if "raises" not in c]
            invalid = [c for c in b["cases"] if "raises" in c]
            bonus_cases = [valid[0], invalid[-1] if invalid else valid[1]]
            rows.append({"path": str(lesson.relative_to(REPO)), "phase": phase.name,
                         "phase_id": phase_id, "lesson": lesson.name, "title": title,
                         "objectives": objectives, "source": str(source.relative_to(REPO)),
                         "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                         "source_kind": "lesson_docs" if source.name == "en.md" else "code_missing_docs",
                         "core": core, "bonus": bonus, "core_cases": k["cases"], "bonus_cases": bonus_cases})
    if len(rows) != 512:
        raise ValueError(f"Expected 512 remaining lessons, found {len(rows)}")
    return rows


SUPPORT = '''"""Local implementation selection and strict fixture assertions, no network."""
import builtins
import copy
import importlib.util
import json
import math
import os
from pathlib import Path
import sys
import unittest

root = Path(__file__).resolve().parent
selected = os.environ.get("CODERPAD_IMPLEMENTATION", "starter")
if selected not in ("starter", "solution"):
    raise ValueError("Unknown implementation")
spec = importlib.util.spec_from_file_location("coderpad_target", root / selected / "main.py")
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)

class ContractCase(unittest.TestCase):
    def assert_contract_value(self, actual, expected):
        if type(expected) is bool or expected is None:
            self.assertIs(actual, expected)
        elif type(expected) in (int, float):
            self.assertIn(type(actual), (int, float))
            self.assertTrue(math.isclose(actual, expected, rel_tol=1e-8, abs_tol=1e-8), f"{actual!r} != {expected!r}")
        elif isinstance(expected, list):
            self.assertIsInstance(actual, list)
            self.assertEqual(len(actual), len(expected))
            for a, e in zip(actual, expected):
                self.assert_contract_value(a, e)
        elif isinstance(expected, dict):
            self.assertIsInstance(actual, dict)
            self.assertEqual(set(actual), set(expected))
            for k, e in expected.items():
                self.assert_contract_value(actual[k], e)
        else:
            self.assertEqual(type(actual), type(expected))
            self.assertEqual(actual, expected)

    def run_contract(self, function, case):
        args = copy.deepcopy(case["args"])
        before = copy.deepcopy(args)
        if "raises" in case:
            with self.assertRaises(getattr(builtins, case["raises"])):
                getattr(m, function)(*args)
        else:
            self.assert_contract_value(getattr(m, function)(*args), case["expected"])
        self.assertEqual(json.dumps(args, sort_keys=True), json.dumps(before, sort_keys=True), "Input mutation")
'''

TESTS = '''"""Visible, frozen examples; expected outputs are authored in the kernel source."""
import json
from pathlib import Path
from _support import ContractCase

DATA = json.loads((Path(__file__).resolve().parents[1] / "fixtures.json").read_text())

class CoreTests(ContractCase):
    pass

class BonusTests(ContractCase):
    pass

def make_test(function, case):
    def test(self):
        self.run_contract(function, case)
    return test

for label, cls in (("core", CoreTests), ("bonus", BonusTests)):
    function = DATA[label]["function"]
    for number, case in enumerate(DATA[label]["cases"], 1):
        setattr(cls, f"test_{number:02d}_{function}", make_test(function, case))
# unittest also discovers class aliases left at module scope.
del label, cls, function, number, case
'''


def implementation(row, starter=False):
    kernels = load()
    snippets = [kernels[row[mode]]["code"] for mode in ("core", "bonus")]
    tree = ast.parse("\n".join(snippets))
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    imports = "\n".join(value for key, value in IMPORTS.items() if key in names)
    if starter:
        for number, node in enumerate(tree.body, 1):
            if isinstance(node, ast.FunctionDef):
                node.body = [ast.Expr(ast.Constant(load()[row["core" if number == 1 else "bonus"]]["contract"])),
                             ast.Raise(ast.Call(ast.Name("NotImplementedError", ast.Load()),
                                                [ast.Constant(f"TODO {number}: {node.name}; see PROMPT.md")], []))]
        ast.fix_missing_locations(tree)
    code = ast.unparse(tree)
    header = f'''"""Original interview practice for {row['phase']}/{row['lesson']}.

Local source: {row['source']} (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
'''
    return header + imports + "\n\n" + code + "\n"


def render_pack(row):
    kernels = load()
    core, bonus = kernels[row["core"]], kernels[row["bonus"]]
    source = Path(row["source"]).relative_to(row["path"])
    source_link = "../" + str(source)
    source_note = "原课 docs/en.md 缺失，本套依据已有 code 文件与目录主题设计；未补写原课程正文。" if row["source_kind"] == "code_missing_docs" else "题目依据本地课程正文与学习目标，抽取适合现场实现的编码范围。"
    objectives = "\n".join("- " + objective for objective in row["objectives"][:6]) or "- 原课程没有可提取的 Learning Objectives；请对照上述代码来源和本题限定合同。"
    prompt = f'''# {row['title']} — interview coding slice

Original practice · 45-minute suggested upper limit · Python 3.10+ · stdlib only.
This is not an Edison Scientific question or official hiring rubric.

## Scenario

You maintain the `{row['lesson']}` component. Complete its core `{core['function']}` operation,
then implement the independent `{bonus['function']}` extension if time remains.
The scope is intentionally one implementable slice of the lesson; no full model, training run,
cloud service, filesystem deployment, provider API, or GPU integration is required.

## Core

```python
{core['signature']}
```

{core['contract']}

## Bonus

```python
{bonus['signature']}
```

{bonus['contract']}

## Shared rules and material

- Edit `starter/main.py` and keep both public signatures intact. Inputs must remain unchanged, including on failure.
- Read `fixtures.json` for six core and two bonus examples, plus `tests/test_exam.py` and `_support.py` for the test harness.
- Floating outputs use absolute/relative tolerance 1e-8. Booleans are distinct from integers.
- You may add meaningful tests in a new `tests/test_candidate.py`; keep supplied fixtures/tests intact.
- Only behavior expressly specified here is scored. Exercise simplifications are not claims about live frameworks or protocols.
- The exact kernel may recur in related lessons; `SCOPE.json` identifies core/bonus names. Repeated content is practice, not an unseen test.

## Commands (inside this coderpad directory)

```bash
python3 run_tests.py --list
python3 run_tests.py --core
python3 run_tests.py --core -k 01
python3 run_tests.py --bonus
python3 run_tests.py
```

Use your own timer. At minute 45, save, record the current result, and then review.
Keep `solution/`, `INTERVIEWER.md`, the original lesson implementation and external answer assistance closed during an independent attempt.
The local filesystem cannot actually hide answers or enforce a timer.
'''
    readme = f'''# {row['phase_id']}/{row['lesson'][:2]}：{row['title']}

**45 分钟 CoderPad 风格练习：核心「{core['label']}」，加分「{bonus['label']}」。**

{source_note}
来源：[本地课程材料]({source_link})。准确输入输出合同见 [PROMPT.md](PROMPT.md)，
具体输入与期望结果见 [fixtures.json](fixtures.json)。
本套与第 13 章试点使用相同的核心/加分测试入口；全部标准库、离线运行。
45 分钟是建议练习上限，基础题可能提前完成，难度与用时尚未经过学员计时校准。

## 从这里开始

在本文件所在的 `coderpad/` 打开终端：

```bash
python3 --version
python3 run_tests.py --list
python3 run_tests.py --core
```

要求 Python 3.10+。`--list` 只收集测试。未完成 TODO 时核心失败正常；
实跑参考记录见 [verification.txt](verification.txt)，初始成绩见 [starter_baseline.txt](starter_baseline.txt)。

## 本次写什么

| 优先级 | 文件与函数 | 练习能力 |
| --- | --- | --- |
| 核心 | `starter/main.py` → `{core['function']}` | {core['label']} |
| 加分 | 同文件 → `{bonus['function']}` | {bonus['label']} |

核心和加分相互独立；只修改 starter，可以新增自己的测试文件。
测试辅助文件不包含这两个 TODO 的答案；原课完整实现和参考答案仅供计时结束后复盘。
相关课共享基础算法，具体组合和 kernel 名称见 [SCOPE.json](SCOPE.json)。
如果曾做过同一核心，请把这轮标成“重复练习”，不要当作未见题成绩。

## 原课学习目标（阅读范围，不是额外评分需求）

{objectives}

## 面试节奏

| 时间 | 行动 |
| --- | --- |
| 0–5 分钟 | 阅读合同和例子，复述输入输出，提出澄清 |
| 5–12 分钟 | 讲实现顺序，完成一个成功路径 |
| 12–30 分钟 | 核心边界、错误处理、不可变输入 |
| 30–39 分钟 | 核心通过后做加分，补自己的反例测试 |
| 39–45 分钟 | 跑核心和全量，保存，解释复杂度与限制 |

```bash
python3 run_tests.py --core
python3 run_tests.py --bonus
python3 run_tests.py
# 计时结束后才选择独立参考答案，不覆盖 starter
python3 run_tests.py --solution
```

每套核心 6 cases、加分 2 cases。新增自己的测试会在全量命令执行，但不会并入这两个固定分母。
`python3 -m unittest discover -s tests -v` 默认也测试 starter。
本地没有真正隐藏的评测服务器，也不会强制停止计时。

需要主持时可说：“按这套 [INTERVIEWER.md](INTERVIEWER.md) 开始面试，一次只问一个问题。”
结束后复制 [REVIEW_TEMPLATE.md](REVIEW_TEMPLATE.md)，先记录计时成绩，再查看
[中文复盘解释](solution/EXPLANATION.md)。重做前另存自己的代码，避免用 git reset/clean 重置上层课程。
'''
    explanation = f'''# 参考解释：{row['title']}

## 核心：{core['label']}

{NOTES[row['core']]}

准确合同：{core['contract']}

## 加分：{bonus['label']}

{NOTES[row['bonus']]}

准确合同：{bonus['contract']}

## 复盘

将每个失败映射到合同与 fixtures 的具体 case，区分公式、索引、类型、边界和状态问题。
比较 [main.py](main.py) 后关掉答案，自己重写失败部分，再补一个原测试没有直接覆盖的反例。
说明核心的时间、空间复杂度；数据扩大后会先遇到什么限制？
本套只证明这些纯函数符合限定合同。参考实现不是完整模型、协议、权限系统或生产服务。
'''
    interviewer = f'''# 面试官：{row['title']}

本文件含提示，候选人计时阶段不要看。只提供 README、PROMPT、starter、fixtures、tests 和 _support。
主持时不替候选人改代码，也不提前输出完整答案。

## 主持流程

1. 说明 45 分钟建议上限，请候选人先复述「{core['label']}」的输入输出。
2. 一次问一个问题，等待回答。开场约定允许的文档/语法帮助并记录。
3. 所有澄清以 PROMPT 为准；未规定的行为明确“不在本题评分范围”，不要临时发明隐藏需求。
4. 约 25 分钟询问核心剩余问题；39 分钟提醒测试、保存和总结。主持者自行计时，聊天不能保证无消息时主动提醒。
5. 45 分钟记录当前代码和成绩；之后修复记复盘，不追溯到计时成绩。

## 分级提示（每次只给一级）

- H1：请挑一个失败 case，手算输入如何得到期望结果。
- H2：请先列出需要拒绝的输入和不可变输入要求，再考虑正常路径。
- H3 核心：{NOTES[row['core']]}
- H3 加分：{NOTES[row['bonus']]}

记录 H1/H2/H3 次数。核心完成前不催促加分。独立轮不提供 H3 或完整解法。

## 追问

- 你如何证明 `{core['function']}` 不会在无效输入时静默返回错误结果？
- 核心时间与空间复杂度是什么？输入规模增大后如何改进？
- 为什么这次只实现「{core['label']}」仍不足以声称完整完成原课「{row['title']}」工程？
- `{bonus['function']}` 的一个容易遗漏的边界是什么？请自己补一个测试。

## 原创训练评分

核心 60 分：核心通过数/6 ×60，向下取整。边界与自写测试 15 分、代码与错误处理 15 分、沟通与时间管理 10 分。
人工维度必须写具体观察证据；没有观察标“未观察”，不自动给满分。
加分通过数独立记录，不补偿核心缺失。分数不是公司招聘标准或录用概率。
若候选人之前做过相同 kernel，标成重复练习，避免误记为未见题表现。
'''
    review = f'''# {row['phase_id']}/{row['lesson'][:2]} 本轮复盘

- 主题：{row['title']}
- 核心 / 加分：{row['core']} / {row['bonus']}
- 模式：学习 / 独立未见题 / 重复练习 / 面试官陪练
- 日期 / 第几轮 / 开始和截止时间：
- 看过的材料、使用的帮助、H1/H2/H3 次数：
- 首个成功路径：第 ___ 分钟
- 45 分钟核心：___ / 6；加分：___ / 2
- 代码与测试输出保存位置：
- 尚未完成的行为：

| 失败场景 | 原理解 | 根因 | 修复与重测 |
| --- | --- | --- | --- |
| | | | |
| | | | |
| | | | |

- 核心 60 分 / 边界测试 15 分 / 代码 15 分 / 沟通 10 分（附观察证据）：
- 自己新增的反例和它验证的规则：
- 核心复杂度及原课完整工程仍需什么：
- 复盘后核心 / 加分（与计时成绩分开）：
- 关闭答案后能否重新解释并实现：
- 下一轮只改进一个习惯：
'''
    fixtures = {"core":{"function":core["function"],"cases":row["core_cases"]},
                "bonus":{"function":bonus["function"],"cases":row["bonus_cases"]}}
    scope = {k:v for k,v in row.items() if k not in ("core_cases","bonus_cases")}
    return {"README.md":readme, "PROMPT.md":prompt, "starter/main.py":implementation(row,True),
            "solution/main.py":implementation(row), "solution/EXPLANATION.md":explanation,
            "fixtures.json":json.dumps(fixtures,ensure_ascii=False,indent=2)+"\n",
            "SCOPE.json":json.dumps(scope,ensure_ascii=False,indent=2)+"\n",
            "tests/test_exam.py":TESTS, "_support.py":SUPPORT,
            "run_tests.py":SHARED_RUNNER.read_text(), "INTERVIEWER.md":interviewer,
            "REVIEW_TEMPLATE.md":review}


def phase_index(rows):
    p = rows[0]
    items="\n".join(f"| {r['lesson'][:2]} | [{r['title']}]({r['lesson']}/coderpad/README.md) | {load()[r['core']]['label']} | {load()[r['bonus']]['label']} |" for r in rows)
    return f'''# {p['phase']}：CoderPad 练习

本章 {len(rows)} 个项目已按第 13 章试点形式提供练习：45 分钟建议上限、Python 3.10+ 标准库、离线执行。
核心 6 cases、加分 2 cases。题目是原课程中的一个编码切面，不要求运行完整训练、云服务或 GPU。
相同基础 kernel 会在相关课程复用；请在复盘中区分“未见题”与“重复练习”。
运行方法：进入任一项目的 `coderpad/`，阅读 README/PROMPT，再执行：

```bash
python3 run_tests.py --list
python3 run_tests.py --core
```

初始失败是 TODO 的正常起点；计时结束后才打开 solution 或使用 `--solution`。
面试官材料、评分与复盘模板均在每套目录；计时器自行设置。

| 课号 | 主题与题目入口 | 核心 | 加分 |
| --- | --- | --- | --- |
{items}

全课程入口：[CODERPAD_INDEX.md](../../CODERPAD_INDEX.md)。维护方式：[生成器说明](../../scripts/coderpad_curriculum/README.md)。
'''


def desired_files(output):
    rows=inventory();files={}
    for row in rows:
        files.update({output/row["path"]/"coderpad"/name:text for name,text in render_pack(row).items()})
    for phase in sorted({r["phase"] for r in rows}):
        files[output/"phases"/phase/"CODERPAD.md"]=phase_index([r for r in rows if r["phase"]==phase])
    phase_rows=[]
    for phase in sorted((REPO/"phases").glob("[0-9][0-9]-*")):
        lessons=[p for p in phase.glob("[0-9][0-9]-*") if p.is_dir()]
        if not lessons:continue
        phase_rows.append(f"| {phase.name} | {len(lessons)} | [打开](phases/{phase.name}/CODERPAD.md) |")
    files[output/"CODERPAD_INDEX.md"]='''# 全课程 CoderPad 面试练习

覆盖编号章节 00–20 的全部 543 个项目：第 13 章已有 31 套，本轮新增 512 套。
个人学习笔记、认证课程和 outputs 内嵌样例不计为新的章节项目。
组织方式与第 13 章试点一致，每个项目下的 coderpad/ 与 code/docs/assets 同级。

新增题包使用 130 个可复用的基础编码 kernel，逐课显式选择核心/加分组合。
新增部分有 421 种核心/加分组合。所以 543 是按课组织的题包数，不是 543 道互不重复的算法题。
相邻架构课可能复用相同 kernel；SCOPE.json 和下表标明范围，复盘时区分未见题与重复练习。
每套只覆盖适合现场写代码的切面，不能代替原课程完整项目或真实部署验收。

## 开始方法

打开下表某章，选择项目的 coderpad/README.md。Python 3.10+，标准库，无 API key、下载或 GPU。
在选定 coderpad/ 目录运行：

```bash
python3 run_tests.py --list
python3 run_tests.py --core
python3 run_tests.py --bonus
```

45 分钟为建议上限，基础题可以提前完成，难度与时间尚未经过学员校准。
初始失败是正常 TODO。计时后再用 `python3 run_tests.py --solution`，不会覆盖 starter。
本地没有真实隐藏测试或强制倒计时；使用自己的计时器。
每套包含面试官指南、参考答案、中文解释、评分与复盘表、参考验证和 starter 基线。
希望助手主持时说：“按这个项目 coderpad/INTERVIEWER.md 开始，一次只问一个问题。”

## 章节入口

| 章节 | 项目数 | 练习索引 |
| --- | --- | --- |
'''+"\n".join(phase_rows)+'''

第 20 章的 09–12 原有 docs/en.md 缺失，题包依据现存 code 设计，已在对应 README/SCOPE 标注。
参考验证总表见 [CODERPAD_VALIDATION.json](CODERPAD_VALIDATION.json)。
维护源文件见 [scripts/coderpad_curriculum/README.md](scripts/coderpad_curriculum/README.md)。
'''
    catalog=[{k:v for k,v in r.items() if k not in ("core_cases","bonus_cases")} for r in rows]
    files[output/"scripts/coderpad_curriculum/CATALOG.json"]=json.dumps(catalog,ensure_ascii=False,indent=2)+"\n"
    return files


def build(output=REPO,check=False):
    desired=desired_files(output)
    diff=[p for p,c in desired.items() if p.exists() and p.read_text(encoding="utf-8")!=c]
    missing=[p for p in desired if not p.exists()]
    if diff or check and missing:
        for p in (diff+(missing if check else []))[:30]:print("DIFF:",p,file=sys.stderr)
        print(f"Refusing overwrite: {len(diff)} differences, {len(missing)} missing",file=sys.stderr)
        return False
    if not check:
        for p in missing:p.parent.mkdir(parents=True,exist_ok=True);p.write_text(desired[p],encoding="utf-8")
    print(f"{'Checked' if check else 'Prepared'} 512 packs / {len(desired)} authored files")
    return True


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check",action="store_true")
    parser.add_argument("--output",type=Path,default=REPO)
    args=parser.parse_args()
    raise SystemExit(0 if build(args.output.resolve(),args.check) else 1)
