"""Build original lesson-specific interview packs without overwriting learner work.

Source: specs/01.py through specs/31.py and runner_template.py.
Generated packs are standalone; no third-party dependency or network.
Canonical command: python3 build.py --check
"""
import argparse
import ast
from pathlib import Path
import runpy
import sys
import textwrap

HERE = Path(__file__).resolve().parent
PHASE = HERE.parents[1] / "phases" / "13-tools-and-protocols"


def load_specs():
    lessons = sorted(p for p in PHASE.glob("[0-9][0-9]-*") if p.is_dir())
    result = []
    for lesson in lessons:
        path = HERE / "specs" / f"{lesson.name[:2]}.py"
        spec = runpy.run_path(str(path))["SPEC"]
        spec["code"] = ast.unparse(ast.parse(textwrap.dedent(spec["code"]))) + "\n"
        spec["tests"] = ast.unparse(ast.parse(textwrap.dedent(spec["tests"]))) + "\n"
        result.append((lesson, spec))
    if len(result) != 31:
        raise ValueError(f"Expected 31 lessons, found {len(result)}")
    return result


def make_starter(code, stubs):
    tree = ast.parse(code)
    edits, found = [], set()
    def visit(nodes, prefix=""):
        for node in nodes:
            if isinstance(node, ast.ClassDef):
                visit(node.body, prefix + node.name + ".")
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                name = prefix + node.name
                if name in stubs:
                    found.add(name)
                    # Expand one-line definitions so their implementation is fully removed.
                    body_line = node.body[0].lineno
                    if body_line == node.lineno:
                        signature = ast.unparse(node).split("\n", 1)[0]
                        replacement = " " * node.col_offset + signature + "\n"
                        start = node.lineno - 1
                    else:
                        replacement = ""
                        start = body_line - 1
                    number = stubs.index(name) + 1
                    replacement += " " * (node.col_offset + 4) + f'raise NotImplementedError("TODO {number}: {name}; see PROMPT.md")\n'
                    edits.append((start, node.end_lineno, replacement))
    visit(tree.body)
    if found != set(stubs):
        raise ValueError(f"Unknown TODO functions: {set(stubs) - found}")
    lines = code.splitlines(keepends=True)
    for start, end, replacement in sorted(edits, reverse=True):
        lines[start:end] = [replacement]
    starter = "".join(lines)
    ast.parse(starter)
    return starter


SUPPORT = '''"""Select a local implementation; importing it never fills in learner TODOs."""
import importlib.util
import os
from pathlib import Path
import sys
root = Path(__file__).resolve().parent
implementation = os.environ.get("CODERPAD_IMPLEMENTATION", "starter")
if implementation not in ("starter", "solution"):
    raise ValueError("CODERPAD_IMPLEMENTATION must be starter or solution")
spec = importlib.util.spec_from_file_location("coderpad_target", root / implementation / "main.py")
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)
'''


def files_for(lesson, s):
    number = lesson.name[:2]
    source = f"../docs/en.md"
    header = f'''"""Original Phase 13 / Lesson {number} CoderPad practice.

Lesson source: {lesson.name}/docs/en.md (local course snapshot).
The precise exercise contract is defined in coderpad/PROMPT.md.
Python 3.10+, stdlib only, no network or API keys.
"""
'''
    prompt = f'''# {s['title']}

Original interview simulation · 45 minutes · Python 3.10+ · standard library only.
This is independent practice, not an Edison Scientific question or scoring policy.

## Scenario

{s['scenario']}

## Candidate work

Edit only `starter/main.py`. Keep public signatures and supplied helpers intact.
`tests/test_exam.py` and fixtures are provided. You may add your own tests in a new `tests/test_candidate.py`.
Explain your plan briefly, then implement the core before attempting the bonus.

## Core contract

{s['contract']}

## Bonus contract

{s['bonus']}

## Commands

```bash
python3 run_tests.py --list
python3 run_tests.py --core
python3 run_tests.py --core -k keyword_from_test_name
python3 run_tests.py --bonus
python3 run_tests.py
```

Read the complete contract before starting. All fixture shapes not declared invalid are supplied valid.
There are no undisclosed external-service requirements. At minute 45, save and record the current result.
Use your own timer; the test runner does not enforce a deadline. Locally stored tests and solutions are readable,
so strict mode relies on your self-discipline or a separate interviewer. Do not read `solution/` or `INTERVIEWER.md` during the attempt.
'''
    todo_rows = "\n".join(f"| {i} | `{name}` |" for i, name in enumerate(s["stubs"], 1))
    readme = f'''# {number}：{s['zh_title']}

**原创 CoderPad 风格模拟面试，45 分钟，{s['level']}。**

{s['brief']}

题目基于[本课课程材料]({source})改编；准确行为以 [英文面试题 PROMPT.md](PROMPT.md) 为准。
这是面试能力训练，不是 Edison 原题，也没有使用真实公司的内部评分。
每套是独立的标准库 Python 项目；不需要服务、API key、付费调用或新依赖。
建议时间与难度是试点设计值，尚未经真实学员计时校准。

## 第一次开始

终端进入本文件所在的 `coderpad/`，然后运行：

```bash
python3 --version
python3 run_tests.py --list
python3 run_tests.py --core
```

要求 Python 3.10+。初始核心测试失败是正常的 TODO 起点；当前生成版本的实跑记录见
[starter_baseline.txt](starter_baseline.txt) 和 [verification.txt](verification.txt)。
`--list` 只收集测试，不执行 TODO。无需先运行原课程 `code/main.py`。

## 你要修改的地方

只在 [starter/main.py](starter/main.py) 完成功能。可以新增自己的测试；不要改变原有测试来获得通过。
给定的构造器、异常类、辅助函数和 fake 依赖可直接使用。TODO 编号按源文件顺序排列，
核心/加分归属以 PROMPT 合同为准，不要求按编号顺序做完。

| TODO | 函数或方法 |
| --- | --- |
{todo_rows}

## 面试节奏

| 时间 | 行动 |
| --- | --- |
| 0–5 分钟 | 阅读 PROMPT、starter、测试，复述输入输出并提出澄清 |
| 5–10 分钟 | 说出实现顺序，完成最小成功路径 |
| 10–30 分钟 | 完成核心行为、边界和失败后的状态保护 |
| 30–39 分钟 | 修复核心，再尝试加分项 |
| 39–45 分钟 | 核心与全量测试、保存、记录未完成项 |

```bash
# 核心 / 加分分开计分；测试失败时退出码为 1
python3 run_tests.py --core
python3 run_tests.py --bonus
python3 run_tests.py

# 过滤名称；将 keyword 换成 --list 显示的测试名片段
python3 run_tests.py --core -k keyword

# 计时结束后才运行参考答案；不会修改 starter
python3 run_tests.py --solution
```

评分单位是 unittest test case；同一方法里的多个 subTest 输入不分别加分。
一个 subTest 失败就算该 case 失败。加分分开记录，不补偿核心缺失。
直接运行 `python3 -m unittest discover -s tests -v` 默认测试 starter；统一入口仍推荐 run_tests.py。

## 两种练习方式

- **独立限时**：使用自己的计时器，只看候选人材料；关闭答案、原课完整实现和 AI 代写。计时后再复盘。
- **面试官陪练**：告诉助手“按这套 coderpad/INTERVIEWER.md 开始面试”，或请朋友主持。面试官分阶段澄清与提示，你独立写代码。

这些规则是训练约定；本地文件无法真正隐藏测试或强制锁定倒计时。
第一轮可先看课程学习，另记为学习轮；后续使用未做过的题练独立表现。

计时结束复制 [REVIEW_TEMPLATE.md](REVIEW_TEMPLATE.md) 记录成绩，再阅读
[参考解释](solution/EXPLANATION.md)。重做前保留自己的 starter 副本；不要使用上层 `git reset` 或 `git clean`。
'''
    questions = "\n".join(f"- {q}" for q in s["followups"])
    interviewer = f'''# 面试官材料：{number} {s['zh_title']}

候选人计时阶段不要阅读本文件。本文件用于本地原创模拟面试，不代表公司招聘标准。
主持开始时只给候选人 PROMPT、starter 和 tests。未经用户要求，不修改候选人代码，也不提前给参考答案。

## 开场与推进

1. 说明本题 45 分钟，核心优先；请候选人先复述输入、输出和失败行为。
2. 一次只问一个澄清或推理问题，等待回答。不要一次倾倒整套提示。
3. 5 分钟左右确认实现顺序；约 25 分钟问一次剩余风险；39 分钟提醒运行测试并保存。
4. 主持人需要自己看时间；聊天助手无法在没有新消息时保证主动发出提醒。实际耗时由候选人计时器记录。
5. 45 分钟保存当前代码和成绩。之后的修改记为复盘结果，禁止追溯算入计时成绩。

## 澄清答案的范围

以 PROMPT 的精确合同回答。无额外网络、部署或供应商 SDK 要求。
若合同没规定，明确说“本题不评分这个行为”，不要临时追加隐藏需求。
可解释语法或运行方式；是否允许 AI 帮助应在开场约定并记入复盘。

## 分级提示（每次只给一级并记录次数）

- H1：让候选人找一个最小失败测试，逐项对照合同中的输入、输出、状态变化。
- H2：问“哪些拒绝条件必须先于外部调用或状态写入？如何用 fake/前后状态证明？”
- H3：针对本题提示：{s['explanation']}

H3 包含实现方向，严格独立轮应避免使用。完整代码仅在宣布计时结束或候选人明确退出后提供。

## 追问

{questions}

## 原创训练评分（100 分）

| 维度 | 分数 | 观察依据 |
| --- | --- | --- |
| 核心功能 | 60 | 核心 case 通过比例 × 60，向下取整；原始通过数同时保留 |
| 边界与自己写的测试 | 15 | 能解释至少两个重要边界，并补一个有意义的反例测试 |
| 代码与错误处理 | 15 | 状态写入顺序、清晰命名、异常分类、避免无必要复杂性 |
| 沟通与时间管理 | 10 | 先澄清、讲实现顺序、及时测试、结尾说明限制 |

人工维度应写出证据与给分原因；没有观察就标“未观察”，不要自动给满分。
加分仅记录通过数与讨论表现，不抵消核心缺失；该分数不能推算任何公司的录用概率。
参考答案与预期初始结果分别见 solution/ 与 starter_baseline.txt。
'''
    review = f'''# {number} {s['zh_title']}：本轮复盘

- 日期 / 第几轮：
- 模式：学习轮 / 独立 45 分钟 / 面试官陪练
- 开始 / 截止时间：
- 计时阶段看过哪些材料或得到哪些帮助：
- H1 / H2 / H3 次数：
- 首个成功路径：第 ___ 分钟
- 45 分钟时核心：___ / ___ cases
- 45 分钟时加分：___ / ___ cases
- 已保存代码与测试输出的位置：
- 未完成功能与已知风险：

## 三个卡点

| 失败场景 | 原因（理解/语法/状态/测试/时间） | 如何定位 | 修复与重测 |
| --- | --- | --- | --- |
| | | | |
| | | | |
| | | | |

## 口头追问

{questions}

- 哪个测试证明拒绝或失败后没有错误的状态改变？
- 核心 60 分：___；边界测试 15 分：___；代码 15 分：___；沟通 10 分：___
- 人工评分证据 / 未观察项：

## 计时结束后的复盘成绩

- 修复后核心 / 加分：
- 关掉答案后能否重新解释并实现：
- 下一轮只改进一个习惯：
'''
    explanation = f'''# 参考解释：{s['zh_title']}

仅在计时结束后阅读。参考实现是满足本题简化合同的一种实现，不是生产 SDK。

{s['explanation']}

## 复盘顺序

1. 将自己失败的 case 映射到 PROMPT 的具体规则，先判断是理解还是实现遗漏。
2. 查看 [main.py](main.py) 中对应函数，解释校验、外部调用和状态变化的顺序。
3. 关闭答案，自己修复 starter；补一个边界测试，再跑核心和全量测试。
4. 回答下面追问，明确本地 fake 测试的证据边界。

{questions}

```bash
python3 run_tests.py --solution
```

这条命令在 `coderpad/` 目录运行，选择独立参考实现，不覆盖学员代码。
测试覆盖只针对 PROMPT 合同；协议、身份、网络、跨 host 或真实部署均需独立集成证据。
'''
    files = {
        "README.md": readme, "PROMPT.md": prompt,
        "starter/main.py": header + make_starter(s["code"], s["stubs"]),
        "solution/main.py": header + s["code"],
        "solution/EXPLANATION.md": explanation,
        "tests/test_exam.py": f'"""Behavior tests for {lesson.name}; default target is starter."""\nimport unittest\nfrom _support import m\n\n' + s["tests"],
        "run_tests.py": (HERE / "runner_template.py").read_text(),
        "_support.py": SUPPORT, "INTERVIEWER.md": interviewer,
        "REVIEW_TEMPLATE.md": review,
    }
    return files


def render_index(specs):
    rows = "\n".join(f"| {lesson.name[:2]} | [{s['zh_title']}]({lesson.name}/coderpad/README.md) | {s['level']} |" for lesson, s in specs)
    return f'''# Phase 13：CoderPad 面试试点

31 个小项目，每个项目的 `coderpad/` 与 `assets/`、`code/`、`docs/`、`notebook/` 同级。
每套 45 分钟，Python 3.10+ 标准库，离线 fake；不需要 API key 或安装包。
原创练习仅参考本地 Edison mock exams 的组织形式，不声称是真题或官方招聘标准。
课程相关协议格式使用本地课程快照和题目明确列出的简化合同，未对外部最新版本作认证。

## 现在开始

```bash
cd phases/13-tools-and-protocols/01-the-tool-interface/coderpad
python3 run_tests.py --list
python3 run_tests.py --core
```

从仓库根目录执行上面的 cd；其他位置可直接在对应 coderpad 目录打开终端。
先读该套 README 和英文 PROMPT，再开自己的 45 分钟计时器，只修改 starter/main.py。
初始失败是 TODO 的正常起点。参考答案在 solution/，计时后再打开。
所有测试均存本地，没有真正隐藏的评分服务器或强制倒计时。

## 建议练习顺序

- **第一轮打基础**：01 → 02 → 04 → 05 → 07。03 的流式与并发可在这之后做。
- **MCP 边界**：06 → 07 → 08 → 09 → 10 → 11 → 12 → 13 → 14 → 15 → 16 → 18 → 17。
- **工程组合**：19 → 20 → 21，再进入 23 综合题。
- **Skills 专项**：22 → 24 → 25 → 26 → 27。
- **进阶专项**：28 → 29 → 30 → 31；23 可最后重做综合复盘。

时间与难度尚未经真实候选人校准。核心 case 数不是难度分数，各套通过率不能直接横向比较。
建议每次只做一套，保留计时成绩与复盘成绩；需要陪练时可说：
“按第 02 套的 coderpad/INTERVIEWER.md 开始模拟面试，一次只问一个问题。”

## 全部题目

| 课号 | 面试题 | 建议难度 |
| --- | --- | --- |
{rows}

## 目录内材料

- README.md / PROMPT.md：中文上手与英文输入输出合同。
- starter/main.py：学员 TODO；tests/：可见行为测试，可以额外添加自己的测试文件。
- run_tests.py：收集、过滤、核心/加分和独立参考实现选择。
- INTERVIEWER.md：澄清、分级提示、追问和原创人工评分标准。
- REVIEW_TEMPLATE.md：计时结果、卡点、提示次数与复盘结果分开记录。
- solution/：参考代码与中文解释；verification.txt / starter_baseline.txt：实跑证据。

包内 `python3 run_tests.py --solution` 不修改 starter。重复练习先另存自己的答案。
维护源文件和安全生成方式见 [生成器说明](../../scripts/coderpad_phase13/README.md)。
'''


def build(output, check=False):
    specs = load_specs()
    desired = {output / "CODERPAD.md": render_index(specs)}
    for lesson, spec in specs:
        for name, content in files_for(lesson, spec).items():
            desired[output / lesson.name / "coderpad" / name] = content
    differences = [p for p, c in desired.items() if p.exists() and p.read_text(encoding="utf-8") != c]
    missing = [p for p in desired if not p.exists()]
    if differences or check and missing:
        for p in differences + (missing if check else []):
            print(f"DIFF: {p}", file=sys.stderr)
        return False
    if not check:
        for p in missing:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(desired[p], encoding="utf-8")
    print(f"{'Checked' if check else 'Prepared'} {len(specs)} packs / {len(desired)} authored files.")
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output", type=Path, default=PHASE)
    args = parser.parse_args()
    raise SystemExit(0 if build(args.output.resolve(), args.check) else 1)
