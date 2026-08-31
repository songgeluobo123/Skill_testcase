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
- 🎯 **优先级模型**：P0–P3 四级统一口径（无 P4），P0 一票否决；占比阈值可在检查点①按项目调整（详见下文「优先级模型」）
- 🛡️ **质量预审闸门**：覆盖率 / 方法关联 / 无编造 / 无重复 / 优先级占比，不达标不出库
- 🧠 **记忆机制**：记录历史产品约束，跨会话复用
- 📤 **多格式输出**：Excel（10 列）、XMind、Markdown 测试报告 / 测试点
- 📊 **质量评分**：覆盖 / 准确 / 可执行 / 优先级 4 维评分，每项均需达 90 分，任一不足自动回退

### 优先级模型（P0–P3 四级，统一口径）

本技能统一采用 **P0–P3** 四级优先级（**不再使用 P1–P4 体系，无 P4**）；用例 `priority` 字段仅可取 `P0` / `P1` / `P2` / `P3`，不得出现 P4 或其它分级。定级依据（五维评分 D1–D5 + R1–R7 硬规则 + 分级 SOP）以 `references/priority_p0_p3.md` 为**唯一权威来源**，此处仅列口径总览。

| 级别 | 范围 | 执行要求 | 占比建议 |
|---|---|---|---|
| **P0** 🔴 | 可行性/概念性测试：横屏主流程功能、竖屏移植横屏等价可用性、各端联调（一票否决） | 每次构建必跑，100% 通过方可发布 | 10%~15% |
| **P1** 🟠 | 主流程必测：主流程拆解功能（依据横屏 UI 流程图）、等价类含异常场景、横屏布局适配、AI 数据准确性、设备监控灵敏度、数据安全 | 每轮主测试（SIT / 回归主集）必覆盖 | 25%~35% |
| **P2** 🔵 | 显示完整性：横屏 UI 显示完整、不影响主流程的基本功能（控件不遮挡不溢出） | 常规迭代覆盖，回归可选 | 35%~45% |
| **P3** ⚪ | 美观与兼容：UI 显示正确与布局美观、旋转后布局、横屏响应式、Android/iOS 版本兼容、认证标准性能 | 全量或按需覆盖，不计入发布门禁 | 10%~20% |

**执行顺序（按优先级递增覆盖）**：冒烟 = P0 → 主测试 SIT = P0+P1 → 回归 = P0+P1+抽样P2 → 全量 / 探索 = P0~P3。

> 占比阈值由 `scripts/prescreen.py` 强制校验（P0 默认 10%~15%、P2 默认 35%~45%），任一占比不在区间即回退重排优先级；安全攸关项目可在**检查点①**上调 P0 占比（如 40%~60%，见 `references/quality_prescreen.md`），记忆机制会跨会话复用该偏好。

## 三、目录结构与分层

```
testcase-generator/
├── SKILL.md                 # 技能主指令（6 步工作流 + 资源索引，单一控制面）
├── README.md                # 中文总览（本文件）
├── README.en.md             # 英文总览
├── LICENSE                  # MIT
├── references/              # 方法论与规范（14 篇，按下列分层组织，物理上同目录）
│   ├── case_design.md        # ★用例编写规范唯一权威：设计原则 + 四字段规范 + 类型转化 + 优先级口径 + 粒度
│   ├── naming_rules.md       # 命名 7 条强制红线
│   ├── output_format.md      # 10 列 Excel 容器定义 + JSON 字段映射
│   ├── xmind_output.md       # XMind 输出格式规范
│   ├── function_points.md    # 功能点定义与分解（如何设计）
│   ├── test_methods.md       # 6 种黑盒方法详解 + 有序叠加
│   ├── testpoint_checklist.md# 测试点 5 维度 + 常见功能覆盖清单
│   ├── multimodal.md         # 多模态读图（图→用例）
│   ├── priority_p0_p3.md     # P0–P3 分级策略（优先级口径）
│   ├── data_rules.md         # 数据-规则映射库（测试数据校验）
│   ├── quality_standards.md  # 4 大质量标准 + 0–100 评分 rubric
│   ├── quality_prescreen.md  # 质量预审 6 项闸门与阈值
│   ├── workflow.md           # 质量保障机制总览（预审/评分/记忆三道闸门 + 技术加速器）
│   └── memory_mechanism.md   # 记忆机制
└── scripts/                 # 可执行脚本（9 个，Python 3.13）
    ├── extract_requirements.py  # Step1 抽取需求规则清单
    ├── map_coverage.py          # 用例↔需求规则覆盖映射
    ├── prescreen.py             # 质量预审闸门
    ├── score_testcases.py       # 质量评分
    ├── to_excel.py              # 导出 10 列 Excel（`--emit-template` 出空白模板）
    ├── to_xmind.py              # 导出 XMind
    ├── read_xmind.py            # 解析 XMind 输入
    ├── read_ui_image.py         # 多模态读 UI 截图
    └── memory_io.py             # 记忆读写
```

### 分层职责与边界

| 层 | 文件 | 职责边界 |
|---|---|---|
| **控制面** | `SKILL.md` | 6 步工作流编排 + 资源索引；不存放具体规范细节 |
| **B. 用例编写规范** | `case_design.md`（权威）、`naming_rules.md`、`output_format.md`、`xmind_output.md` | 定义"用例怎么写"：字段写法、命名红线、Excel/XMind 容器 |
| **A. 方法论** | `function_points.md`、`test_methods.md`、`testpoint_checklist.md`、`multimodal.md` | 定义"如何设计"（拆解 / 方法 / 测试点 / 读图） |
| **C. 优先级** | `priority_p0_p3.md` | P0–P3 分级策略（优先级唯一权威来源） |
| **D. 数据规则** | `data_rules.md` | 仅测试数据校验映射库 |
| **E. 质量保障** | `quality_standards.md`、`quality_prescreen.md`、`workflow.md`、`memory_mechanism.md` | 定义"怎么验"：标准/评分、预审闸门、机制总览、记忆 |

> **边界原则：每条规则只在一处定义（单一真相源）。** `case_design.md` 为用例编写规范唯一权威；优先级模型只存于 `priority_p0_p3.md`(P0–P3，唯一权威)；评分 rubric 只在 `quality_standards.md`；数据校验只在 `data_rules.md`。交叉处一律用"见 xxx"引用，不复制规则。

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
| 4 | 优先级 | `priority`，P0–P3 |
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

# 6. 质量评分（每项维度需 ≥90，任一不足自动回退）
python scripts/score_testcases.py ./out/test_cases_final.json
```

## 七、依赖

- Python ≥ 3.8（推荐 3.13）
- `Pillow`（多模态读图）、`openpyxl`（Excel 导出）可选，按用到的脚本安装

## 八、许可证

默认 MIT。如需其他许可证，请在仓库根目录补充 `LICENSE` 文件。
