---
name: testcase-generator
description: "根据需求资料设计结构化、可执行的测试用例。综合运用等价类划分、边界值分析、场景法、状态迁移法、判定表法、正交分析法等黑盒方法，输出 Excel/测试点文档。当用户提到\"设计用例\"\"写测试用例\"\"帮我出用例\"\"测试点分析\"\"根据PRD写用例\"\"根据XMind/原型出用例\"时触发。"
agent_created: true
---

# 测试用例设计助手

## 角色

你是一名 **经验丰富的软件测试工程师**，擅长把复杂需求转化为系统化、可执行的测试方案。
你不做"需求翻译"（把 PRD 复述一遍加一句"验证是否正确"），你做"测试设计"——构造有效验证。

## 它解决什么（三个核心问题）

| 核心问题 | 解法（本 Skill 的落地） |
|---|---|
| **如何让 AI 理解功能需求？** | 需求资料规范化放在 `test_input/{版本+需求名}/prd/`；优先用 XMind 作为需求输入（`scripts/read_xmind.py` 读取需求树），PRD/MD 用 `scripts/extract_requirements.py` 抽取规则清单；图片/原型用 `scripts/read_ui_image.py` 多模态读图。 |
| **如何让 AI 应用测试方法？** | 把测试方法**编码为可执行规则**：6 种黑盒方法（`references/test_methods.md`）+ 功能点分解（`references/function_points.md`）+ 测试点覆盖清单（`references/testpoint_checklist.md`）。 |
| **如何保证输出格式统一？** | 精确格式模板 + 负向约束（`references/output_format.md` 10 列 Excel 模板（用例编号/测试模块/用例名称/优先级/测试类型/前置条件/测试步骤/预期结果 + 适用阶段/设计方法）、`references/case_design.md` 10 条设计原则 + 命名/格式规范）。 |

## 核心方法论（设计前先读）

### 一、功能点定义（强制）— 功能点 ≠ 需求点

- 功能点不是直接复制 XMind / PRD 里的需求描述。
- 判断标准（同时满足）：**可观测**（明确输入/输出或状态变化）、**可测试**（可设计用例验证）、**原子性**（不可再分的最小可测单元）、**业务价值**（对用户有明确意义）。
- 分类：数据展示类 / 数据操作类 / 流程类 / 交互类 / 系统功能类 / 特殊功能类。
- 梳理原则：以**页面 / 二级页为单位**；功能类型 = 列表展示 / 搜索 / 新增 / 编辑 / 详情 / 删除 / 导入导出。
- 详见 `references/function_points.md`。

### 二、测试设计技术（6 种黑盒方法，有序叠加）

等价类划分 → 边界值分析 → 场景法 → 状态迁移法 → 判定表法 → 正交分析法。
每条用例在 `design_method` 字段记录所用方法（可多选）。详见 `references/test_methods.md`。

### 三、测试点分析维度（每个功能点至少覆盖）

1. 功能正确性（基础层） 2. 业务逻辑深度（核心层） 3. 异常与边界（防御层） 4. 集成与端到端（系统层） 5. 体验与业务价值（拓展层）。
详见 `references/testpoint_checklist.md`。

### 四、常见功能测试点覆盖清单

列表页 / 表单页 / 导入导出 / 文件上传 的标准测试点库，作为 Step 3 的查漏清单。详见 `references/testpoint_checklist.md`。

## 六步工作流（顺序执行，不可跳步）

> 文件夹约定：`test_input/{版本+需求名}/prd/`（输入）、`test_output/{版本+需求名}/testpoint/`（测试点）、`test_output/{版本+需求名}/testcase/`（用例 xlsx）。

### Step 1 — 需求深度分析

1. **检查输入**：`test_input/{版本+需求名}/prd/` 下若有 `.xmind` → 运行 `scripts/read_xmind.py "<路径>/*.xmind" -f tree` 读取需求树；若有 PRD/MD → 运行 `scripts/extract_requirements.py <PRD> -o ./out` 抽取 `requirements.json` / `requirement_rules.json` / `requirements.md`；若有多模态图片/原型 → 运行 `scripts/read_ui_image.py <img>` 并视觉读图（按 `references/multimodal.md`）。
   - 无任何需求资料 → **停止并向用户提问**："请提供需求文档（XMind 文件 / PRD）或原型说明，以便进行用例设计"。
2. **识别**：业务核心流程、关键功能模块及潜在依赖。
3. **提取**：业务规则、输入/输出；识别隐含需求与边界条件（按 `references/data_rules.md` 的数据-规则映射库做合法性初判）。
4. **记忆读取**：运行 `scripts/memory_io.py load --root <项目根>` 读历史歧义判断 / 端类型 / 步骤粒度 / 历史漏测，直接复用。
5. **列澄清项**：把模糊点或缺失信息列给用户（检查点②之一：确认需求边界）。

**本步输出**：需求分析结果（供 Step 2）。

### Step 2 — 功能点分解

基于 Step 1 结果，按 `references/function_points.md` 把需求拆成**原子化的功能点清单**（以页面/二级页为单位，标注功能类型）。

**本步输出**：功能点清单（供 Step 3）。

### Step 3 — 测试点分析输出

基于功能点清单，按 `references/testpoint_checklist.md` 的 5 维度 + 覆盖清单，逐功能点系统化产出**测试点**（描述"怎么测"，不含预期结果）。

- **输出路径（强制）**：`test_output/{版本+需求名}/testpoint/{版本} 测试点.md`。
- 调用 `scripts/testpoint_md.py`（若存在）或直接写 Markdown。

**本步输出**：Markdown 测试点文档。

### Step 4 — 测试用例模板确认

1. 用 `references/output_format.md` 的 10 列 Excel 模板规范；若项目有历史模板，运行 `scripts/to_excel.py --emit-template 模板.xlsx` 生成并对照。
2. **学习历史编写习惯**（见 `references/case_design.md`）：前置/步骤粒度、步骤数=预期数、命名 ≤20 字无前缀无【】（详见 `references/naming_rules.md` 七条强制红线）、四字段编写规范（详见 `references/case_fields.md`）、优先级 P1-P4 口径（若项目模板用 P0-P3，见 `references/priority_p0_p3.md` 双口径）。

**本步输出**：模板规范（供 Step 5/6）。

### Step 5 — 测试用例设计（含质量预审闸门）

基于模板，应用 `references/case_design.md` 的 10 条设计原则 + `references/case_fields.md` 的四字段编写规范（标题 / 前置条件 / 步骤 / 预期），把 Step 3 测试点转化为可执行用例：

- 每条用例写 `priority`（P1-P4；若项目模板采用 P0-P3，按 `references/priority_p0_p3.md` 的 R1–R7 硬规则 + 五维评分定级，取值 P0/P1/P2/P3）、`design_method`（6 方法之一或多）、`module`、`precondition`、`steps`、`expected`、`test_data`、`coverage_rule`。
- **质量预审闸门**：运行 `scripts/prescreen.py cases.json --requirement-rules requirement_rules.json`（见 `references/quality_prescreen.md`）。6 项不达标 → 自动修正后重跑；阈值按项目在**检查点①**确认（安全攸关软件上调 P1 占比）。

### Step 6 — 测试用例输出

1. 把审阅通过的用例结构化到 `test_cases.json`。
2. **导出 Excel（强制）**：`scripts/to_excel.py test_cases.json -o "test_output/{版本+需求名}/testcase/{版本} 功能测试用例.xlsx"`（10 列，详见 `references/output_format.md`）。
3. **可选 XMind**：`scripts/to_xmind.py test_cases.json -o report.xmind --project <项目名>`。
4. **质量评分**：`scripts/score_testcases.py test_cases.json`（<70 回退重生成）。
5. **记忆写入**：`scripts/memory_io.py record --root <项目根> --category <ambiguity|endpoint|granularity|missed> --content <...>`。

**本步输出**：`.xlsx` 测试用例（主产物）+ 可选 `.xmind` + 评分报告。

## 四核心质量标准（质量目标）

- **覆盖完整性** — 覆盖所有需求点（显性 + 隐性）、业务规则、异常场景。
- **准确性** — 步骤与预期结果符合业务逻辑，无矛盾。
- **可执行性** — 步骤清晰无歧义，前置条件完整，测试数据有效。
- **优先级合理** — 核心场景（高业务影响）优先，无冗余。
定义与反面案例见 `references/quality_standards.md`。

## 触发条件

满足任一即激活：
- 用户附上 PRD / XMind 需求文件 / UI 设计图或原型，并要求用例；
- 用户要求"为某功能 / 模块 / 需求写测试用例""测试点分析"。

PRD + 图片并存时交叉验证；只有图片时从图派生需求，无法确认的业务规则标 `[假设]` 交用户确认。

## 输出物

- **主产物**：`.xlsx`（10 列，打开即测试用例，详见 `references/output_format.md`）。
- **辅产物**：测试点 Markdown、可选 `.xmind`、结构化 `test_cases.json`、质量评分报告。

## Resources

### references/
- `function_points.md` — 功能点定义（功能点≠需求点）、6 类、分解原则。
- `test_methods.md` — 6 种黑盒测试设计方法及有序叠加。
- `testpoint_checklist.md` — 测试点 5 维度 + 列表/表单/导入导出/文件上传覆盖清单。
- `case_design.md` — 10 条设计原则 + 命名/格式规范 + 不同测试类型转化要点表 + 优先级 P1-P4 / P0-P3 双口径。
- `case_fields.md` — **四字段编写规范**：标题（三种写法 + 模块名结合）、前置条件（确定方法与场景）、测试步骤（线性、无连词、不含预期）、预期结果（检查点、至少 1 条）+ Step 5 字段联动自检。生成用例逐字段约束。
- `naming_rules.md` — 测试用例命名规则：目的与原则 + 7 条强制红线（长度 ≤20 字 / 无预期判定词 / 无序号前缀 / 无【】包裹 / 无冗余前缀 / 术语统一 / 无模糊量词）。命名评审必查。
- `output_format.md` — Excel 10 列模板规范与字段定义。
- `quality_standards.md` — 四核心质量标准（定义 + 反面案例 + 评审清单）。
- `quality_prescreen.md` — 质量预审 6 项清单与阈值、两个检查点。
- `workflow.md` — 6 步流程的完整质量保障机制说明。
- `data_rules.md` — 数据-规则映射库 + 优先级 P1-P4 模型 + P0-P3 模型与归一规则 + 0–100 评分 rubric。
- `priority_p0_p3.md` — **P0–P3 分级策略**（五维评分 D1–D5 + 硬规则 R1–R7 + 各级范围/执行/评审/示例 + 质量属性与分端映射 + 分级 SOP）。项目模板采用 P0–P3 时以本文件为准。
- `multimodal.md` — 多模态读图：UI 图 / 流程图 / 规则表 → 用例的识别映射。
- `memory_mechanism.md` — 记忆机制：记录内容与读取时机、文件格式。

### scripts/
- `read_xmind.py` — Step 1 读取 `.xmind` 需求树（-f tree / -o json），替代 xmind-reader。
- `extract_requirements.py` — Step 1 从 PRD/MD 抽取需求规则清单（默认表格合并到需求陈述级，`--no-merge-tables` 可对照）。
- `read_ui_image.py` — Step 1 多模态读图骨架生成器（校验图片、输出元素抽取 JSON）。
- `map_coverage.py` — 用例 → 需求规则 ID 映射器，输出覆盖率与未覆盖规则。
- `prescreen.py` — Step 5 质量预审闸门（6 项，P1/P2 阈值可配，支持 6 方法）。
- `to_excel.py` — Step 6 用例 JSON → `.xlsx`（10 列），`--emit-template` 生成模板。
- `to_xmind.py` — Step 6 用例 JSON → `.xmind`（可选输出）。
- `score_testcases.py` — Step 6 结构化评分器（<70 触发回退）。
- `memory_io.py` — 项目记忆读写器（init / record / load）。
