# Changelog

本文件记录 Skills 仓库（WorkBuddy 技能集合）的发布历史。格式参考 [Keep a Changelog](https://keepachangelog.com/)。

## [1.0.1] - 2026-08-08

### 新增
- **`testcase-generator` 测试用例评级策略（P0–P3）**：新增 `references/priority_p0_p3.md`，提供 P0–P3 四级优先级口径（与默认 P1–P4 并存）。
  - 五维评分模型（业务重要性 / 用户影响 / 故障概率 / 修复成本 / 使用频率）定量定级
  - 7 条硬规则决策表（命中即定级，高于评分）
  - 与六类质量属性、设备 / 移动 / 手环三端映射，及分级 SOP 与维护升降级规则
  - 同步更新 `SKILL.md`、`case_design.md`、`data_rules.md` 以引用统一评级口径
- **`testcase-generator` 测试用例命名规则**：新增 `references/naming_rules.md`，定义用例名称命名规范。
  - 目的与原则：一眼看懂 / 名称 ≠ 预期 / 可检索聚合 / 单一对应
  - 7 条强制红线（命名评审必查）：长度 ≤20 字、不含预期判定词、无数字序号前缀、无【】包裹、无冗余前缀、术语统一、无模糊量词
  - 同步在 `SKILL.md` 的 references 索引与 Step 4 编写习惯说明中引用该文件

## [1.0.0] - 2026-08-06

首个公开版本，包含 `testcase-generator` 技能。

### 新增
- **`testcase-generator` 技能**：把 PRD / UI 设计图 / XMind 需求，结构化转成可直接执行的测试用例。
  - **10 列 Excel 主产物**：用例编号 / 测试模块 / 用例名称 / 优先级 / 测试类型 / 前置条件 / 测试步骤 / 预期结果 / 适用阶段 / 设计方法
  - **6 步工作流**：需求深度分析 → 功能点分解 → 测试点分析 → 模板确认 → 用例设计 → 用例输出
  - **6 种黑盒测试方法**：等价类划分、边界值分析、场景法、状态迁移法、判定表法、正交分析法
  - **质量预审闸门**：覆盖率 / 方法关联 / 无编造 / 无重复 / 优先级占比，不达标不出库
  - **质量评分**：覆盖 / 准确 / 可执行 / 优先级 4 维评分，低于阈值自动回退
  - **多源输入**：PRD 文本、UI 截图（多模态读图）、XMind 解析
  - **多格式输出**：Excel、XMind、Markdown 测试报告 / 测试点
  - **记忆机制**：跨会话复用历史产品约束
- **仓库级文件**：`README.md`（集合索引）、`README.en.md`、`LICENSE`（MIT）、`CHANGELOG.md`、`.gitignore`

### 说明
- **仓库结构**：每个技能独立存放在同名子目录（如 `testcase-generator/`），根目录仅放集合级文件，便于扩展为多技能集合。
- **Release `v1.0`** 附带打包产物 `testcase-generator.zip`（技能源码快照，不含 `.git`）。
- **本地安装路径**：WorkBuddy 用户级技能目录为 `~/.workbuddy/skills/testcase-generator/`（扁平结构，即本仓库 `testcase-generator/` 子目录的内容），克隆后把该子目录复制到技能目录即可使用。

[1.0.1]: https://github.com/songgeluobo123/Skills/releases/tag/v1.0.1
[1.0.0]: https://github.com/songgeluobo123/Skills/releases/tag/v1.0
