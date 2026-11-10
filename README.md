# Skills · WorkBuddy 测试技能集合

本仓库是 WorkBuddy **测试类技能**的集合，每个技能独立存放在同名子目录中，可单独取用。

| 技能 | 说明 |
|---|---|
| [`testcase-generator/`](testcase-generator/) | 把 PRD / UI 设计图 / XMind 需求，结构化转成可直接执行的测试用例（10 列 Excel 主产物）。含分析闸门（STOP & ASK）、**14 项质量预审**、等价类/边界值矩阵闸门、模块级覆盖率评审、变异强度闸门、缺陷反哺闭环 |
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
├── scripts/        # 可执行脚本（Python 3.13，仅标准库 + openpyxl/Pillow）
└── tests/          # 回归（`python tests/run_all.py`，路径无关）
```

## 仓库级工具（`tools/`）

| 工具 | 用途 |
|---|---|
| `tools/skill_selfcheck.py` | **技能一致性自检**：引用 / 索引 / 计数 / 项数 / 规则数 / CLI 参数 / 编号连续性 / 字段契约 / 口径冲突，共 A–N 14 类。`--skill` 可指向同一技能的另一份副本 |
| `tools/sync_skill_to_repo.py` | **本地 → 仓库同步**：逐个技能比对并写入，默认 dry-run，`--apply` 才落盘，`--prune` 才删冗余。文本统一 LF |

两者都**路径无关**：仓库根从脚本位置（`tools/` 的上级）推断，本地技能目录默认 `~/.workbuddy/skills`，可用 `TC_REPO` / `TC_SKILL` / `WB_SKILLS` 覆盖。

```bash
python tools/skill_selfcheck.py          # 自检，0 ERROR 才算过
python tools/sync_skill_to_repo.py       # dry-run 看差异
python tools/sync_skill_to_repo.py --apply
```

## 报告（`docs/`）

| 文件 | 内容 |
|---|---|
| `docs/整体自检报告_20261109.md` | 技能整体自检 + 可行性评估（**2026-11-09 快照**，其中 3 个缺陷已在 1.9.3 修复、P0/P1/P2 建议已在 1.9.4 落地） |
| `docs/真库校准报告_20261110.md` | 用真实项目库（1669 条已执行用例）校准的结果（**2026-11-10 快照**，对应 1.9.5） |

> 两份报告都是**当时时点的快照**，不代表当前状态。当前口径以 `CHANGELOG.md` 与技能内文档为准。

## 组合用法

| 阶段 | 用哪个技能 |
|---|---|
| 有需求、要从零出用例 | `testcase-generator` |
| 用例已有一批，但顺序混乱不可执行 | `test-case-sorter` |

> 用例库的**模块级深挖**、**三分类审计**、**测试计划成文**目前不随本仓库发布，按项目单独维护。

## 许可证

默认 MIT。各技能目录下的 `LICENSE` 优先。
