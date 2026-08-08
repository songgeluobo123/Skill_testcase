# XMind 输出规范

生成的文件是 `.xmind`，结构严格按照 XMind 导入规范组织，打开即一份结构清晰的测试用例树，**无需二次整理**。

**核心观点：打开 XMind，全选导入，一份结构清晰的测试用例树就在眼前了。**

---

## 树结构

```
根节点（项目名）
└── 功能模块（按 module）
    └── 测试用例（每条一个节点）
        ├── 标签(label) = 优先级（P0–P3）
        └── 备注(notes.plain.content) =
              【前置条件】
              【操作步骤】
              【测试数据】
              【预期结果】
              【覆盖规则】
              【设计方法】
```

- 同一模块下的用例按功能区域归类，**不会出现"每个功能点单独建一个目录"导致目录爆炸**。
- 优先级用 XMind 标签，便于按优先级筛选 / 筛选视图。

## 生成

```bash
python scripts/to_xmind.py cases.json -o E-Bike_测试用例.xmind --project "E-Bike 智能骑行"
```

- 输入为 Step 6 产出的结构化 `test_cases.json`（每条含 `module / priority / precondition / steps / test_data / expected / coverage_rule / design_method`）。
- 输出 `.xmind` 可直接被 XMind 2020+ 打开。

## XMind 2020+ content.json 关键结构

`.xmind` 本质是 ZIP，含 `content.json` / `metadata.json` / `manifest.json`。`content.json` 为顶层数组：

```json
[
  {
    "id": "sheet-1",
    "class": "sheet",
    "title": "E-Bike 智能骑行",
    "rootTopic": {
      "id": "root-1",
      "class": "topic",
      "title": "E-Bike 智能骑行",
      "children": {
        "attached": [
          {
            "id": "mod-登录",
            "class": "topic",
            "title": "登录",
            "children": {
              "attached": [
                {
                  "id": "tc-001",
                  "class": "topic",
                  "title": "TC-001 · P0",
                  "labels": ["P0"],
                  "notes": { "plain": { "content": "【前置条件】...\n【操作步骤】...\n..." } }
                }
              ]
            }
          }
        ]
      }
    }
  }
]
```

> 详细序列化逻辑见 `scripts/to_xmind.py`。如需导出为 XMind Zen 旧版（content.xml），可在此脚本基础上扩展，但 2020+ 版（content.json）已覆盖绝大多数使用场景。
