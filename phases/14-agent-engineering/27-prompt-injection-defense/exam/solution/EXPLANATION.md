# 参考答案讲解：PVEGate（14/27）

计时结束后再看。参考实现在同目录的 `pvegate/` 里，`python3 -m pytest --solution --all-parts` 应该显示 5 passed。

## Part 1 修 PVE 会话

**现象**：解锁后第一个失败是第三次调用。一个干净的 `search("agent frameworks")` 被拒了，断言里的实际观察是 `that action was refused; try a different approach. (tool_output content contains injection marker 'ignore all instructions')`。

**顺着往上找**：哪条 tool_output 里有 'ignore all instructions'？history 里只有一条工具输出可能带它，就是第二步被拒时 `Session.step` 写进去的观察。原代码把拒绝理由拼在 REFUSAL 后面，理由又原样引用了注入标记，于是这条观察本身成了“带注入的工具输出”，之后每一步都被拦。课里写的是模型只被告知 "that action was refused; try a different approach."，docstring 也写了理由只进 audit。这一关想练的是：报错的位置在下一步，根因在上一步留下的数据里。

**依次修四处**：

1. 拒绝时观察只写 REFUSAL，理由留在 `audit`。
2. `normalize` 按 docstring 做：NFKC，去掉不可见字符，casefold，最后 strip。NFKC 把全角字母和全角冒号还原成 ASCII，strip 让前导空格挡不住 `startswith("do ")`。
3. `_drop_invisible` 改成一遍过滤：`"".join(ch for ch in text if ch not in INVISIBLE)`。原来的写法每删一个字符就把剩下的字符串整个复制一次，页面越长、零宽字符越多越慢。攻击者完全可以往页面里塞几万个零宽字符，让验证器自己变成瓶颈。本机上原写法 1.1–2.5 秒，一遍过滤 3–10 毫秒；`str.translate` 或 `re.sub` 也都在限值以内。
4. `assess` 在三项检查都通过之后，对 `sensitive_tools` 里的工具返回 "confirm"。`Session.step` 已经会处理 confirm：问人，人同意才执行，不同意就当作拒绝。

**护栏**：

- 修第 1 处时，最省事的写法是扫描 history 时跳过 tool_output。这会让真正带注入的工具输出（课里的 case 3）也溜过去，测试用一个返回注入页面的 fetch 专门查这个。反过来，也不能把用户消息一起扫：测试里的用户消息以 "Do a quick search" 开头，形状像指令，但只有用户的直接指令才算授权。
- 理由不进观察，但要进 audit，而且要写清是哪个标记。只把理由里的标记删掉，泄露是止住了，审计也就没用了。
- 规范化只用于检测。参数里有全角字母、中文和零宽字符的正常查询，必须原样交给工具。
- 顺序要照 docstring。先 strip 再删不可见字符，`"\u200b  execute ..."` 开头的零宽字符会挡住 strip，删完以后剩下两个前导空格。
- 为了提速只扫前 2 万个字符，会漏掉藏在长页面末尾的注入。
- 验证器整个跑完，才轮到人。把 confirm 提到扫 history 之前，注入页面之后的 send_message 就会去问人；验证器拒掉的调用不该再去打扰人，否则人很快会养成什么都点同意的习惯。
- confirm 由 `assess` 返回，不要在 `Session.step` 里另外判断敏感工具。别的调用方（比如 Part 4 的 `serve`）只看验证器的裁决，验证器自己不说 confirm，它们就不会问人。

## Part 2 带污点的记忆

参考实现只有一张表：`note_id` 是整数主键，`derived_from` 用 JSON 文本存成一个列表，`tainted` 存 0 和 1，读回来转成 bool。

- **原样存**：护栏用的是 `normalize` 之后的文本，但存的必须是原文。测试里的文本带 `\r\n`、首尾空白、全角字母和零宽字符，任何一种“顺手清理”都会让它读不回来。
- **污点传递**：`tainted = source != "user_message" or 任一父节点的 tainted`。看的是父节点存下来的污点，不是父节点的来源标签，所以污点能跨过任意多层摘要传下去，这就是课里说的持久记忆投毒和信息生态污染。每个父节点都要看，不能只看第一个：重开后写的 `later` 来自 `[5, 4]`，干净的在前，有污点的在后。
- **先检查再写**：来源不合法、像指令、父 id 不存在，都要在写入之前发现。参考实现在一个 `with self._db:` 事务里先查父节点再 INSERT，任何一步抛异常都不会留下记录。查父节点用循环，每个都读一遍；写成 `any(self.get(p).tainted for p in parents)` 的话，`any` 遇到第一个有污点的父节点就停，后面不存在的 id 查不出来。
- **父节点的顺序**：JSON 列表天然保序，`(3, 1)` 读回来还是 `(3, 1)`。如果用父子关系表存，就要多存一列位置。
- **recall 带上污点**：读回上下文的 Content 用存下来的 `tainted`，不能交给 Content 按来源去推断，否则用户来源的被污染摘要就变成干净的了。

## Part 3 参数来源检查

`tainted_args` 先把 history 分成两组，把每段内容 casefold 之后的所有 `min_run` 字符窗口放进集合：有污点的进 `untrusted`，没有的进 `trusted`。可疑窗口是 `untrusted - trusted`。然后对每个参数，递归取出里面所有的字符串，只要有一个窗口落在可疑集合里，这个参数就有污点。参数一侧的窗口用同一个 `_windows` 取，所以两边都 casefold 过。

```python
def _windows(text, n):
    folded = text.casefold()
    return {folded[i : i + n] for i in range(len(folded) - n + 1)}
```

- 减去 `trusted`，是因为用户自己写过的地址，网页里再出现一次，并不会变成攻击者的。减法按窗口做，不按整串：第一条断言的参数是 `Bob <bob@example.com>`，整串不在用户消息里，但它每个出现在网页上的窗口也都出现在用户消息里，所以不算污点。
- 分组看 `content.tainted`，不看来源标签。用户来源但有污点的记忆在 Part 2 里已经出现过。
- `range(len - n + 1)` 包含最后一个窗口；长度正好是 n 的字符串只有一个窗口。
- 字符串比 `min_run` 短时一个窗口都没有，自然不会被判成污点。
- 结果按参数在 dict 里的顺序给出，不排序。

`ProvenanceCheck.assess` 的顺序是：白名单，intent 能不能用这个工具（未知 intent 一个工具都不能用），敏感工具的参数有没有污点，敏感工具要人确认，其余放行。污点只对敏感工具有约束力，这是为了让正常流量上的拒绝率接近零（Exercise 5）。调用 `tainted_args` 时传的是检查自己的 `min_run`，不能靠默认值：测试里有一个 `min_run=24` 的检查，20 个字符的地址装不下一个窗口，它只能交给人确认。

测试最后一段把 Part 2 接了进来：页面写进记忆，用户来源的摘要从页面派生，下一次会话只读回摘要，发往攻击者地址的 send_message 仍然被拦。

## Part 4 单请求 PVE 与 JSON-RPC

`serve` 是给定的传输循环：逐行调用同步的 `handle_line`，返回回复字符串时立即输出，返回 None 时继续下一行。候选人的任务在单请求处理，不需要实现 async generator、任务队列或取消清理。

`handle_line` 先跳过空行、解析请求并检查 method / params。对合法工具调用，按这一刻的原 history 调 `validate`；confirm 只问这次调用，人同意才转为 allow。只有 allow 分支运行工具，并在返回前把结果作为 `Content(result, "tool_output")` 追加到原 history。最后用是否有 id 成员决定返回回复还是 None。

- 这就是课里 "All guardrails at the end" 的反面：第一个调用抓回注入页面，下一调用验证时已经看得到它。只给验证器初始用户消息，会把新抓回的证据藏起来；把输出改标为 `user_message`，又把不可信内容升成了授权。
- 只有真实工具输出进验证历史，空字符串也一样。Part 1 的 `Session` 把 REFUSAL 当作模型观察；这里模型已从错误回复知道拒绝，REFUSAL 不再作为工具证据加入 history。
- 通知仍必须验证和执行，只是没有 reply。fetch 通知更新后续 history；被拒或未知方法的通知也不回复。参考实现所有正常请求分支共用最后一个回复门，错误路径不提前绕过它。
- id 为 0 也要回复，id 原类型回传。params 可以省略，按空对象调用。未知方法与非对象 params 分别是 -32601 / -32602，不调用验证器；解析失败和非请求对象按 docstring 的标准错误回 id null。
- refuse 或 human-no 不执行；human-yes 允许这次调用，普通 allow 不向人提问。拒绝只回 `{"code": REFUSED, "message": REFUSAL}`，不把内部 reason 加到 error.data。
- 每条回复都有末尾 newline，外层不预读下一行。原测试也检查这些给定传输和编码 helper 的边界。

## Part 5 嵌套内容扫描

递归 `visit(node, path, inherited)`：

- 自己的来源缺省时用父节点的；有效来源是 `max(inherited, own, key=SOURCES.index)`，也就是两者里更不可信的那个。子节点只能比父节点更不可信，不能更可信。
- `len(path) > max_depth` 时记一条 TOO_DEEP，然后返回，不看里面的内容：它自己的 text 不读，parts 也不进。深度上限顺便挡住了自己包含自己的结构和故意做得很深的嵌套。
- 有效来源不是 user_message 时，对自己的 text 调用 `looks_like_directive`，有命中就记下路径、有效来源和标记。根节点也一样，来源不是 user_message 的根，它自己的 text 也要查。
- 然后按顺序访问 parts。递归的先序遍历就是文档顺序；改成队列会变成按层输出，FORWARD 里第三个顶层部分的 "Override:" 就会排到最前面。
- 不记已访问节点，同一个附件出现在两个位置就报告两次，各自带着自己那条路径的有效来源。

## 这套题证明了什么，没证明什么

通过了说明你能在 PVE 这种安全组件里顺着数据流调试，知道规范化只用于检测，能设计带来源和污点的存储，能实现基于来源的参数检查，能实现接入 JSON-RPC 流的同步单请求 PVE 处理，并能处理嵌套内容的信任传递。它不证明这套防御挡得住真实的提示注入：标记列表是黑名单，换个说法就能绕过；真正的验证器通常是一个模型，它的误报率和漏报率需要在真实流量上量出来。课里提到的允许列表导航、Gemini 2.5 Computer Use 式的逐步安全服务、外部内容存储，这套题都没有涉及。
