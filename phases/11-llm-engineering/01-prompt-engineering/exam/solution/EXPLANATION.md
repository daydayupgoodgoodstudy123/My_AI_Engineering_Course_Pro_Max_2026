# 参考答案讲解：PromptBench（11/01）

计时结束后再看。参考实现在同目录的 `promptbench/`。参考测试只使用本地数据。

## Part 1 修 Prompt 构建

`PromptService.preview` 返回的 prompt 把 task 填进 role。问题不在外层断言，也不在模板文字，而在 `bind_variables` 把声明名与输入 dict 的 value 顺序 zip。具名变量必须按同一个 key 取值；多余输入字段没有占位符职责。

接着修多轮历史：每个 role/content 都要保留，包括 assistant 和空串。system override 则只在 None 时用默认值；空串是显式选择。

最后修性能。慢版每个变量都生成一份完整 fragment 列表，字段数和 fragment 数相乘。参考版只走一次已正确解析的 fragments，把 literal 和当前 field 的字符串值 append，最后 join。4,500 字段的本机三次慢版为 0.68–0.72 秒，参考版为 0.0005–0.0008 秒；限值 0.07 秒。这里的测量是小模板引擎的本地 CPU 行为，不是模型响应时间。

变量值不再参与解析，所以 `{other}` 仍是字面值。Formatter 负责模板本身的 `{{`、`}}` 转义，不靠删花括号或再次 format 修复。

## Part 2 模板版本库

正文编码为 UTF-8，SHA-256 只对正文 bytes 取值，存到 `objects/<digest>`。清单按加入顺序存 name、version、digest 和独立 metadata。两个名字指向相同正文时共用对象，温度、description、system 选择仍各自保存。

正文按 bytes 读写，避免 CRLF 被通用换行转换。清单使用 JSON，可以保留 Python binary64 的 round-trip 值和 -0.0；读回 tuple 类型的变量名并保持声明顺序，不能排序。读取对象时重新核对 hash，以免损坏的正文仍被当成原版本。

## Part 3 Rubric 与比较

四个分量分别是 length_compliant、keyword_coverage、no_violations、format_valid。先独立算，再只对启用分量取平均；word_count 是诊断值，不能因为它恰好为 1 就当成一个评分分量。

required 和 forbidden 按大小写不敏感子串匹配，不要求完整单词。空 required 列表覆盖率为 1。JSON 检查用 `json.loads`，完整 scalar 也有效。格式规则沿源 Python：bullet 用非空行中至少一半以 `-`、`*` 或 `1` 开头；编号列表需要两条行首数字加点的匹配。

模型分数降序排列，Python 稳定排序保留平分模型的输入顺序。保留 token 和 API latency 供比较，但它们不参与 composite。

## Part 4 CSV 模型评分投影

score_rows 只接收一个完整 case，先使用该 case 的 criteria 得到 comparison，再按 comparison 的输入 model 顺序构造各行。原始 response 来自相同 model 的 replay，composite、tokens 和 latency 来自该 model 的比较结果。不能取 ranked 改变回放顺序，也不能把所有模型 token 相加后写入每一行；latency 保持 API 原值的毫秒单位。零 token、空 response 都仍有一条完整记录。

_row 的 csv.writer/CRLF 编码和 stream_scores 的完整异步循环正确给定。驱动先发布 header，随后只拉一个 case，将同步 callback 返回的全部行发布后才拉下一 case，关闭时负责 aclose。候选不写消费、发布或关闭循环。引用、换行与关闭断言验证完整管线的集成边界；模型行只按当前 case 缓存，没有固定内存上界的承诺。

## Part 5 报告层级

按 pattern、model 分组，保留 case 顺序，用 `(pattern, model, case_id)` 拦重复。四项 criterion 各自收集实际存在的分数：不存在就 count=0、mean=None，存在的零分必须参与。最弱项只比较有观察的项，平分保持 CRITERIA 顺序。

本课的自然结构是嵌套测试报告，所以这关做报告归集与覆盖率解释，没有加一个来源中不存在的递归 prompt 执行器。

## 这套题证明了什么，没证明什么

通过说明你能调试具名模板与多轮构建，保存可核对的模板版本，实现本课 rubric、CSV 异步输出和嵌套报告归集。它没有调用真实 LLM，没有证明 prompt 改动能提升真实任务质量，也没有测 provider 延迟、模型能力或线上效果。60 分钟的难度与时间分配尚未经过真人校准。
