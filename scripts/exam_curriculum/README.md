# 分关面试题（exam/）出题规范

每课的 `exam/` 和 `coderpad/` 同级，是一套 60 分钟的结对编程面试题，形式照 Edison Scientific 的 backend pair session：一个写好一半的小服务，5 个测试用 `@pytest.mark.skip("Part N")` 锁住，一次解锁一关，要求测试原样全部通过。

样板：[06/03 ClipTag](../../phases/06-speech-and-audio/03-audio-classification/exam/)。新题的文件结构、文档骨架、语气都以它为准。

## 设计方法

先读完这一课的 `docs/en.md` 和 `code/`，再动笔。五关是一个能力骨架，内容必须从这一课长出来：

| 关 | 能力 | 内容从哪来 |
|---|---|---|
| 1 修 | 在别人的代码里调试 | 本课自己的代码，加上课里写明的 Pitfalls。3–5 个叠在一起的缺陷，修好一个才露出下一个 |
| 2 存 | 建模和持久化 | 这个领域真正要存的状态。必须有一个“存进去再读出来完全一致”的断言，用的是这个领域自己的精度陷阱 |
| 3 算 | 核心算法 | 本课的核心算法，放进服务里实现，至少 3 个陷阱 |
| 4 流 | 流式、在线、分批、异步 | 这个领域里“数据随时间到达”的那一面。输出格式由测试里的解析代码决定 |
| 5 构 | 嵌套、递归、图 | 这个领域自带的树、DAG 或嵌套结构 |

某一关在这一课里不自然时，换成这一课里更自然的东西，在 SCOPE.json 里写明，不硬凑。不往检索、RAG 上套，除非这一课本身就讲这个。

同一章里还要避免形式上的重复：

- 各课的核心算法不能重复。Part 1 预埋的缺陷也不能重复，判断标准是候选人做到这里会不会觉得“这个 bug 刚修过”，而不是“都算 off-by-one”这种大类。
- Part 2 的存储方式要轮换：SQLite、追加写的日志文件、二进制格式、内容寻址的文件、JSON 快照等。同一章里用 SQLite 的不超过一半。
- Part 4 的输出格式要轮换：NDJSON、SSE、原始字节流、长度前缀帧，或者 RTTM、CSV 这类领域格式。同一种格式不超过同一章的三分之一。
- 同一类陷阱（漏 commit、`INSERT OR REPLACE` 改了行号、对 0 取对数）在一章里最多出现两次。这里的陷阱指候选人能直接感受到的：Part 1 预埋的缺陷，以及每关测试主要围绕的那个坑（INTERVIEWER.md 里每关“坑”的前几条）。`traps.json` 里的 `wrong_fixes` 是验证用的错误写法，越多越好，不受这条限制；测试里顺带覆盖的边界也不算。
- 为满足这些规则只能替换，不能删减：不删 `wrong_fixes`、断言或测试，换掉的那一关测试强度不能下降。

出题前先看同章已有的 `exam/`，或者章节索引 `phases/<章>/EXAM.md`。

## 文件

```
exam/
  README.md            英文题面，照样板写，每关一两句
  使用说明.md          中文：开始、规则、时间分配、命令、重做
  INTERVIEWER.md       中文：开场、澄清问题标准答案（英文回答）、每关的坑/提示/追问、评分表
  REVIEW_TEMPLATE.md   中文复盘表
  SCOPE.json           来源 hash、每关考点、陷阱、澄清问题（键同样板）
  conftest.py          和样板完全相同（--solution、--all-parts 两个练习开关）
  pytest.ini           和样板完全相同
  <包名>/              题目代码：能用的部分 + 预埋缺陷 + 待实现的函数
  tests/test_parts.py  5 个测试，每个带 skip 锁、docstring、英文断言消息
  solution/<包名>/     参考实现
  solution/EXPLANATION.md  中文讲解，结尾写“这套题证明了什么，没证明什么”
  solution/traps.json  陷阱清单，供 check_traps.py 验证
  _starter/            <包名>/ 和 tests/ 的原始副本，用于重做
  verification.txt     check_traps.py --write 生成
```

包名在全课程唯一，用这一课的领域词（如 cliptag）。

## 代码规则

- Python 3.10+，只用标准库和 pytest。不联网，不用 numpy，结果确定（`random.Random(seed)`）。
- 题目代码要像真实代码：docstring 写的是正确行为，缺陷是代码和 docstring 不一致；注释里不能暗示 bug 在哪。待实现的函数保留签名和 docstring，函数体是 `raise NotImplementedError`。
- Part 1 至少有一处错误在离根因一两层调用之外报出来。
- 计时断言在本机实测：慢版本至少是限值的 8 倍，修好的版本不超过限值的 1/8；慢版本单次不超过 3 秒左右，不能让测试卡住。
- 防过度修复的断言：针对最常见的“为了过测试或提速而改坏”的写法。
- 测试直接调用包里的函数。异步用 `asyncio.run`，不用 pytest-asyncio。参考答案跑完全部 5 关不超过 5 秒。
- 断言消息像样板那样是简短的英文提示，指出要求，不说怎么修。

## traps.json 与验证

格式见样板的 [solution/traps.json](../../phases/06-speech-and-audio/03-audio-classification/exam/solution/traps.json)：

- `layers`：Part 1 从原始 starter 开始，一次修一个缺陷，每一步写明下一个应该出现的失败（断言消息或异常名的子串），最后一步是 `PASSED`。
- `wrong_fixes`：在参考答案上改出常见的错误写法，每个都必须被指定的测试抓住，`expect` 是失败输出里的子串。Part 1 至少 1 个过度修复，Part 2–5 每关至少 3 个。
- `expect` 不要依赖随 Python 版本变化的报错措辞（比如 struct 的越界消息），尽量用断言消息。
- 容差和边界要拿最省事的错误写法去试，不只试自己埋的那一个。例如 1 LSB 的容差会放过 `int()` 截断。

```bash
python3 scripts/exam_curriculum/check_traps.py <课>/exam --python <带 pytest 的 python>
python3 scripts/exam_curriculum/check_traps.py <课>/exam --python <带 pytest 的 python> --write
```

检查器在临时副本上运行，不在题目目录里执行代码。全部通过后用 `--write` 生成 verification.txt。不要直接在 `exam/` 里跑 pytest；目录里不能留下 `__pycache__` 或 `.pytest_cache`。

## 文档语气

中文文档写当前状态，不写修改记录或版本说明。句子直接、具体，和样板一致。
