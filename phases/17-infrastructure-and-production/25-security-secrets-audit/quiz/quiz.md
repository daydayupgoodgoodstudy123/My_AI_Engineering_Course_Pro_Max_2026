# 测验 · 安全：密钥、API 密钥轮换、Audit Logs 与 Guardrails（Security — Secrets, API Key Rotation, Audit Logs, Guardrails）

> **阶段 17 · 基础设施与生产 · 第 25 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 密钥蔓延（secret sprawl）的四种反模式 | 配置文件进版本库、硬编码在 env 文件里、存在电子表格里、使用静态密钥；替代方案是集中式 vault + IAM 角色 + CI/CD 的 OIDC |
| 2 | AI 网关从 vault 拉取凭证 | 应用 → 网关 → 模型 provider，网关在运行时从 vault 取 `OPENAI_API_KEY`；在 vault 中轮换后下一次请求即用新 key，无需重新部署 |
| 3 | 轮换与扫描 | 所有 API key、vault root token、CI/CD 凭证轮换周期 ≤ 90 天（skill 建议 CI/CD 30 天）；每次 commit 用 TruffleHog / GitGuardian / Gitleaks 扫描，发现新密钥就阻止 PR |
| 4 | 零信任 | MFA、SSO（SAML/OIDC）、RBAC/ABAC、短期 token（小时级）、设备状态检查 |
| 5 | PII/PHI 脱敏 | 实体识别（spaCy NER、Presidio）+ 正则；把实体替换成占位符；**一致性 tokenization**（同一值 → 同一占位符）让 LLM 仍能理解实体间关系；可选的反向映射 |
| 6 | 输入/输出 guardrail | 输入：拦截已知越狱与禁止话题、按用户限流；输出：正则扫描泄漏的密钥/邮箱、策略违规分类器 |
| 7 | 网络出口白名单 | LLM 服务放在专用子网，只允许访问 provider、向量库、vault 等域名，其余全部丢弃；DNS 走只解析白名单的 resolver，防 DNS 隧道外泄 |
| 8 | Audit log | 每次 LLM 调用一条不可篡改记录：时间、用户/租户、prompt 哈希（不存原文）、模型与版本、token 数、成本、响应哈希、guardrail 触发；讲义：SOC 2 保留 1 年、HIPAA 6 年 |
| 9 | 2026 Vercel 事件（讲义所述） | 被攻破的 CI/CD 凭证导致成千上万客户部署的环境变量外泄；教训：CI/CD 凭证等同生产凭证，放 vault、窄权限、积极轮换 |
| 10 | 本节代码的问题 | 电话正则漏掉左括号（输出 `([PHONE_002]`）、同一号码不同写法得到不同占位符、所谓"不可变 audit log"只是打印 JSON、哈希不加盐且截断到 48 位 |

### 核心技能（能动手做到）

- [ ] 为一个 LLM 服务画出"应用 → 网关 → vault → provider"的凭证流，并说明轮换时发生什么
- [ ] 写出带一致性 tokenization 的 PII 脱敏器，并处理格式归一化（电话号码、大小写）
- [ ] 找出 `PHONE` 正则的边界 bug 并修复
- [ ] 设计按租户隔离的占位符（HMAC + 租户密钥），避免跨租户关联
- [ ] 实现一个哈希链（hash chain）的追加式 audit log，并能验证是否被篡改
- [ ] 为 vLLM-on-EKS 调用 OpenAI + Anthropic + Weaviate 设计出口策略

---

## 二、基础自测（选择题）

**Q1.** 下列哪一项**不是**讲义所说的密钥管理反模式？

- A. 把含密钥的配置文件提交到版本库
- B. 把 API key 硬编码在 env 文件里
- C. 用电子表格记录各环境的密钥
- D. 让应用通过 IAM 角色向 vault 换取短期凭证

**Q2.** 讲义把"AI 网关在运行时从 vault 拉取凭证"称为 2026 年生产标准。它最直接解决的问题是：

- A. 降低模型推理延迟
- B. 轮换密钥时无需修改几十个配置文件、无需重新部署，下一次请求就用新 key
- C. 让每个开发者都能看到明文 key，方便排障
- D. 取代 PII 脱敏

**Q3.** 一致性 tokenization（同一值 → 同一占位符）的主要目的是：

- A. 让 LLM 在看不到真实值的情况下，仍能理解"这两处提到的是同一个人/同一个账户"之类的关系
- B. 让占位符更短，节省 token
- C. 让脱敏过程可以完全不用正则
- D. 加密 PII，使其可以安全地发送给 provider 并由 provider 解密

**Q4.** 讲义描述：EKS 集群里的 LLM Pod 可以访问任意外网主机，攻击者通过向自己控制的域名发 DNS 查询外泄数据。最对症的防护是：

- A. 给 Pod 加更多 CPU 限制
- B. 每 90 天轮换一次 API key
- C. 出口白名单（只允许 provider、向量库、vault 等域名）+ 只解析白名单域名的 DNS resolver
- D. 在 audit log 里记录完整 prompt

**Q5.** 关于 audit log 应记录的内容，讲义的要求是：

- A. 完整的原始 prompt 与响应，方便复盘
- B. 只记录出错的调用
- C. prompt 与响应的**哈希**、用户/租户、模型与版本、token 数、成本、guardrail 触发，不存原始 prompt
- D. 只记录 token 数与成本，用于计费

**Q6.** 运行本节代码，第 3 条 prompt 中的 `(202) 555-0150` 被脱敏成 `([PHONE_002]`。原因是：

- A. 正则开头的 `\b` 要求单词边界，空格与 `(` 之间不是单词边界，于是匹配从 `202` 开始，可选的 `\(?` 被跳过，左括号留在原文
- B. `SSN` 正则先执行，吃掉了左括号
- C. `EMAIL` 正则把括号当成了邮箱字符
- D. 占位符格式字符串 `f"[{kind}_..."` 多写了一个括号

**Q7.** 你在 2 年前的 git 历史中发现了一个仍然有效的 API key。正确的处理顺序是：

- A. 只需重写 git 历史删除它，key 不用动
- B. 只需轮换 key，历史不用管
- C. 先在代码里加注释说明该 key 已废弃
- D. 立即轮换/吊销 key（视为已泄露），检查 provider 侧的使用日志，再清理历史并加上提交扫描防止复发

**Q8.** 讲义从 2026 年 Vercel 供应链事件中得出的教训是：

- A. 不要使用 serverless 平台
- B. CI/CD 凭证等同于生产凭证：存入 vault、窄化权限、积极轮换，并用 OIDC 身份联合取代静态云密钥
- C. 把所有环境变量改成明文写在代码里，便于审计
- D. 关闭 CI/CD，改为手工部署

---

## 三、动手 / 代码题

**Q9.** 本节的电话正则：

```python
PHONE = re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")
```

实际测试结果：

```text
'call (202) 555-0150'   -> 'call ([PHONE_001]'
'call 202-555-0150'     -> 'call [PHONE_002]'
'call 202.555.0150'     -> 'call [PHONE_003]'
'call +1 202 555 0150'  -> 'call +[PHONE_004]'
'order 4155550199'      -> 'order [PHONE_005]'
```

1. 解释为什么 `(` 和 `+` 会残留。
2. 同一个号码 202-555-0150 得到了 4 个不同的占位符，这破坏了什么性质？
3. 给出修复后的正则与归一化函数。
4. `order 4155550199` 被当成电话号码，这说明正则方法有什么固有局限？

**Q10.** 代码只有一个全局 `Scrubber` 实例，所有用户/租户共享；占位符是按出现顺序编号的 `[SSN_001]`；打印 token 表时显示 `123***`。请指出这三处设计分别带来什么隐私风险，并给出一个按租户隔离的占位符生成函数。

**Q11.** 代码 docstring 声称"Appends to an immutable audit log on every call"，而实现是：

```python
def hash_short(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()[:12]

def audit_log_call(entry: AuditEntry) -> str:
    return json.dumps({...})
```

1. 这个"audit log"在哪些方面并不"不可变"？
2. 对脱敏后的 prompt 做不加盐的 SHA-256，有什么风险？截断到 12 个十六进制字符（48 位）又有什么影响？（估算 1,000 万条记录时出现至少一次碰撞的概率）
3. 写一个哈希链（hash-chained）的追加式日志，并说明如何检测篡改。

**Q12.**（讲义练习 4）audit log 每天增长 10 GB，需要满足 6 年保留。设计热 / 温 / 冷三层存储（热 30 天、温 12 个月、冷 6 年），计算每层的原始数据量，并说明各层的访问方式与不可变性保障。

---

## 四、面试高频题

**Q13.**（基础必考）一个 LLM 应用应该如何管理 provider 的 API key？从存储、分发、轮换、检测泄漏四个方面回答。

**Q14.**（原理深挖）（讲义练习 5）PII 脱敏为什么要"正则 + NER 一起用"？一致性 tokenization 有哪些坑？反向 tokenization（把真实值替换回 LLM 输出）值得做吗？

**Q15.**（工程实践）（讲义练习 2）为一个部署在 EKS 上、需要调用 OpenAI、Anthropic 和 Weaviate 的 vLLM 服务设计网络出口策略。

**Q16.**（场景设计）（讲义练习 3）安全扫描在 2 年前的 git 历史中发现了一个 OpenAI key。你会怎么做？轮换、清理历史还是两者都做？

**Q17.**（追问型）CI/CD 凭证为什么"等同生产凭证"？OIDC 身份联合是如何消除静态云密钥的？

---

## 五、参考答案与解析

### Q1 — 答案：D

讲义学习目标："four secret-management anti-patterns (config files in VCS, hardcoded env, spreadsheets, static keys)"。D 是替代方案："IAM role: app/gateway authenticates via its IAM identity, not a static key"。A、B、C 都是反模式。

### Q2 — 答案：B

讲义："gateway pulls `OPENAI_API_KEY` from vault at request time. Rotate in vault; next request gets the new key. No redeploys." 问题部分描述的反面情况是"Slack 通知团队、改 40 个配置文件、重新部署所有服务，8 小时后只有一半服务上线"。A 与安全无关；C 恰好违背最小权限；D 是另一个层面的控制。

### Q3 — 答案：A

讲义："Consistent tokenization (Mesh approach): same value maps to the same placeholder so the LLM preserves relationships." 例如"联系 [SSN_001] 关于账户 [EMAIL_001]"中，LLM 能知道这与上一句提到的是同一个人。

- B：占位符通常比原值更长。
- C：一致性与检测方式（正则/NER）无关。
- D：tokenization 不是加密，provider 无法也不应解密；映射表只保存在自己的基础设施内。

### Q4 — 答案：C

讲义："Whitelist: `api.openai.com`, `api.anthropic.com`, vector DB endpoints, vault endpoints. Everything else: drop. DNS via allowlist-only resolver (avoid DNS-tunneling exfil)." 注意仅有出口防火墙还不够——DNS 查询本身可以携带数据，必须让 resolver 只解析白名单域名。A、B、D 都不能阻止外泄，D 还会扩大泄漏面。

### Q5 — 答案：C

讲义 Audit log 字段列表："Prompt hash (not raw prompt for privacy)... Response hash. Any guardrail trips." skill 文件把"在 audit log 中存储原始 prompt"列为 hard reject（除非监管框架明确要求）。A 把 audit log 变成了 PII 仓库；B、D 不满足合规审计的完整性要求。

### Q6 — 答案：A

`\b` 是"单词字符与非单词字符之间"的位置。`call (202)` 中空格和 `(` 都是非单词字符，它们之间没有 `\b`，所以正则无法从 `(` 开始匹配；引擎继续向后找，在 `(` 与 `2` 之间找到了 `\b`，此时 `\(?` 匹配空串。实际匹配区间是 `202) 555-0150`，左括号残留，token 表里存的值也是 `202) 555-0150`。

- B：SSN 正则只匹配 `ddd-dd-dddd`。
- C：邮箱正则要求 `@`。
- D：占位符是 `[PHONE_002]`，左括号来自原文。

### Q7 — 答案：D

一旦进入 git 历史，就应假定 key 已被复制（克隆、fork、CI 缓存、备份都可能保存了副本）。只清理历史（A）无法收回已经流出的副本；只轮换（B）会让历史中留着一个"看起来像密钥"的字符串，持续触发扫描告警并可能误导他人。正确顺序：先吊销/轮换（止血）→ 查 provider 侧使用日志与账单，确认是否被滥用 → 清理历史（`git filter-repo` 等）并通知所有克隆者 → 加 commit 前与 CI 扫描防止复发。C 毫无防护作用。

### Q8 — 答案：B

讲义："Lesson: CI/CD credentials are prod-equivalent. Store in vault. Scope narrowly. Rotate aggressively." skill 文件补充："OIDC identity federation (no static cloud keys)... Cite the 2026 Vercel supply-chain incident as motivation."（该事件为讲义所述，讲义未附具体来源。）A、D 因噎废食；C 与安全目标背道而驰。

### Q9 — 参考答案

1. **残留原因**：
   - `(`：见 Q6，`\b` 无法出现在空格与 `(` 之间，匹配起点被推到 `202`。
   - `+`：`+` 也是非单词字符，空格与 `+` 之间没有 `\b`；引擎在 `+` 与 `1` 之间找到边界，`\+?` 匹配空串，`1 ` 被 `1[-.\s]?` 吃掉，结果 `+` 残留，token 表中的值是 `1 202 555 0150`。
2. **破坏的性质**：一致性 tokenization。LLM 看到 `[PHONE_001]` 与 `[PHONE_002]` 会认为是两个不同号码，"同一实体"的关系丢失；token 表也会无谓膨胀。同理，`JANE.DOE@EXAMPLE.COM` 与 `jane.doe@example.com` 也会得到不同占位符（大小写未归一化）。
3. **修复**（已运行验证）：

```python
PHONE = re.compile(
    r"(?<!\w)(?:\+?1[-.\s]?)?(?:\(\d{3}\)|\d{3})[-.\s]?\d{3}[-.\s]?\d{4}\b")

def normalize(kind, value):
    if kind == "PHONE":
        return re.sub(r"\D", "", value)[-10:]       # 只保留后 10 位数字
    if kind == "EMAIL":
        return value.strip().lower()
    return re.sub(r"\D", "", value)                  # SSN 去掉分隔符
```

   - 用负向后顾 `(?<!\w)`（"前面不是单词字符"）代替开头的 `\b`，这样匹配可以从 `(` 或 `+` 开始；
   - 用 `(?:\(\d{3}\)|\d{3})` 要求括号成对出现；
   - 测试：`phone (202) 555-0150.` → `phone [PHONE].`；`+1 (202) 555-0150` → `[PHONE]`；
   - `_token_for` 中用 `normalize(kind, value)` 作为字典键：`(202) 555-0150` 与 `+1 202-555-0150` 都归一化为 `2025550150`，得到同一个占位符。
4. **固有局限**：正则只看形状不看语义。10 位订单号、发票号会被误判为电话（误报）；`123 45 6789`、`123456789` 这类 SSN 写法、信用卡号 `4111 1111 1111 1111`、人名 "Jane Doe"、地址都**没有**被识别（实测均原样保留，即漏报）。所以讲义说"Static regex filters catch basic patterns; NER catches more. Use both."，再加上校验规则（如信用卡 Luhn 校验）和上下文词（"SSN"、"phone"）来降低误报。

### Q10 — 参考答案

| 设计 | 风险 |
|------|------|
| 全局共享一个 `Scrubber` | 不同租户的同一 SSN 会得到同一个占位符。若占位符出现在任何跨租户可见的地方（日志、缓存、评估数据集），就能把两个租户的记录关联起来；映射表本身汇集了所有租户的明文 PII，成为高价值攻击目标 |
| 按顺序编号 `[SSN_001]` | 编号泄露了"这是本进程见过的第几个不同 SSN"，可推断用户量与出现顺序；进程重启后编号重置，同一值在不同时间得到不同占位符，跨会话不一致 |
| 打印 `123***` | SSN 前 3 位（区域号）、电话区号、邮箱前缀被写进标准输出/日志，属于部分泄露；与其他信息组合可能重新识别个人 |

按租户隔离的占位符（已运行验证）：

```python
import hmac, hashlib

def placeholder(kind, value, tenant_key: bytes) -> str:
    norm = normalize(kind, value)                     # 见 Q9
    digest = hmac.new(tenant_key, f"{kind}:{norm}".encode(),
                      hashlib.sha256).hexdigest()[:6]
    return f"[{kind}_{digest}]"
```

- 同一租户：`(202) 555-0150` 与 `+1 202-555-0150` 都得到 `[PHONE_bd7cb5]`；`Jane.Doe@Example.com` 与 `jane.doe@example.com` 都得到 `[EMAIL_6f1038]`。
- 不同租户：同一 SSN `123-45-6789` 在租户 A 是 `[SSN_1785dc]`，在租户 B 是 `[SSN_b56833]`，无法跨租户关联。
- `tenant_key` 存在 vault 中；HMAC 让没有密钥的人无法通过穷举 SSN（只有 10⁹ 种）反推出原值。截断 6 位十六进制在同一租户内可能碰撞，可在映射表写入时检测碰撞并加长。
- 反向映射（如需）存放在加密存储里，按租户隔离、设置 TTL，并记录访问日志。这与讲义示例占位符 `[SSN_TOKEN_A3F]` 的"非顺序、看起来像哈希"的风格一致。

### Q11 — 参考答案

1. **并不"不可变"**：`audit_log_call` 只是把字典序列化成 JSON 字符串并打印，没有写入任何存储；就算写入普通文件，也可以被任意修改或删除；没有序号、没有前后链接、没有签名，无法发现缺失或篡改。真正的不可变需要 WORM 存储（如对象存储的 Object Lock / 合规保留模式）、哈希链或签名、以及与写入者分离的权限。
2. **哈希的问题**：
   - **不加盐可被字典攻击**：脱敏后的 prompt 往往来自少量模板（"Please contact [SSN_001] regarding account [EMAIL_001]."），攻击者可以枚举候选文本计算 SHA-256 来确认某条记录的内容。应使用 HMAC（密钥存在 vault）。
   - **截断到 48 位**：按生日问题估算，`p ≈ 1 − exp(−n² / 2N)`，`N = 2⁴⁸`。实际计算：100 万条约 0.18%，1,000 万条约 **16.3%**，约 1,670 万条时约 39%。每天 10 GB 的日志很快达到千万级，"用哈希证明是哪条 prompt"在碰撞时会失效。审计用途建议保留完整 256 位。
   - 另外：`input_tokens = len(scrubbed.split())` 是**单词数**而不是 token 数，`cost_usd` 是常量，`datetime.utcnow()` 在 Python 3.12+ 已弃用（本次运行在 Python 3.13 下启用警告时会打印 DeprecationWarning），应改用 `datetime.now(timezone.utc)`。
3. **哈希链日志**（已运行验证）：

```python
class ChainedAuditLog:
    def __init__(self, hmac_key: bytes):
        self.key, self.entries, self.prev = hmac_key, [], "0" * 64

    def append(self, record: dict) -> dict:
        body = dict(record, ts=datetime.now(timezone.utc).isoformat(), prev=self.prev)
        body["entry_hash"] = hashlib.sha256(
            json.dumps(body, sort_keys=True).encode()).hexdigest()
        self.prev = body["entry_hash"]
        self.entries.append(body)
        return body

    def prompt_digest(self, scrubbed: str) -> str:          # 带密钥的哈希
        return hmac.new(self.key, scrubbed.encode(), hashlib.sha256).hexdigest()

    def verify(self) -> bool:
        prev = "0" * 64
        for e in self.entries:
            body = {k: v for k, v in e.items() if k != "entry_hash"}
            if body["prev"] != prev or hashlib.sha256(
                    json.dumps(body, sort_keys=True).encode()).hexdigest() != e["entry_hash"]:
                return False
            prev = e["entry_hash"]
        return True
```

   写入 3 条后 `verify()` 返回 True；把第 2 条的 `user` 改成 `"attacker"` 后返回 False。每条记录包含上一条的哈希，修改任意一条都会让它及其后所有链接失效。仍需配合：定期把最新的链头哈希写到另一个独立系统（或公证/签名），否则攻击者可以重算整条链；日志写入 WORM 存储。

### Q12 — 参考答案

原始数据量（未压缩、按 365 天/年计）：

| 层 | 保留期 | 数据量 | 存储与访问 |
|----|-------|-------|-----------|
| 热 | 30 天 | `10 × 30 = 300 GB` | 可检索的日志/搜索系统（如 OpenSearch、ClickHouse），秒级查询，用于事故调查与安全分析 |
| 温 | 12 个月 | `10 × 365 = 3,650 GB ≈ 3.65 TB`（含热层这 30 天） | 对象存储标准/低频层，Parquet 等列式格式 + 分区，按需用查询引擎（Athena、Trino）扫描，分钟级 |
| 冷 | 6 年 | `10 × 365 × 6 = 21,900 GB ≈ 21.9 TB` | 归档层（如 Glacier 类），小时级取回；只用于合规审计与法律取证 |

设计要点：

- **压缩**：JSON 日志通常有很高的压缩率，转为列式格式后存储量会显著下降；具体比例需实测。
- **不可变**：温、冷层开启 Object Lock（合规模式）并设置与保留期一致的锁定期；写入权限与删除权限分离，删除需双人审批。
- **生命周期**：用对象存储生命周期规则自动迁移 30 天 → 低频层、1 年 → 归档层、6 年后删除（删除本身也要留审计记录）。
- **完整性**：每天对当日日志生成清单与哈希（或哈希链头），单独保存，审计时可证明未被篡改。
- **保留期依据**：讲义给出 SOC 2 1 年、HIPAA 6 年；实际保留期以适用的法规与审计师要求为准，GDPR 的数据最小化原则还要求不要无理由地长期保存个人数据（这也是只存哈希不存原文的原因之一）。

### Q13 — 参考回答要点

- **存储**：集中在 vault（HashiCorp Vault、AWS Secrets Manager、Azure Key Vault、GCP Secret Manager），不进代码、不进 env 文件、不进表格。
- **分发**：应用/网关以 IAM 角色或工作负载身份向 vault 认证，换取短期凭证；最好只有 AI 网关持有 provider key，业务应用只调用网关（讲义的 2026 标准模式）。CI/CD 用 OIDC 联合身份，不存静态云密钥。
- **轮换**：≤ 90 天，CI/CD 建议 30 天；在 vault 中轮换，网关下一次请求自动取新 key；轮换过程记录日志。可以让新旧 key 短暂并存实现无缝切换。
- **检测泄漏**：每次 commit 与 CI 中运行 TruffleHog / GitGuardian / Gitleaks，命中即阻止 PR；输出 guardrail 用正则扫描响应中是否出现 key 模式；监控 provider 侧的异常用量。
- 加分点：skill 文件的单一指标"每月 secret-scan 命中数，目标为零"；按用途拆分 key（每个服务/环境一个），泄漏时能精准吊销。
- 常见误区：以为删除提交就等于修复泄漏。

### Q14 — 参考回答要点

- **正则 + NER**：
  - 正则擅长格式固定的实体（SSN、邮箱、电话、信用卡），可解释、快；但不认识人名、地址、病情描述，且对格式变化敏感（Q9 的括号问题、空格分隔的 SSN）。
  - NER（spaCy、Presidio 的识别器）能识别人名、地点、组织等语义实体，但有漏检和误检、需要语言模型、延迟更高。
  - 两者互补；skill 文件指出脱敏延迟通常 < 20 ms，不能以延迟为由拒绝脱敏。
- **一致性 tokenization 的坑**：
  - 必须先归一化（格式、大小写），否则同一实体得到多个占位符；
  - 映射表本身是敏感数据，需加密、按租户隔离、设 TTL；
  - 顺序编号会泄露信息，宜用带密钥的 HMAC；
  - 跨会话保持一致需要持久化映射（或确定性的 HMAC），持久化又增加泄漏面。
- **反向 tokenization（练习 5）**：
  - 价值：用户看到的回答里是"您的邮箱 jane.doe@example.com"而不是 `[EMAIL_001]`，体验更自然；工具调用（发邮件、查账户）需要真实值。
  - 代价：映射表必须在请求生命周期内可用；LLM 可能改写或拆分占位符（`[EMAIL_001]` 变成 "EMAIL 001"），需要容错匹配；反向替换后的响应若写入日志又会重新引入 PII；
  - 折中：面向终端用户的对话做反向替换，但只在返回给该用户的那一跳替换，日志与监控中保留占位符；内部分析场景保持占位符可见。
- 加分点：输出侧也要扫描，防止模型凭上下文"猜"出被遮盖的信息或复述其他用户的数据。

### Q15 — 参考回答要点

- **分层控制**（安全组只能按 IP/端口过滤，无法按域名放行，因此需要能识别域名的组件）：
  1. **子网与路由**：vLLM 与网关 Pod 所在节点放在私有子网，出站只能经过 NAT + 出口防火墙（或出口代理）。
  2. **出口防火墙 / 代理**：按域名（TLS SNI / HTTP Host）放行 `api.openai.com`、`api.anthropic.com`、Weaviate 实例的域名、vault 端点；其余全部拒绝。可用 AWS Network Firewall 的域名列表规则，或部署显式出口代理。
  3. **DNS**：VPC 使用只解析白名单的 DNS 防火墙规则（如 Route 53 Resolver DNS Firewall），其余域名返回 NXDOMAIN，防止 DNS 隧道。
  4. **集群内**：Kubernetes NetworkPolicy 默认拒绝出站；只有网关 Pod 允许访问外部，vLLM Pod 只允许访问网关、向量库、vault。支持 FQDN 策略的 CNI（如 Cilium）可以在 Pod 级别按域名放行。
  5. **私有连接**：AWS 自身服务（Secrets Manager、S3）走 VPC Endpoint，不经公网。
- **补充**：模型权重下载（如 Hugging Face）只在构建镜像或初始化阶段放行，运行时关闭；监控被拒绝的出站连接并告警——那往往是攻击或配置错误的第一个信号。
- 常见误区：只配置 NetworkPolicy 而忽略 DNS；或用 `0.0.0.0/0` 放行 443 端口"图方便"（skill 文件："Allowing egress to `*` or 'the internet.' Refuse"）。

### Q16 — 参考回答要点

- **两者都要做，先轮换**：
  1. 立即在 OpenAI 控制台吊销该 key 并在 vault 中生成新 key；若网关从 vault 拉取，切换无需重新部署。
  2. 查看 provider 侧的使用日志、账单和组织审计日志，确认 2 年间是否有异常调用；如有，按安全事件处理并评估数据泄露范围。
  3. 清理 git 历史（`git filter-repo` 或 BFG），强制推送，通知所有协作者重新克隆；同时清理 CI 缓存、制品、fork 中的副本——但要明白清理只能"减少未来暴露"，不能"收回已暴露"。
  4. 找到根因：为什么当时没被拦住（缺 pre-commit hook？CI 未扫描历史？），补上 TruffleHog / Gitleaks 的全历史扫描与 PR 阻断。
  5. 复盘：记录在 audit 与安全事件台账中。
- **理由**：key 在历史中存在了 2 年，必须假设已经泄露；轮换是唯一能真正止损的动作。只清理历史而不轮换是最常见的错误。

### Q17 — 参考回答要点

- **为什么等同生产凭证**：CI/CD 系统能构建并部署生产代码、读取部署所需的全部环境变量和密钥、往往拥有云账号的高权限。攻破 CI/CD 等于拿到了"把任意代码送进生产"和"读取所有生产密钥"的能力。讲义的 Vercel 事件正是 CI/CD 凭证被攻破后环境变量被大规模外泄。
- **OIDC 身份联合**：CI 平台（如 GitHub Actions）在每次运行时签发一个短期 OIDC token，声明"哪个仓库、哪个分支、哪个工作流"；云厂商的 IAM 信任该签发方，并按 token 中的声明（例如只允许 `main` 分支的部署工作流）授予一个短期角色凭证。全程没有长期有效的静态 access key 存放在 CI 中，被窃取的 token 很快过期且权限受限。
- **配套措施**：按环境、按仓库窄化角色权限；部署步骤与测试步骤用不同身份；CI 中的第三方 action/插件固定版本或哈希；CI 访问 vault 时也用 OIDC。
- 加分点：skill 文件建议 CI/CD 凭证 30 天轮换（比普通的 90 天更短）。

---

## 六、关联知识点

### 前置知识
- [阶段 17 · 19 AI 网关：LiteLLM、Portkey、Kong AI Gateway、Bifrost](../../19-ai-gateways/docs/zh.md)：网关从 vault 拉取凭证的前提。
- [阶段 17 · 13 LLM Observability 技术栈选型](../../13-llm-observability/docs/zh.md)：audit log 与 trace 的关系。
- [阶段 00 · 04 APIs 与密钥](../../../00-setup-and-tooling/04-apis-and-keys/docs/zh.md)：API key 的基础管理习惯。
- [阶段 11 · 12 Guardrails,安全及内容过滤](../../../11-llm-engineering/12-guardrails/docs/zh.md)：输入/输出 guardrail 的实现方式。

### 本节被哪些后续内容用到
- [阶段 17 · 26 合规：SOC 2、HIPAA、GDPR、PCI-DSS、EU AI Act、ISO 42001](../../26-compliance-frameworks/docs/zh.md)：audit log 保留期、PII 处理是各合规框架的共同控制项。
- [阶段 17 · 27 LLMs 的 FinOps：单位经济性与多租户成本归因](../../27-finops-llms/docs/zh.md)：audit log 中的 token 与成本字段用于成本归因。
- [阶段 18 · 15 Indirect Prompt Injection：生产环境的攻击面](../../../18-ethics-safety-alignment/15-indirect-prompt-injection/docs/zh.md)：出口白名单是阻止注入后数据外泄的最后一道防线。
- [阶段 18 · 22 面向 LLMs 的差分隐私](../../../18-ethics-safety-alignment/22-differential-privacy-for-llms/docs/zh.md)：比脱敏更强的隐私保护手段。
- [阶段 19 · 08 面向受监管行业的生产级 RAG 聊天机器人](../../../19-capstone-projects/08-production-rag-chatbot/docs/zh.md)：综合项目中落地脱敏、审计与出口控制。

### 延伸关键词
`secret sprawl` · `HashiCorp Vault` · `AWS Secrets Manager` · `IAM role / workload identity` · `OIDC federation` · `TruffleHog / Gitleaks / GitGuardian` · `git filter-repo` · `Presidio` · `NER` · `consistent tokenization` · `HMAC` · `egress allowlist` · `DNS firewall` · `NetworkPolicy / Cilium FQDN` · `hash chain` · `WORM / Object Lock` · `zero trust`
