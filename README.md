# Skills · WorkBuddy 测试技能集合

本仓库是 WorkBuddy **测试类技能**的集合，每个技能独立存放在同名子目录中，可单独取用，也可按「生成 → 排序 → 深挖 → 审计 → 出计划」串成一条用例全生命周期流水线。

| 技能 | 说明 |
|---|---|
| [`testcase-generator/`](testcase-generator/) | 把 PRD / UI 设计图 / XMind 需求，结构化转成可直接执行的测试用例（10 列 Excel 主产物）。含分析闸门（STOP & ASK）、9 项质量预审、模块级覆盖率评审、变异强度闸门、缺陷反哺闭环 |
| [`test-case-sorter/`](test-case-sorter/) | 按业务流程给测试用例排序：五层模型 + 六级判定优先级，还原可直接执行的用例顺序（内容与格式零改动） |
| [`testcase-module-deepdive/`](testcase-module-deepdive/) | 对**单个功能模块**做穿透式质量深挖并分批安全落库：批次 A（补缺口/硬化弱预期，只增不删）→ 批次 B（删重/合并/改名，需单独确认），全程 dry-run → 确认 → apply → 门禁 → 回读核对 |
| [`testcase-triclass-audit/`](testcase-triclass-audit/) | 基于三分类理论 V2.1 审计用例「设备型号」列（公共 / 横屏专项 / 竖屏专项）的分类准确性与跨类重复副本，并按三者关系原则处置冗余 |
| [`test-plan-generator/`](test-plan-generator/) | 基于标准测试计划模板生成测试计划 Word 文档：复制模板 → 填占位符 → 另存为《产品名》产品《版本号》测试计划.docx（原模板不改写） |

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
| 某个模块质量差，要深挖重构 | `testcase-module-deepdive` |
| 用例库跨设备形态，分类乱了 | `testcase-triclass-audit` |
| 用例齐了，要出测试计划交付 | `test-plan-generator` |

## 许可证

默认 MIT。各技能目录下的 `LICENSE` 优先。
