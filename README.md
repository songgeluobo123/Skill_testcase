# testcase-generator · 测试用例生成技能

> WorkBuddy 技能：把 PRD / UI 设计图 / XMind 需求，结构化地转成可直接执行的测试用例（10 列 Excel 主产物）。

English version: [README.en.md](README.en.md)

---

## 一、这个技能解决什么

人工写用例常遇三难：**需求理解不全、测试方法用得散、输出格式乱**。本技能用「6 步工作流 + 6 种黑盒方法 + 质量预审闸门」把这三难拆开解决：

- **让 AI 读懂需求**：支持 PRD 文本、UI 设计图（多模态读图）、XMind 需求文件三种输入，自动抽取「需求规则清单」。
- **让 AI用对方法**：等价类划分、边界值分析、场景法、状态迁移法、判定表法、正交分析法，按场景有序叠加。
- **让输出统一**：固定 10 列 Excel 模板 + 命名/格式负向约束，保证用例可被直接导入执行。

## 二、能力特性

- 📥 **多源输入**：PRD（`.md`/`.txt`）、UI 截图（多模态读图）、XMind（`.xmind` 解析）
- 🧩 **功能点分解**：按页面/模块拆原子功能点，逐点产出测试点（5 维度）
- 🎯 **优先级模型**：P1–P4（安全攸关场景自动上调 P1 占比）
- 🛡️ **质量预审闸门**：覆盖率 / 方法关联 / 无编造 / 无重复 / 优先级占比，不达标不出库
- 🧠 **记忆机制**：记录历史产品约束，跨会话复用
- 📤 **多格式输出**：Excel（9→10 列）、XMind、Markdown 测试报告 / 测试点
- 📊 **质量评分**：覆盖 / 准确 / 可执行 / 优先级 4 维评分，低于阈值自动回退

## 三、目录结构

```
testcase-generator/
├── SKILL.md                 # 技能主指令（全中文）
├── README.md                # 本文件
├── references/              # 方法论与规范（12 篇）
│   ├── workflow.md          # 6 步工作流
│   ├── case_design.md       # 10 条用例设计原则 + 命名/格式规范
│   ├── output_format.md     # 10 列 Excel 模板规范
│   ├── test_methods.md      # 6 种黑盒方法详解
│   ├── data_rules.md        # 测试数据校验规则 + 优先级模型
│   ├── function_points.md   # 功能点分解方法
│   ├── testpoint_checklist.md # 测试点 5 维度清单
│   ├── quality_standards.md # 4 大质量标准
│   ├── quality_prescreen.md # 质量预审 6 项闸门与阈值
│   ├── memory_mechanism.md  # 记忆机制说明
│   ├── multimodal.md        # 多模态读图说明
│   └── xmind_output.md      # XMind 输出格式
└── scripts/                 # 可执行脚本（9 个，Python 3.13）
    ├── extract_requirements.py  # Stage1 抽取需求规则清单
    ├── map_coverage.py          # 用例↔需求规则覆盖映射
    ├── prescreen.py             # 质量预审闸门
    ├── score_testcases.py       # 质量评分
    ├── to_excel.py              # 导出 10 列 Excel（`--emit-template` 出空白模板）
    ├── to_xmind.py              # 导出 XMind
    ├── read_xmind.py            # 解析 XMind 输入
    ├── read_ui_image.py         # 多模态读 UI 截图
    └── memory_io.py             # 记忆读写
```

## 四、6 步工作流

| 步骤 | 名称 | 产出 |
|---|---|---|
| ① | 需求深度分析 | `requirements.json` / `requirement_rules.json` / `requirements.md` |
| ② | 功能点分解 | 原子化功能点清单（页面/模块维度） |
| ③ | 测试点分析 | 测试点 Markdown（5 维度覆盖） |
| ④ | 模板确认 | 10 列 Excel 模板 + 命名/优先级口径 |
| ⑤ | 用例设计 | 结构化用例 JSON（含 `coverage_rule` / `design_method` / `priority`） |
| ⑥ | 用例输出 | 10 列 Excel + XMind + 测试报告 + 质量评分 |

## 五、Excel 10 列模板

| # | 列名 | 说明 |
|---|---|---|
| 1 | 用例编号 | 自动生成 `TC-001`…（用例 JSON 含 `id` 时优先用 `id`） |
| 2 | 测试模块 | `module` |
| 3 | 用例名称 | `name` |
| 4 | 优先级 | `priority`，P1–P4 |
| 5 | 测试类型 | `test_type`（功能/异常/边界/接口/兼容/性能…） |
| 6 | 前置条件 | `precondition` |
| 7 | 测试步骤 | `steps` |
| 8 | 预期结果 | `expected` |
| 9 | 适用阶段 | `stage`（质量追溯列） |
| 10 | 设计方法 | `design_method`（质量追溯列） |

## 六、快速开始（本地跑管线）

```bash
# 0. 准备 venv（含 Pillow、openpyxl）
python -m venv venv && venv/Scripts/pip install Pillow openpyxl

# 1. 抽取需求规则清单
python scripts/extract_requirements.py path/to/PRD.md -o ./out

# 2. 设计用例（人工/AI 产出 test_cases.json，含 coverage_rule 等字段）

# 3. 覆盖映射
python scripts/map_coverage.py ./out/test_cases.json ./out/requirements.json -o ./out/test_cases_mapped.json

# 4. 质量预审闸门（不达标会列出缺口）
python scripts/prescreen.py ./out/test_cases_mapped.json \
    --requirement-rules ./out/requirement_rules.json --coverage-min 0.95

# 5. 导出 10 列 Excel
python scripts/to_excel.py ./out/test_cases_final.json -o 测试用例.xlsx

# 6. 质量评分（<70 自动回退）
python scripts/score_testcases.py ./out/test_cases_final.json
```

## 七、依赖

- Python ≥ 3.8（推荐 3.13）
- `Pillow`（多模态读图）、`openpyxl`（Excel 导出）可选，按用到的脚本安装

## 八、许可证

默认 MIT。如需其他许可证，请在仓库根目录补充 `LICENSE` 文件。
