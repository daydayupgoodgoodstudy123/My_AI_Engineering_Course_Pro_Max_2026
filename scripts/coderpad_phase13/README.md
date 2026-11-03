# 试点维护说明

`specs/*.py` 是题目、合同、测试和参考实现的源文件；`build.py` 生成每课的 `coderpad/`。
Python 3.10+，仅标准库，不需要安装依赖。题目是基于本地课程的原创、简化训练合同。

```bash
# 从本目录运行；已有文件一律不覆盖，发现差异会退出并列出路径
python3 build.py

# 对照源文件检查生成材料；学员修改过 starter/main.py 后出现差异是正常的
python3 build.py --check

# 在临时目录重建、验证，避免触碰学员的 starter
python3 verify.py
```

需要更新材料时，先修改对应 spec，在新目录生成和验证，再审阅差异。
`--output /tmp/phase13-coderpad-preview` 可以指定一个新的输出目录。
不要覆盖已经做过的 `starter/`；重做练习也请先另存上一轮。
