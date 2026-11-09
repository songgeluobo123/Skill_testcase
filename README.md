# Skills · WorkBuddy 测试技能集合

本仓库是 WorkBuddy **测试类技能**的集合，每个技能独立存放在同名子目录中，可单独取用。

| 技能 | 说明 |
|---|---|
| [`testcase-generator/`](testcase-generator/) | 把 PRD / UI 设计图 / XMind 需求，结构化转成可直接执行的测试用例（10 列 Excel 主产物）。含分析闸门（STOP & ASK）、9 项质量预审、模块级覆盖率评审、变异强度闸门、缺陷反哺闭环 |
| [`test-case-sorter/`](test-case-sorter/) | 按业务流程给测试用例排序：五层模型 + 六级判定优先级，还原可直接执行的用例顺序（内容与格式零改动） |

每个技能的详细规范见各自目录下的 `SKILL.md`（控制面）与 `README.md`（说明）。

更新日志见 [CHANGELOG.md](CHANGELOG.md)。English: [README.en.md](README.en.md)

---

## 目录约定

```
<skill-name>/
├── SKILL.md        # 技能主指令（控制面：流程编排 + 资源索引）
├── README.md       # 技能说明（可选）
├── references/     # 方法论与规范（单一真相源，每条规则只在一处定义）
└── scripts/        # 可执行脚本（Python 3.13，仅标准库 + openpyxl/Pillow）
```

## 组合用法

| 阶段 | 用哪个技能 |
|---|---|
| 有需求、要从零出用例 | `testcase-generator` |
| 用例已有一批，但顺序混乱不可执行 | `test-case-sorter` |

> 用例库的**模块级深挖**、**三分类审计**、**测试计划成文**目前不随本仓库发布，按项目单独维护。

## 许可证

默认 MIT。各技能目录下的 `LICENSE` 优先。
