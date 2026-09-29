# 参与贡献

感谢你愿意改进电商运营数据分析 Agent。

## 本地准备

Python 3.10–3.12 均可。建议使用虚拟环境，并通过项目依赖文件安装依赖：

```bash
python -m venv .venv
python -m pip install -r requirements.txt
```

## 提交改动前

- 对指标口径、字段映射或分析规则的改动，请同步更新 README 中对应说明。
- 新增计算逻辑时，请为关键行为补充单元测试，并覆盖缺失字段或异常输入。
- 不要提交店铺导出的真实数据、凭证、`.env` 文件或生成的 `demo_output/`。
- 保持分析结论可追溯；没有数据支持的原因应标记为待验证线索。

运行测试：

```bash
python -m unittest discover -s tests -v
```

## Pull request

请在 PR 描述中说明问题背景、改动内容、验证方式，以及对指标口径或兼容性的影响。涉及界面改动时，附上截图或简短录屏。
