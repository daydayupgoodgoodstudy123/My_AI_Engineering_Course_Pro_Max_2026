# 测验 · 在真实代码仓库中使用工作台（The Workbench on a Real Repo）

> **阶段 14 · Agent 工程 · 第 41 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 七个 workbench surface | 第 31 节定义的 Instructions、State、Scope、Feedback、Verification、Review、Handoff；本节把 32–40 节逐个造出来的 surface 在同一个样本应用上串起来 |
| 2 | A/B 对比的控制变量 | 同一任务、同一样本应用、同一个"agent"（脚本），只改变 harness；mission 原话："The comparison holds the model constant by construction" |
| 3 | 样本应用与"禁区诱饵" | `app.py` 的 `/signup` 尚无校验、`test_app.py` 只有一个 happy-path 测试；`README.md` 和 `scripts/release.sh` 是故意放的诱饵，用来检验 agent 会不会越界 |
| 4 | 两条管线 | prompt-only：读 README → 读 app.py → 改文件 → 宣布完成（4 步）；workbench：init(35) → scope(36) → state(34) → 只改允许文件 → feedback runner(37) → gate(38) → reviewer(39) → handoff(40)（8 步） |
| 5 | 五个度量 | `tests_actually_run`、`acceptance_met`、`files_outside_scope`、`handoff_quality`、`reviewer_total`；前三个是可机器判定的事实，后两个偏质量判断 |
| 6 | "测试跑了" ≠ "验收达成" | 讲义：证明目标的那个测试必须就是实际运行的那个测试（"The test that proves the goal must be the test that ran"） |
| 7 | 脚本化 = 可复现，但也是简化 | 本节代码的两条管线不调用 LLM，五个结果都是**硬编码常量**；它演示的是"度量框架和报告格式"，不是真实测出来的收益 |
| 8 | 行业证据（讲义转述） | Terminal Bench 2.0 同一模型只改 harness 从 30 名外升到第 5；Vercel 删掉 80% 工具后成功率 80%→100%；Harvey 只靠 harness 准确率翻倍以上；88% 企业 agent 项目没进生产，根因在运行时 |
| 9 | False negative 要诚实列出 | 单步事实问题、单行 lint、formatter 运行等任务 prompt-only 更快；不列出来，workbench 会被当成"过度设计" |
| 10 | 可移植 benchmark 的规则 | 必须两条管线；百分比要带分母（`n / m`）；样本应用不能是模型训练过的；无 acceptance command 拒绝发布；workbench 中位耗时 >3 倍要报告；不能离线运行就不接 CI |

### 核心技能（能动手做到）

- [ ] 说出七个 surface 各自防住哪一类失败，并能把 workbench 管线的 8 个步骤对应到第 34–40 节
- [ ] 读懂 `main.py`：说清 `TaskOutcome` 的字段、`files_outside_scope` 怎么算、报告和 JSON 写到了哪里
- [ ] 指出本节代码"度量全是硬编码"的问题，并改写成真正执行 acceptance command、按实际 diff 计算越界文件的度量函数
- [ ] 亲手完成本节任务：给 `signup` 加长度校验、返回 422 + 类型化错误信封，并写出证明新行为的测试
- [ ] 设计一份能放进 CI 的 before/after benchmark，结果以 `n / m` 报告，并包含 false negative 清单
- [ ] 面对"模型已经够强、这个 sprint 先关掉 gate"的说法，能用数据和 false negative 两面论证

---

## 二、基础自测（选择题）

**Q1.** 本节两条管线都是脚本化的、不调用任何 LLM。这样设计的主要理由是：

- A. LLM 调用太贵，课程预算不够
- B. workbench 本身不需要模型也能完成任务
- C. 让测量可复现，并且从构造上保证"模型不变、只变 harness"
- D. LLM 无法直接编辑文件，只能输出文本

**Q2.** 运行 `python3 code/main.py`，prompt-only 管线打印的 `files_outside_scope` 是：

- A. `['README.md', 'sample_app/scripts/release.sh']`
- B. `['sample_app/app.py', 'README.md', 'sample_app/scripts/release.sh']`
- C. `['sample_app/scripts/release.sh']`
- D. `[]`

**Q3.** prompt-only 管线"宣布完成"但 `tests_actually_run = False`。在七个 surface 中，最直接拦住这类"未经验证就宣布完成"的是：

- A. Instructions（启动规则写了"完成的定义"就够了）
- B. State（记录当前任务）
- C. Handoff（把剩余工作留给下个会话）
- D. Feedback + Verification（acceptance command 经 feedback runner 真实执行并捕获输出，再由 gate 复核）

**Q4.** `reviewer_total` 沿用第 39 节的评审器：5 个维度各 0–2 分，满分 10；任一维度为 0 或总分 < 5 判 `hard_fail`，总分 ≥ 7 判 `pass`，其余 `soft_fail`。prompt-only 的 `reviewer_total = 3` 对应的结论是：

- A. `pass`
- B. `hard_fail`
- C. `soft_fail`
- D. 信息不足，无法判定

**Q5.** 一份 benchmark 报告写道："引入 workbench 后成功率提升了 40%。"按本节 `skill-workbench-benchmark` 的规则，它最主要的问题是：

- A. 百分比没有分母，应报告成 `n / m`（例如 `9/10 vs 5/10`）
- B. 应该改用中位数而不是平均数
- C. benchmark 不允许报告成功率
- D. 只应该报告 `reviewer_total`

**Q6.** 讲义提醒要诚实列出 false negative（prompt-only 反而更快的任务）。下列哪一个**最可能**是 false negative？

- A. 跨 5 个文件重构认证模块
- B. 需要分三个会话完成的数据库迁移
- C. 给 API 增加输入校验并补一个证明新行为的测试
- D. 对一个文件跑一次 formatter 修复格式

**Q7.** 关于 `main.py` 中定义的 `FORBIDDEN = {"sample_app/scripts/release.sh"}`，说法正确的是：

- A. 触碰禁区文件时它会让 prompt-only 管线直接失败
- B. `files_outside_scope` 就是用它计算出来的
- C. 它定义了但从未被使用；越界判定只和 `ALLOWED` 比较，"禁区"与"一般越界"没有区分
- D. `write_report` 用它在报告里单独列出禁区文件

**Q8.** benchmark skill 的拒绝规则中，如果 workbench 管线在中位任务上耗时超过 prompt-only 的 3 倍，应该：

- A. 换一个更强的模型再测
- B. 把这一发现报告出来：需要简化的是 workbench，而不是模型
- C. 删除这个 benchmark，避免引起误解
- D. 直接放弃 workbench，回到 prompt-only

---

## 三、动手 / 代码题

**Q9.** 阅读 `run_workbench`：

```python
def run_workbench() -> TaskOutcome:
    """Reads scope, edits inside scope, runs acceptance through feedback, gates, reviews, hands off."""
    touched = ["sample_app/app.py", "sample_app/test_app.py"]
    return TaskOutcome(
        pipeline="workbench-guided",
        tests_actually_run=True,
        acceptance_met=True,
        files_outside_scope=[p for p in touched if p not in ALLOWED],
        handoff_quality="full packet",
        reviewer_total=9,
    )
```

运行 `main.py` 后，`sample_app/app.py` 里仍然没有任何密码校验。

1. 这段代码和本节讲义的核心论点之间有什么"反讽"？
2. 请写一个 `measure(touched, cwd)`，让 `tests_actually_run`、`acceptance_met`、`files_outside_scope` 由**实际执行**决定，而不是写死。
3. 为什么 `tests_actually_run` 更严格的口径应该看"agent 自己的 feedback 日志"，而不是 harness 事后补跑一遍？

**Q10.** 观察 prompt-only 管线：

```python
ALLOWED = {"sample_app/app.py", "sample_app/test_app.py"}
FORBIDDEN = {"sample_app/scripts/release.sh"}

def run_prompt_only() -> TaskOutcome:
    touched = ["sample_app/app.py", "README.md", "sample_app/scripts/release.sh"]
```

而 `write_sample()` 写出的诱饵 README 路径是 `sample_app/README.md`。

1. 指出这里的两处不一致。
2. 讲义说 README 和 `release.sh` 都是"禁区诱饵"，但 `FORBIDDEN` 只有一个文件。修正后 prompt-only 的越界列表应是什么？
3. "越界"和"触碰禁区"应如何区别对待？给出判定规则。

**Q11.** 动手完成本节任务本身："拒绝短于 8 个字符的密码，返回 422 并带类型化错误信封；添加一个证明新行为的测试。"请写出修改后的 `signup` 和至少两个新测试，并说明你会把哪个测试名写进 scope contract 的 acceptance 条件里、为什么。

**Q12.** 在 `code/` 目录下（先运行过 `main.py`，生成了 `sample_app/`）分别执行：

```bash
python3 -m pytest -q sample_app/test_app.py     # 结果 A
pytest -q sample_app/test_app.py                # 结果 B
```

实际结果 A 是 `1 passed`，结果 B 是收集阶段报错 `ModuleNotFoundError: No module named 'sample_app'`。

1. 解释为什么两个命令结果不同。
2. 这对 workbench 中"acceptance command"的写法有什么启示？

---

## 四、面试高频题

**Q13.**（基础必考）什么是 agent harness / workbench？它由哪几个 surface 组成？为什么说"同一个模型、换个 harness，排名能差 25 名"？

**Q14.**（原理深挖）为什么 agent 的"tests passed"声明往往不可信？`tests_actually_run` 与 `acceptance_met` 有什么区别？工程上怎样让这两个结论变成可验证的事实？

**Q15.**（工程实践）请设计一个能放进 CI、长期运行的 "workbench vs prompt-only" benchmark：目录结构、度量口径、回归判定、哪些情况必须拒绝发布？

**Q16.**（场景设计）团队负责人说："新模型很强，这个 sprint 先把 verification gate 关掉，赶进度。" 你会如何回应？

**Q17.**（追问型）如果把本节脚本化的"agent"换成真实 LLM 调用，五个度量里哪些会变得有噪声？你会怎么设计实验来得到可信结论？

---

## 五、参考答案与解析

### Q1 — 答案：C

讲义 Build It："Both pipelines are scripted (no LLM in the loop) so the measurement is reproducible." mission 的 Out of scope 也写明："The comparison holds the model constant by construction." 对比实验最重要的是控制变量：只改 harness，其它都不变。A 不是讲义给出的理由；B 错，workbench 是包在模型外面的环境，不能替代模型；D 错，真实 agent 通过工具调用编辑文件，这与是否脚本化无关。

需要补充的是：脚本化的代价是**结果被写死**（见 Q9），本节证明的是"怎么量"，而不是"量出来多少"。

### Q2 — 答案：A

`touched = ["sample_app/app.py", "README.md", "sample_app/scripts/release.sh"]`，列表推导式只保留不在 `ALLOWED` 中的路径：`app.py` 在允许集合里被过滤掉，剩下 `['README.md', 'sample_app/scripts/release.sh']`。实际运行输出与此一致，报告里显示为计数 `2`。B 忘了过滤；C 误以为只算 `FORBIDDEN`；D 是 workbench 管线的结果。

### Q3 — 答案：D

第 31 节的表格：Feedback 缺失时 "Agent declares success on a 400"，Verification 缺失时 "'Looks good' reaches main"。workbench 管线第 5、6 步正是"通过 feedback runner 运行 acceptance command"和"运行 verification gate"。A 只能"告诉"agent 完成的标准，无法"证明"它做到了；B 记录进度，不检查结果；C 发生在任务结束之后，拦不住虚假的完成声明。

### Q4 — 答案：B

3 < 5，直接 `hard_fail`（第 39 节 `review()`：`if has_zero or total < 5: verdict = "hard_fail"`）。workbench 的 9 ≥ 7 判 `pass`。C 是 5–6 分区间；D 错，规则是完全确定的。注意本节报告里只写了 `reviewer_total (/10)`，没有写 verdict，读者需要知道第 39 节的阈值才能解读。

### Q5 — 答案：A

skill 的 Hard rejects："Outcomes phrased as percentages without a denominator. Always report `n / m`." "提升 40%" 既可能是 5/10 → 7/10（绝对值 +20 个百分点、相对 +40%），也可能是 1/1 → 1.4……完全无法判断样本量和是绝对还是相对提升。B、C、D 都不是 skill 的规则。

### Q6 — 答案：D

讲义列出的 false negative："Single-step factual tasks, one-line lints, formatter runs, anything the model has memorized verbatim"。跑 formatter 是确定性的一步操作，init、读 scope、gate、review、handoff 全套流程纯属开销。A、B、C 都是多步、有越界风险、需要测试证明的任务，恰恰是 workbench 的用武之地。

### Q7 — 答案：C

`FORBIDDEN` 在整个文件中只出现在定义处。`files_outside_scope` 的计算是 `[p for p in touched if p not in ALLOWED]`，只看允许清单。这意味着"改了 README"和"改了发布脚本"在度量里分量相同，都只是计数 +1。生产中触碰禁区应该是一票否决（见 Q10）。A、B、D 描述的行为代码里都不存在。

### Q8 — 答案：B

skill 的 Refusal rules："If the workbench pipeline takes more than 3x the prompt-only pipeline on the median task, surface that finding; the workbench needs simplification, not the model." 这与讲义中 Vercel "删掉 80% 工具反而更好"的案例同一逻辑：harness 也会过度膨胀。A 把问题归到了错误的对象上；C 是隐藏不利结果，违背"诚实列出"的精神；D 过度反应。

### Q9 — 参考答案

1. **反讽**：讲义的核心论点是"大多数 'tests passed' 声明不可验证"，workbench 的价值就在于把声明变成证据。但本节代码中 workbench 管线的 `tests_actually_run=True`、`acceptance_met=True` 本身就是**无法验证的声明**——没有运行任何命令，`sample_app/app.py` 运行前后都没有校验逻辑（`write_sample()` 每次都写回原始版本）。报告里那一行 `acceptance_met | False | True` 在字面意义上是假的。作为教学脚本可以接受，但读者必须知道它展示的是**报告格式**，而不是测量结果。

2. 参考实现（已在临时目录实际运行验证：在加好校验与测试的样本应用上返回 `tests_actually_run=True, acceptance_met=True, files_outside_scope=[]`，退出码 0，`3 passed`）：

```python
import subprocess, sys
from pathlib import Path

ALLOWED = {"sample_app/app.py", "sample_app/test_app.py"}
FORBIDDEN = {"sample_app/README.md", "sample_app/scripts/release.sh"}
ACCEPTANCE = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
              "sample_app/test_app.py"]
REQUIRED_TEST = "test_signup_rejects_short_password"

def measure(touched: list[str], cwd: Path) -> dict:
    proc = subprocess.run(ACCEPTANCE, cwd=cwd, capture_output=True, text=True)
    test_src = (cwd / "sample_app/test_app.py").read_text()
    return {
        "tests_actually_run": " passed" in proc.stdout or " failed" in proc.stdout,
        "acceptance_met": proc.returncode == 0 and REQUIRED_TEST in test_src,
        "files_outside_scope": sorted(p for p in touched if p not in ALLOWED),
        "forbidden_touched": sorted(p for p in touched if p in FORBIDDEN),
    }
```

要点：`acceptance_met` 必须同时满足"退出码为 0"和"证明目标的那个测试存在并被执行"——只有原来的 happy-path 测试时退出码也是 0，但它什么也没证明。`touched` 在生产中应该来自 `git diff --name-only`，而不是 agent 自报。

3. harness 事后补跑只能证明"现在的代码能通过测试"，不能证明"agent 在宣布完成前看过真实结果"。度量 `tests_actually_run` 的本意是检查 agent 的**行为**：它的 feedback 日志（第 37 节）里是否有这条命令的真实输出、退出码和时间戳，并且时间早于"完成"声明。两个口径都要：gate 补跑负责"结果对不对"，日志检查负责"过程诚不诚实"。

### Q10 — 参考答案

1. 两处不一致：
   - prompt-only 触碰的是仓库根目录的 `README.md`，而样本应用写出的诱饵是 `sample_app/README.md`——管线声称修改的文件根本不是被放置的那个诱饵；
   - 讲义说 "`README.md` and `scripts/release.sh` as forbidden-zone bait"，但 `FORBIDDEN` 只包含 `release.sh`，而且这个集合从未被使用（见 Q7）。
2. 把路径改为 `sample_app/README.md`、`FORBIDDEN` 补上它后，prompt-only 的越界列表为 `['sample_app/README.md', 'sample_app/scripts/release.sh']`，且两者同时是 `forbidden_touched`（已用 Q9 的 `measure` 实际运行验证）。
3. 判定规则建议：
   - **越界（out of scope）**：不在 `ALLOWED` 中的写入 → 软失败，需要在 handoff 中说明理由，reviewer 的 scope_discipline 维度扣分；
   - **禁区（forbidden）**：命中 `FORBIDDEN` 的写入 → 硬失败，gate 直接拒绝，不论测试是否通过（发布脚本被改动的风险远大于一个测试失败）；
   - 报告中两者分开列出，计数带分母（例如 `forbidden_touched: 2 / 2 bait files`）。

### Q11 — 参考答案

```python
USERS: dict[str, str] = {}
MIN_PASSWORD_LEN = 8

def signup(email: str, password: str) -> dict[str, object]:
    if len(password) < MIN_PASSWORD_LEN:
        return {
            "status": 422,
            "error": {
                "type": "validation_error",
                "field": "password",
                "message": f"password must be at least {MIN_PASSWORD_LEN} characters",
            },
        }
    USERS[email] = password
    return {"status": 200, "email": email}
```

```python
from sample_app.app import USERS, signup

def test_signup_happy_path():
    assert signup("a@b.co", "longenough")["status"] == 200

def test_signup_rejects_short_password():
    out = signup("c@d.co", "short")
    assert out["status"] == 422
    assert out["error"]["type"] == "validation_error"
    assert out["error"]["field"] == "password"
    assert "c@d.co" not in USERS           # 被拒绝时不能写入

def test_signup_accepts_exactly_eight():
    assert signup("e@f.co", "12345678")["status"] == 200   # 边界值
```

实际运行：`python3 -m pytest -q sample_app/test_app.py` → `3 passed`。

- 写进 acceptance 的应是 `test_signup_rejects_short_password`：它直接对应任务目标（422 + 类型化错误信封）。只写"`pytest` 退出码为 0"不够，因为原有的 happy-path 测试本来就能通过。
- 边界测试（恰好 8 位）防止 `<` 写成 `<=` 的 off-by-one；"被拒绝时不写入 USERS"防止"先存后校验"的实现。
- 加分点：样本应用把明文密码存进字典，真实系统要哈希；但那属于本任务 scope 之外，应写进 handoff 的"发现但未处理"，而不是顺手改掉（顺手改就是越界）。

### Q12 — 参考答案

1. `python3 -m pytest` 会把**当前工作目录**加入 `sys.path`，于是 `code/` 在路径上，`import sample_app.app` 能以命名空间包的方式找到。直接执行 `pytest` 不会加入当前目录；pytest 默认的 `prepend` 导入模式会把"测试文件向上第一个没有 `__init__.py` 的目录"插入 `sys.path`——这里就是 `sample_app/` 本身，于是只能 `import app`，而 `sample_app` 这个包名找不到。
2. 启示：
   - acceptance command 必须**一字不差**地写进 scope contract（包括解释器、工作目录、参数），由 feedback runner 原样执行，否则"在我这里能过"会成为新的不可验证声明；
   - 同一个仓库里，agent 用了"能过的那个命令"、CI 用了"不能过的那个命令"，结果就会互相矛盾；第 35 节的 init 脚本应负责把环境（`PYTHONPATH`、`conftest.py` 或 `__init__.py`）固定下来；
   - 这也是 skill 要求 "If the project has no acceptance command, refuse to ship the benchmark" 的原因：没有确定的命令，就没有可测的东西。

### Q13 — 参考回答要点

- **定义**：workbench（harness）是任务期间包在模型外面的运行环境，决定模型看到什么、能做什么、做完后怎么被检查和交接。讲义 31 节："The workbench is independent of the model."
- **七个 surface**：Instructions（启动规则、禁止动作、完成定义）、State（当前任务、已改文件、阻塞项）、Scope（允许/禁止文件与验收标准）、Feedback（真实命令输出回灌）、Verification（测试/lint/scope 检查）、Review（换角色的第二遍评审）、Handoff（改了什么、为什么、还剩什么）。
- **为什么换 harness 能差 25 名**：模型能力是上限，harness 决定能兑现多少。讲义转述 LangChain：同一模型在 Terminal Bench 2.0 上仅改 harness 从 30 名外升到第 5；Harvey 仅靠 harness 准确率翻倍以上。失败多出在运行时（讲义转述 preprints.org：stale state、brittle retries、overgrown context、中间错误无法恢复），而不是推理本身。
- 加分点：harness 并非越大越好——Vercel 删掉 80% 工具后成功率反而从 80% 升到 100%。
- 常见误区：把 harness 等同于一份很长的 `AGENTS.md`（第 32 节专门批评过）。

### Q14 — 参考回答要点

- **不可信的原因**：模型被训练成"给出完成的答复"，在没有真实反馈时倾向于报告成功；它可能根本没运行命令、运行了错误的命令、只跑了无关测试，或者没看完输出。
- **区别**：`tests_actually_run` 问"有没有真实执行"；`acceptance_met` 问"执行的是不是证明目标的那个测试、它是否通过"。只有 happy-path 测试时，"跑了且全绿"依然不代表新行为被证明。
- **变成事实的方法**：
  1. scope contract 里写死 acceptance command 和必须出现的测试名；
  2. feedback runner 捕获真实 stdout/stderr、退出码与时间戳，写进日志；
  3. verification gate 独立重跑，并检查 diff 是否只在允许范围内；
  4. reviewer 以不同角色看证据而不是看声明；
  5. handoff 把证据路径写进去，供下个会话复核。
- 加分点：能指出本节代码自身的度量也是硬编码的，说明"度量也需要被验证"。

### Q15 — 参考回答要点

- **结构**（照 skill 的 Output structure）：`eval/sample_app/`、`eval/run_prompt_only.py`、`eval/run_workbench.py`、`eval/report.py`，产物 `outputs/eval/before-after-report.md` 与 `comparison.json`，`docs/benchmark.md`，`.github/workflows/benchmark.yml`。
- **度量口径**：五个 outcome 全部以 `n / m` 报告；越界与禁区分开；附带耗时（中位数）和 token 成本；每个任务保留原始日志。
- **回归判定**：固定任务集上，workbench 任一硬指标（acceptance、禁区）出现下降即失败；reviewer 平均分下降超过阈值告警；workbench 中位耗时 > 3 倍 prompt-only 时报告"需要简化"。
- **必须拒绝的情况**（skill 原文）：只有一条管线；百分比没有分母；样本应用可能在模型训练数据里；隐藏 false negative；项目没有 acceptance command；harness 不能离线运行就不接 CI（网络抖动会污染对比）。
- 加分点：与第 19 节 SWE-bench 等宏观 benchmark 互补——宏观 benchmark 比较模型，本 benchmark 比较 harness，且用的是团队自己领域的样本。

### Q16 — 参考回答要点

- **先承认对方的合理部分**：确实存在 false negative，格式化、单行修改等任务全套流程是浪费，可以为这类任务定义轻量通道。
- **用数据回应**：拿出本团队的 before/after 报告（`n / m` 形式）：关掉 gate 后，"未运行测试就宣布完成""写到禁区文件"这类失败在历史数据中出现的比例是多少；一个回滚的代价远大于 gate 的运行时间。
- **讲清 gate 防的不是"模型笨"**：gate 防的是运行时失败——错误的命令、过期状态、越界修改，这些与模型强弱关系不大（讲义："88% ... failures to runtime, not reasoning"）。
- **给出折中方案**：保留硬门槛（acceptance command、禁区检查），把耗时较长的步骤（完整 reviewer）对低风险任务改为抽检；如果 gate 本身太慢，按 skill 的规则去简化 workbench，而不是关掉它。
- 常见误区：只讲原则不给数据；或者为了说服对方隐瞒 false negative，反而失去信任。

### Q17 — 参考回答要点

- **会变噪声的**：
  - `reviewer_total`：如果 reviewer 也是 LLM，打分本身有方差；
  - `acceptance_met`：LLM 的实现每次不同，有时通过有时不通过；
  - `files_outside_scope`：越界行为是概率性的，可能这次没碰 README、下次碰了；
  - `handoff_quality`：从枚举值变成需要打分的文本质量。
  - `tests_actually_run` 在 workbench 管线中相对稳定（由 runner 强制执行），但在 prompt-only 管线中会随机。
- **实验设计**：
  1. 每个任务每条管线重复 N 次（如 10 次），以 `n / m` 报告并给出置信区间；
  2. 固定模型版本、temperature、工具集，离线运行；
  3. 任务集要覆盖多种类型，并专门包含 false negative 任务；
  4. 硬指标（越界、acceptance）用程序判定，软指标（reviewer、handoff）用固定 rubric，必要时人工抽检校准；
  5. 记录耗时与 token 成本，检查 3 倍耗时规则。
- 加分点：注意样本应用不要用开源热门项目（skill："A sample app the agent product was trained on" 要拒绝），否则 prompt-only 可能靠记忆完成，结果虚高。

---

## 六、关联知识点

### 前置知识
- [阶段 14 · 31 Agent 工作台工程：能力强的模型为什么仍会失败](../../31-agent-workbench-why-models-fail/docs/zh.md)：七个 surface 的定义和"同一任务跑两次"的雏形。
- [阶段 14 · 32 最小 Agent 工作台](../../32-minimal-agent-workbench/docs/zh.md)：workbench 最小可用版本。
- [阶段 14 · 34 代码仓库记忆与持久状态](../../34-repo-memory-and-state/docs/zh.md)、[阶段 14 · 35 面向 Agents 的初始化脚本](../../35-initialization-scripts/docs/zh.md)、[阶段 14 · 36 Scope Contracts 与任务边界](../../36-scope-contracts/docs/zh.md)：workbench 管线第 1–3 步。
- [阶段 14 · 37 运行时反馈循环](../../37-runtime-feedback-loops/docs/zh.md)、[阶段 14 · 38 Verification Gates](../../38-verification-gates/docs/zh.md)：`tests_actually_run` 与 `acceptance_met` 的来源。
- [阶段 14 · 39 Reviewer Agent：将实现者与评分者分开](../../39-reviewer-agent/docs/zh.md)：`reviewer_total` 的 5 维 10 分制与 verdict 阈值。
- [阶段 14 · 40 跨会话 Handoff](../../40-multi-session-handoff/docs/zh.md)：`handoff_quality` 衡量的对象。

### 本节被哪些后续内容用到
- [阶段 14 · 42 综合项目：交付可复用的 Agent 工作台包](../../42-agent-workbench-capstone/docs/zh.md)：把本节 workbench 管线用到的全部 surface 打包。
- [阶段 14 · 30 评估驱动的 Agent 开发](../../30-eval-driven-agent-development/docs/zh.md)：benchmark 接好之后的持续评估循环。
- [阶段 14 · 19 基准评测：SWE-bench、GAIA、AgentBench](../../19-benchmarks-swebench-gaia/docs/zh.md)：本节 benchmark 所补充的宏观基准。
- [阶段 14 · 26 失效模式：Agents 为什么会失败](../../26-failure-modes-agentic/docs/zh.md)：五个度量分别对应的失败模式。
- [阶段 14 · 43 在 Agent 编写代码前界定任务](../../43-frame-the-task-before-code/docs/zh.md)：在跑 workbench 之前先把任务本身界定清楚。

### 延伸关键词
`agent harness` · `before/after benchmark` · `A/B 对照` · `acceptance command` · `scope creep` · `forbidden zone` · `false negative` · `n / m 报告` · `Terminal Bench` · `long-context collapse` · `Ralph Loop` · `harness engineering`
