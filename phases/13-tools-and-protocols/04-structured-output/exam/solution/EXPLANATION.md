# 参考答案讲解：InvoiceKit（13/04）

计时结束后再看。参考实现在同目录的 `invoicekit/` 里，`python3 -m pytest --solution --all-parts` 应该显示 5 passed。

## Part 1 修校验器和回复分类

**现象**：解锁后的第一个错误是 `lookup` 里的 `TypeError: list indices must be integers or slices, not str`，而 `lookup` 本身没有 bug。

**顺着往上找**：`feedback` 为每个错误调用 `lookup(payload, error.loc)`，取出模型在那个位置写了什么。传进来的 loc 是 `("line_items", "0", "discount")`，下标是字符串。`ValidationError` 的 docstring 写得很清楚：loc 和 Pydantic 的一样带类型，成员名是 str，数组下标是 int。问题出在 `_at`：它对所有的 step 都做了 `str(step)`。路径打印成 `$.line_items.0.sku` 只是表面，真正坏掉的是位置的类型。

**依次修四处**：

1. `_at` 原样保留 step：`return loc + (step,)`。
2. 数组分支不在第一个出错的元素处 return，每个元素的错误都收进来。课里说校验器返回的错误列表就是要放进重试提示的东西，一次报全，模型才能一次改完。
3. `process_model_output` 先判断 `__REFUSAL__` 前缀，再解析。原来的顺序里，拒答文本先被 `json.loads` 拒掉，变成 parse error，后面那个判断永远走不到。到了 Part 3，parse error 会被拿去重试，而拒答不该重试。
4. enum 不再逐个比较。参考实现第一次见到某个 enum 列表时，把每个成员变成一个可哈希的键，存成 frozenset，以后每次查找都是 O(1)：

```python
def _json_key(value):
    if isinstance(value, bool):
        return ("boolean", value)
    if _is_number(value):
        return ("number", value)
    if isinstance(value, list):
        return ("array", tuple(_json_key(v) for v in value))
    if isinstance(value, dict):
        return ("object", frozenset((k, _json_key(v)) for k, v in value.items()))
    return (type(value).__name__, value)
```

缓存按 `id(options)` 存，每一项同时持有列表本身，所以这个 id 不会被别的列表复用。5,000 个 SKU、3,000 行，原来本机约 1.1 秒，改完约 5 毫秒。

**两个护栏**：

- 最顺手的写法是 `value in set(schema["enum"])`。可是 enum 里可以有对象（这里的付款条件），对象不能哈希；就算只放标量，`False == 0`、`True == 1` 在 set 里也会撞在一起，`gst_rate: false` 会被当成 0 放过去。课里原来的 `value not in enum` 也有同样的问题，只是在这里够快，能过计时。键要把布尔值和数字分开，又要让 5.0 和 5 相等（JSON 按数值比较），对象不看键的顺序。`repr` 和 `json.dumps` 当键都做不到。
- 缓存不能放进 schema 字典。schema 是共享的常量，同一个字典还要原样发给模型提供方。

## Part 2 结果快照

一个 JSON 文件，里面是按存入顺序排列的结果。每条结果存 doc_id、kind、payload、errors（loc 和 message）和原始回复：

```python
def _encode(value):
    if isinstance(value, Decimal):
        return {"$decimal": str(value)}
    if isinstance(value, dict):
        encoded = {key: _encode(v) for key, v in value.items()}
        if len(encoded) == 1 and next(iter(encoded)) in ("$decimal", "$object"):
            return {"$object": [[key, v] for key, v in encoded.items()]}
        return encoded
    ...

def _decode(obj):
    if obj.keys() == {"$decimal"}:
        return Decimal(obj["$decimal"])
    if obj.keys() == {"$object"}:
        return dict(obj["$object"])
    return obj
```

容易漏的几点：

- **Decimal 原样**：`str(Decimal("120.00"))` 是 `"120.00"`，`Decimal("120.00")` 再读回来，每一位都在。`Decimal("120.0") == Decimal("120.00")` 是真的，所以只用 `==` 查不出丢了一位，测试另外用 `exact()` 比较类型和字符串形式。转成 float 再存，120.00 就成了 120.0；`normalize()` 会变成 `1.2E+2`。
- **为什么要打标记**：violation 的 payload 里有模型加了引号的 `"49.99"` 和 `"2"`。如果 Decimal 存成普通字符串，读回来就分不清哪个本来是数字、哪个本来就是字符串。另一种可行的写法是把 Decimal 写成 JSON 数字（`outcome.json_text` 就是这样写的），读的时候用 `parse_float=Decimal`；字符串还是字符串，数字的每一位也都保住了。参考实现选了字符串，是因为别的程序读这个文件时，JSON 数字常常会被解析成双精度浮点。
- **标记也会撞车**：payload 是模型写的任意 JSON，模型完全可能写出 `{"$decimal": "1"}`，只按标记解码的话，读回来就成了 `Decimal('1')`。参考实现把只有一个 `$decimal` 或 `$object` 键的对象改存成 `{"$object": [[键, 值]]}`。object_hook 是从里往外调用的，如果写成 `{"$object": {...}}`，里面那层会先被当成 Decimal 解开，所以这里用键值对列表，object_hook 不会碰列表。测试不查这一点，面试里能主动说出来就是加分；把 Decimal 写成 JSON 数字的写法本来就没有这个歧义。
- **存结论，不存推导**：只存原始回复、读的时候重新跑 `process_model_output`，看起来更省事，但 po-0452 是 Part 3 的总额检查判出来的 violation，重新解析会变成 ok。校验器以后会改，已经做出的判断不能跟着变。
- **顺序和替换**：文档 id 故意不是按字母顺序给的。Python 的 dict 保留插入顺序，同一个键再赋值时位置不变，正好是“替换后留在原位”。
- **原子写**：

```python
fd, tmp = tempfile.mkstemp(dir=directory, prefix=".results-", suffix=".tmp")
try:
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, self.path)
except BaseException:
    os.unlink(tmp)
    raise
```

临时文件和快照在同一个目录，`os.replace` 才是一次原子的改名；放进系统临时目录的话，那里常常是另一个文件系统，`os.replace` 会报 EXDEV。测试把 `os.replace` 和 `os.rename` 换成会抛错的函数，模拟保存到一半进程挂了：旧快照必须完好，临时文件要删掉，store 的状态也不能变；这个函数还记下了临时文件的路径，查它是不是在快照旁边。参考实现每次都从文件读，没有内存里的副本，失败的 put 自然什么都没改。

## Part 3 带重试的提取

```python
note = None
for attempt in range(1, max_retries + 2):
    result = process_model_output(generate(note), INVOICE_SCHEMA)
    if result.kind == "ok":
        errors = check_totals(result.payload)
        if errors:
            result = ParsedResult("violation", result.payload, errors, result.raw)
    if result.kind in ("ok", "refusal"):
        break
    note = feedback(result)
return Extraction(result, attempt)
```

- 这就是课里的 `generate -> parse -> validate -> if fail, inject error and retry, max 3x`。3 次重试加上第一次，最多 4 次尝试。
- 每次重试只带上一次的反馈。Part 1 修好以后，`feedback()` 里有每一个错误的路径和模型写的值，比如 `$.line_items[1].qty: expected integer, got str (value: "1")`。
- 拒答马上结束，不管前面有没有失败过。课里说 refusal 分支不重试，它是一个带类型的结果。
- "Here is your JSON:" 开头的回复就是 parse error。课里把 leaked prose 列为直接要 JSON 的失败之一；截出花括号之间的部分，模型的问题被藏起来了，存下来的也不是模型说的话。
- 总额规则 schema 表达不了，所以在 schema 通过以后再查。payload 里的金额是解析时就得到的 Decimal，`2 * Decimal("49.99") + Decimal("120.00")` 精确等于 `Decimal("219.98")`。用浮点会得到 219.98000000000002；`Decimal(49.99)` 带进来的是二进制展开；quiz Q10 的写法允许 0.01 的误差，这里要求精确，差一分钱就要报出来；四舍五入到分会把 0.375 当成 0.38；按字符串比较的话，220 和 220.00 又不相等了。容差改小也不对：0.3751 对 0.375 只差万分之一，也要报；`math.isclose` 是相对误差，2,500 万的发票差一分钱它也放过，测试用一张 2,500 万的发票查这一点。

## Part 4 约束解码

参考实现把 schema 摊平成一串片段：固定文字（`{"currency":`、`,"line":{"sku":` 这样的键和标点）、enum（每个成员的完整 JSON 字面量，带引号）、非负整数。状态是“第几个片段，这一段已经写了什么”。

```python
while not _complete(pieces, state) or _can_continue(pieces, state):
    for token in model(text):
        if token == EOS:
            if _complete(pieces, state):
                return
            continue
        after = _advance(pieces, state, token)
        if after is not None:
            break
    else:
        raise ValueError(f"no allowed token after {text!r}")
    state = after
    text += token
    yield token.encode("utf-8")
```

- `_advance` 逐个字符走。token 和 JSON 语法对不齐，`R","line":{"sku":"ABC-1` 一个 token 就跨过了 enum 的结尾、两段固定文字和下一个 enum 的开头。
- enum 用带引号的字面量来匹配。JSON 字符串在右引号处结束，所以 `"ABC-1"` 不是 `"ABC-12"` 的前缀，右引号一到就知道是哪个成员。把引号和内容分开处理，就会在 EU（只是 EUR 的前缀，不能闭合）和 ABC-1（已经完整，但还能接着写成 ABC-12）上出错。
- 字面量用 `json.dumps(member, ensure_ascii=False)` 生成。默认的 `ensure_ascii=True` 会把 ² 写成 `\u00b2`，模型给的 `²"}` 就被屏蔽了。
- 整数片段：`0` 后面不能再跟数字；有了至少一个数字以后，非数字的字符交给下一个片段。一个数字都没有就遇到非数字，要屏蔽：模型在 `"qty":` 后面给的 `,"unit":"m²"}}` 想把数量跳过去，放过它就会输出 `"qty":,`。
- 对象的右括号出来以后，什么都不能再跟，直接结束，不再调用模型。单独一个整数时，有数字以后 EOS 才合法。
- 没有合法候选就抛 ValueError。课里说约束解码的输出保证能解析、保证符合 schema，所以不能为了“总得输出点什么”硬选一个。
- 这是一个生成器，选中一个 token 就 yield，下游马上就能把这几个字节发出去。

## Part 5 判别式 oneOf

```python
if discriminator is None:
    matches = sum(1 for branch in branches if not validate(branch, value, loc))
    ...  # 恰好 1 个才算通过
if not isinstance(value, dict):
    return [ValidationError(loc, f"expected object, got {type(value).__name__}")]
tag = discriminator["propertyName"]
if tag not in value:
    return [ValidationError(_at(loc, tag), "missing required field")]
for branch in branches:
    if _in_enum(value[tag], branch["properties"][tag]["enum"]):
        return validate(branch, value, loc)
return [ValidationError(_at(loc, tag), f"value {value[tag]!r} not in enum")]
```

- kind 选定分支以后，只用这个分支校验，错误路径从当前元素的 loc 往下接，所以是 `$.line_items[3].parts[1].hours`。bundle 的 parts 又是一层判别式 oneOf，validate 的递归自然处理。
- 未知或缺失的 kind 报在 `.kind` 上，模型一看就知道该改哪里。
- 没有 discriminator 时，oneOf 要求恰好一个分支匹配。整数也是 number，所以 discount 为 1 时两个分支都匹配，这正是 oneOf 和 anyOf 的区别。一个都不匹配时只报一条，不把每个分支的错误都倒给模型。

## 这套题证明了什么，没证明什么

通过了说明你能在这个规模的代码里顺着类型化的错误位置调试、给 enum 建一个保持 JSON 等值语义的索引、把带 Decimal 的结果原子地存成 JSON 并原样读回、写出拒答不重试的重试循环和精确的总额检查、按 schema 一个字符一个字符地屏蔽 token，以及实现带 discriminator 的 oneOf。它没有调用真实的模型，也不涉及 OpenAI strict 模式、Anthropic tool use、Pydantic 和 Zod 的真实 API，约束解码也只覆盖了很小的 schema 子集，没有处理真实词表的规模和字节级 tokenizer。课后练习 3 到 5 需要另外动手做。
