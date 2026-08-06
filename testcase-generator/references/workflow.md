# 六步流程的完整质量保障机制

本档为 `SKILL.md` 六步工作流的**完整机制说明**，把"理解需求 → 应用方法 → 统一格式"
三大问题拆进 6 个步骤，并在 Step 5 嵌入质量预审闸门、Step 6 嵌入评分与记忆。

---

## Step 1 — 需求深度分析：让 AI 理解需求

- **输入规范化**：需求资料放 `test_input/{版本+需求名}/prd/`。
- **XMind 优先**：`.xmind` 用 `scripts/read_xmind.py "<路径>/*.xmind" -f tree` 读取需求树（替代 xmind-reader）。
- **PRD / MD**：`scripts/extract_requirements.py PRD.md -o ./out` 产出 `requirements.json` / `requirement_rules.json` / `requirements.md`。默认「表格合并」把每个表格合并为单条需求规则，使覆盖率分母落在**需求陈述级**。
- **图片 / 原型**：`scripts/read_ui_image.py <img>` 校验并输出元素抽取骨架，随后视觉读图（见 `multimodal.md`），识别出的隐含规则并入需求清单，无法确认的规则标 `[假设]`。
- **记忆读取**：`scripts/memory_io.py load` 读历史歧义 / 端类型 / 步骤粒度 / 历史漏测。
- **列澄清项**：模糊点或缺失信息交用户确认（检查点②之一）。

**本步输出**：需求分析结果（供 Step 2）。

---

## Step 2 — 功能点分解：从需求到原子可测单元

- 按 `function_points.md`：功能点 ≠ 需求点，以页面 / 二级页为单位拆解，标注功能类型（列表 / 表单 / 流程 / 交互 / 系统 / 特殊）。
- 输出功能点清单（供 Step 3）。

---

## Step 3 — 测试点分析：系统化"怎么测"

- 基于功能点清单，按 `testpoint_checklist.md` 的 5 维度 + 覆盖清单逐功能点产出测试点（不含预期）。
- **输出路径（强制）**：`test_output/{版本+需求名}/testpoint/{版本} 测试点.md`。

---

## Step 4 — 模板确认：统一输出格式

- 用 `output_format.md` 的 10 列 Excel 模板；项目有历史模板时用 `scripts/to_excel.py --emit-template` 生成对照。
- 学习 `case_design.md` 的 10 原则、命名 / 格式规范、P1–P4 口径。

---

## Step 5 — 用例设计 + 质量预审闸门

- 应用 6 种方法（`test_methods.md`）把测试点转化为用例，每条写 `priority`（P1–P4）、`design_method`（6 方法之一或多）、`module`、`precondition`、`steps`、`expected`、`test_data`、`coverage_rule`。
- **预审闸门**（见 `quality_prescreen.md` + `prescreen.py`）：6 项检查（覆盖率、P1/P2 占比、方法关联、无编造、无重复）。任何一项不达标先自动修正，改完再进入 Step 6。
- **检查点①**：阈值是否适用本项目（如安全攸关软件上调 P1 占比）。

---

## Step 6 — 用例输出 + 评分 + 记忆

- **导出 Excel（强制）**：`scripts/to_excel.py test_cases.json -o "<...>.xlsx"`（10 列）。
- **可选 XMind**：`scripts/to_xmind.py test_cases.json -o report.xmind --project <项目名>`。
- **质量评分**：`scripts/score_testcases.py test_cases.json`（<70 回退重生成）。
- **记忆写入**：`scripts/memory_io.py record --root <项目根> --category <ambiguity|endpoint|granularity|missed> --content <...>`。
- **执行反馈闭环**：用例执行失败但功能正常 → 修正用例；线上漏测 → 反向补场景。

---

## 技术支撑（可选加速器）

- **领域大模型微调**：基于历史优质用例微调，贴合业务规范。
- **知识图谱关联**：构建"需求-场景-用例"图谱，定位未覆盖点。
- **模拟执行引擎**：UI 用例用 Selenium 模拟执行，API 用例用 Mock 验证参数合法性。
- **人工反馈接口**：标记优质 / 劣质用例及原因，用于优化生成逻辑。
