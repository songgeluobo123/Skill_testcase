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
- 🚧 **分析闸门（两阶段）**：先出《测试分析报告》→ 确认后才生成；五条硬约束——禁止假设、业务规则咨询必做、术语一致、来源可追溯、多源融合显式标注（见 `references/analysis_gate.md`）
- 🧩 **功能点分解**：按页面/模块拆原子功能点，逐点产出测试点（5 维度）
- 🎯 **四类场景配额**：每个功能点 `1 正向 : ≥3 异常·边界` 且 **≥1 条权限校验**（未登录/无权限/跨角色越权），只测顺利路径直接判场景失衡
- 📊 **等价类/边界值矩阵（Step 3.5 强制）**：逐字段穷举等价类与边界点，**一行一项**并回指到具体用例；`matrix_lint.py` 拦「边界点 <3 / 未消费等价类 / 编造需求 / `[假设]` 超 30% / 列错位」。它是密度闸门的**唯一燃料**——没有矩阵，补出来的 6 条只是同一件事换说法
- 🎯 **优先级模型**：P0–P3 四级统一口径（无 P4）——P0 可行性/概念性测试、P1 主流程必测、P2 显示完整性、P3 美观与兼容；P0 一票否决；占比阈值可在检查点①按项目调整（详见下文「优先级模型」）
- 🛡️ **质量预审闸门（14 项）**：结构面 10 项（覆盖率 / 方法关联 / 无编造 / 无重复 / 优先级占比 / 预期可判定 / 标题规范与编号唯一 / 场景构成配额 / 孤儿用例）+ 密度面 4 项（**逐需求密度 / 方法一致性 / 需求级场景配额 / 范围性用例**）。注意**第 11 项默认关闭**（`--min-cases-per-rule 0`），需显式开启；第 12/13/14 项默认只告警。**Step 5 模板把四项一律硬写 `block`**——靠默认值跑出来的全绿是假绿
- 🔍 **覆盖率评审（逆向）**：拿已有用例库回审需求，输出**模块级**覆盖率 + 三类缺口（G1 缺失 / G2 场景失衡 / G3 名义覆盖）；支持 `.xlsx` 直读，专治"全局 95% 掩盖某模块 40%"（见 `references/coverage_audit.md`）
- 🧪 **强度闸门（默认 P0 阻断）**：需求层变异——假设需求被写错（阈值差一 / 边界方向写反 / 否定词去掉 / 动作漏做 / 文案改写），这条用例会不会变红？输出**零强度规则 / 零贡献用例**清单；**P0 规则 ≥90% 才放行**（P1–P3 只告警，`--mut-gate warn` 可切纯报告）。预审只保证结构，强度由 `scripts/mutation_audit.py` 兜底（见 `references/mutation_review.md`）
- 🔗 **双向需求追溯（RTM）**：需求→用例（查漏测）+ 用例→需求（查孤儿），区分「全覆盖 / 部分覆盖 / 未覆盖」，可写入用例 Excel 的**第二个 sheet「需求追溯」**（`to_excel.py --with-rtm requirements.json`）
- 🕳️ **缺陷反哺评审（逃逸驱动，默认不阻断）**：拿**真实缺陷**当外部地面真值，反算"这条缺陷发生时用例库为什么没红"——输出**逃逸缺陷清单**、**零覆盖模块**（库内 0 条用例却有事故）、**7 类断言缺口**（数值/逐字文案/结果态/唯一性/否定/边界/现象）与回归回填草案。口径收敛为 **「漏」可自动判、「拦」只给候选**（实测自动判「拦」人工一致率 0/5），因此不宣称拦截率、`--gate` 默认 `off`（见 `references/defect_loop.md`）
- 📐 **实证写法模式**：从真实优秀用例库（1278 条）反推的 10 个可复制做法——双前置列分离、动词白名单、预期断言化、同构组批量产出、非功能三件套等（见 `references/excellent_case_patterns.md`）
- 🧠 **记忆机制**：记录历史产品约束，跨会话复用
- 📤 **多格式输出**：Excel（10 列）、XMind、Markdown 测试报告 / 测试点
- 📊 **质量评分**：覆盖 / 准确 / 可执行 / 优先级 4 维评分，每项均需达 90 分，任一不足自动回退

### 优先级模型（P0–P3 四级，统一口径）

本技能统一采用 **P0–P3** 四级优先级（**不再使用 P1–P4 体系，无 P4**）；用例 `priority` 字段仅可取 `P0` / `P1` / `P2` / `P3`，不得出现 P4 或其它分级。定级依据（五维评分 D1–D5 + R1–R7 硬规则 + 分级 SOP）以 `references/priority_p0_p3.md` 为**唯一权威来源**，此处仅列口径总览。

| 级别 | 范围 | 执行要求 | 占比建议 |
|---|---|---|---|
| **P0** 🔴 | 可行性/概念性测试：横屏主流程功能、竖屏移植横屏等价可用性、各端联调（一票否决） | 每次构建必跑，100% 通过方可发布 | 10%~25% |
| **P1** 🟠 | 主流程必测：主流程拆解功能（依据横屏 UI 流程图）、等价类含异常场景、横屏布局适配、AI 数据准确性、设备监控灵敏度、数据安全 | 每轮主测试（SIT / 回归主集）必覆盖 | 25%~35% |
| **P2** 🔵 | 显示完整性：横屏 UI 显示完整、不影响主流程的基本功能（控件不遮挡不溢出） | 常规迭代覆盖，回归可选 | 25%~40% |
| **P3** ⚪ | 美观与兼容：UI 显示正确与布局美观、旋转后布局、横屏响应式、Android/iOS 版本兼容、认证标准性能 | 全量或按需覆盖，不计入发布门禁 | 10%~20% |

**执行顺序（按优先级递增覆盖）**：冒烟 = P0 → 主测试 SIT = P0+P1 → 回归 = P0+P1+抽样P2 → 全量 / 探索 = P0~P3。

> 占比阈值由 `scripts/prescreen.py` 强制校验（P0 默认 10%~25%、P2 默认 25%~40%），任一占比不在区间即回退重排优先级；安全攸关项目可在**检查点①**上调 P0 占比（如 40%~60%，见 `references/quality_prescreen.md`），记忆机制会跨会话复用该偏好。

## 三、目录结构与分层

```
testcase-generator/
├── SKILL.md                 # 技能主指令（6 步工作流 + 资源索引，单一控制面）
├── README.md                # 中文总览（本文件）
├── README.en.md             # 英文总览
├── LICENSE                  # MIT
├── references/              # 方法论与规范（20 篇，按下列分层组织，物理上同目录）
│   ├── analysis_gate.md      # ★分析闸门与硬约束（两阶段 + STOP & ASK + H1–H5）
│   ├── case_design.md        # ★用例编写规范唯一权威：设计原则 + 四字段规范 + 类型转化 + 优先级口径 + 粒度
│   ├── naming_rules.md       # 命名 7 条强制红线 + 用例编号规范（TC-{模块}-{序号}）
│   ├── output_format.md      # 10 列 Excel 容器定义 + JSON 字段映射
│   ├── xmind_output.md       # XMind 输出格式规范
│   ├── function_points.md    # 功能点定义与分解（如何设计）
│   ├── test_methods.md       # 6 种黑盒方法详解 + 有序叠加
│   ├── testpoint_checklist.md# 测试点 5 维度 + 四类场景配额 + 覆盖清单
│   ├── equivalence_matrix.md # ★等价类/边界值矩阵（Step 3.5 强制中间产物，一行一项 + lint 规则）
│   ├── multimodal.md         # 多模态读图（图→用例）
│   ├── excellent_case_patterns.md # ★优秀用例实证模式（10 做法 + 自检清单 + 反面清单）
│   ├── priority_p0_p3.md     # P0–P3 分级策略（优先级口径）
│   ├── data_rules.json       # 可执行的数据校验规则库模板（六种 type）
│   ├── data_rules.md         # 数据-规则映射库（测试数据校验）
│   ├── quality_standards.md  # 4 大质量标准 + 0–100 评分 rubric
│   ├── quality_prescreen.md  # 质量预审 14 项闸门与阈值
│   ├── coverage_audit.md     # ★覆盖率评审（逆向）：模块级下钻 + G1/G2/G3 缺口
│   ├── mutation_review.md    # ★强度闸门（P0 阻断）：需求层变异 + 零强度规则 + killer_pattern 规范
│   ├── defect_loop.md        # ★缺陷反哺评审（真实缺陷层）：逃逸缺口 G4 + 缺口分类 + 回填顺序
│   ├── workflow.md           # 质量保障机制总览（六道闸门 + 一道事后复盘 + 技术加速器）
│   └── memory_mechanism.md   # 记忆机制
└── scripts/                 # 可执行脚本（19 个，Python 3.14/3.13）
    ├── extract_requirements.py  # Step1 抽取需求规则清单
    ├── map_coverage.py          # 用例↔需求规则覆盖映射
    ├── prescreen.py             # 质量预审闸门（14 项）
    ├── matrix_lint.py           # Step3.5 矩阵 lint（边界点/未消费等价类/编造/假设占比/列错位）
    ├── coverage_audit.py        # 覆盖率评审（模块级下钻 + 缺口报告）
    ├── mutation_audit.py        # 强度审计（需求层变异，实验性，默认 warn 不阻断）
    ├── score_testcases.py       # 质量评分
    ├── to_excel.py              # 导出 10 列 Excel（`--emit-template` 出空白模板；`--with-environment`/`--with-remark`/`--with-defect` 可叠加 11–13 列）
    ├── defect_audit.py          # 缺陷反哺评审（逃逸清单/零覆盖模块/缺口回填，默认不阻断）
    ├── selftest_defect.py       # defect_audit 离线自测（17 项断言）
    ├── to_xmind.py              # 导出 XMind
    ├── read_xmind.py            # 解析 XMind 输入
    ├── read_ui_image.py         # 多模态读 UI 截图
    ├── memory_io.py             # 记忆读写
    └── doc_stats.py             # 文档计数一致性闸门（--check 校验 / --apply 自动回写）
└── tests/                   # 回归（`python tests/run_all.py`，路径无关）
    ├── run_all.py               # 一键跑全部回归（含 scripts/selftest_*.py）
    └── test_*.py                # 预审 / 矩阵 / 覆盖审计 / 契约 / 退出码 / 范围性用例 / 计数
```

### 分层职责与边界

| 层 | 文件 | 职责边界 |
|---|---|---|
| **控制面** | `SKILL.md` | 6 步工作流编排 + 资源索引；不存放具体规范细节 |
| **F. 流程闸门** | `analysis_gate.md` | 定义"什么时候可以开始生成"：两阶段（分析→确认→生成）、报告模板、硬约束 H1–H5 |
| **B. 用例编写规范** | `case_design.md`（权威）、`naming_rules.md`、`output_format.md`、`xmind_output.md`、`excellent_case_patterns.md`（经验证据层） | 定义"用例怎么写"：字段写法、命名红线、Excel/XMind 容器、优秀范式与反面清单 |
| **A. 方法论** | `function_points.md`、`test_methods.md`、`testpoint_checklist.md`、`multimodal.md` | 定义"如何设计"（拆解 / 方法 / 测试点 / 读图） |
| **C. 优先级** | `priority_p0_p3.md` | P0–P3 分级策略（优先级唯一权威来源） |
| **D. 数据规则** | `data_rules.json`（可执行规则库）+ `data_rules.md`（说明与口径） | 仅测试数据校验映射库；`json` 是机器读的那份，`md` 是人读的 |
| **E. 质量保障** | `quality_standards.md`、`quality_prescreen.md`、`coverage_audit.md`、`mutation_review.md`（强度闸门）、`defect_loop.md`（缺陷反哺）、`workflow.md`、`memory_mechanism.md` | 定义"怎么验"：标准/评分、预审闸门、覆盖率评审（模块级下钻）、强度评审（需求层变异）、缺陷反哺（真实故障对账）、机制总览、记忆 |

> **边界原则：每条规则只在一处定义（单一真相源）。** `case_design.md` 为用例编写规范唯一权威；优先级模型只存于 `priority_p0_p3.md`(P0–P3，唯一权威)；评分 rubric 只在 `quality_standards.md`；数据校验只在 `data_rules.md`。交叉处一律用"见 xxx"引用，不复制规则。

## 四、6 步工作流

| 步骤 | 名称 | 产出 |
|---|---|---|
| ① | 需求深度分析 | `requirements.json` / `requirement_rules.json` / `requirements.md` + **《测试分析报告》**（🚧 STOP & ASK：确认后才继续） |
| ② | 功能点分解 | 原子化功能点清单（页面/模块维度） |
| ③ | 测试点分析 | 测试点 Markdown（5 维度覆盖 + 四类场景配额） |
| ④ | 模板确认 | 10 列 Excel 模板 + 命名/优先级口径 |
| ⑤ | 用例设计 | 结构化用例 JSON（含 `coverage_rule` / `design_method` / `priority`） |
| ⑥ | 用例输出 | 10 列 Excel + XMind + 测试报告 + 质量评分 + 可选覆盖率评审报告 |
| ⑥.5 | 缺陷反哺（可选，版本收尾/接手存量库） | 《缺陷反哺报告》+ 逃逸缺陷清单 + 缺口回填草案（**默认不阻断**） |

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

# 4. 质量预审闸门（14 项；后 4 项深度闸门在 Step 5 模板里一律 block）
python scripts/prescreen.py ./out/test_cases_mapped.json \
    --requirement-rules ./out/requirement_rules.json --coverage-min 0.95

# 4b. 覆盖率评审：模块级下钻 + 三类缺口（可选；首个参数也可直接传历史用例库 .xlsx）
python scripts/coverage_audit.py ./out/test_cases_mapped.json ./out/requirements.json \
    -o ./out/覆盖率报告.md

# 5. 导出 10 列 Excel（需"测试环境/前置条件"分列时加 --with-environment 出 11 列）
python scripts/to_excel.py ./out/test_cases_final.json -o 测试用例.xlsx [--with-environment]

# 6. 质量评分（每项维度需 ≥90，任一不足自动回退）
python scripts/score_testcases.py ./out/test_cases_final.json

# 7. 缺陷反哺（可选：版本收尾 / 接手存量库；无缺陷数据则跳过，不阻断）
python scripts/defect_audit.py bugs.json 测试用例.xlsx \
    --module-map ./out/module_map.json --layer 3 -o ./out/缺陷反哺报告.md \
    --emit-backfill ./out/regression_backfill.json
```

## 七、依赖

- Python ≥ 3.8（推荐 3.13）
- `Pillow`（多模态读图）、`openpyxl`（Excel 导出）可选，按用到的脚本安装

## 八、许可证

默认 MIT。如需其他许可证，请在仓库根目录补充 `LICENSE` 文件。
