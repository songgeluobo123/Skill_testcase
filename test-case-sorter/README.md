# test-case-sorter · 测试用例流程排序

> WorkBuddy 技能：把散乱的测试用例，按**业务执行链路 + 测试点依赖**还原成能照着跑的执行清单。只重排行，不改内容与格式。

## 一、这个技能解决什么

用例库常见的「乱」有三种：按 ID 导出、按拼音排序、多人合并后顺序错乱。直接拿去执行，会出现「先测暂停再测登录」「同一个页面的用例散落在三百行之外」这类问题。

本技能用一套**五层排序模型 + 六级判定优先级**，把顺序还原成真实使用链路：

```
L0 分类分区   公共 → 横屏专项 → 竖屏专项（或 公共 → BB2 → BB3）
 └ L1 顶级模块   APP → 嵌入式固件 → 联调功能 → 系统后台
     └ L2 功能模块  启动 → 登录 → 手机号 → 协议书 → 验证码 → …
         └ L3 测试点   模块内的界面/子流程节点（进入 → 主流程 → 交互 → 校验 → 异常 → 适配）
             └ L4 组内次序  显式序号 > 类型序（可选）> 优先级序（可选）> 原始顺序
```

三条设计取舍：

- **保序优于重排** —— 规则没覆盖到的用例「承接上一个测试点、保持原相对位置」，不甩到模块末尾。因为原库顺序往往承载了作者写用例时的测试点逻辑。
- **属性不越权** —— 测试类型、优先级、测试状态默认只是标签，不参与排序。这一点有实证：某真实用例库 58 条模块中类型切换 21 次、优先级 P0/P2/P4/P3 混排，说明作者压根没按这两维排。
- **幂等** —— 排序键末位永远是原始行号，同一份文件反复排序结果完全一致，不会二次打乱。

## 二、快速开始

```bash
# 1) 用内置默认流程直接排
python scripts/sort_test_cases.py cases.xlsx

# 2) 指定项目流程配置 + 出排序报告
python scripts/sort_test_cases.py cases.xlsx \
    --flow-config references/flow_config.eqi_aicoach_sw.json \
    --report 排序报告.md

# 3) 先演练看未归类，不写文件
python scripts/sort_test_cases.py cases.xlsx \
    --flow-config references/flow_config.eqi_aicoach_sw.json \
    --dry-run --dump-unclassified 待补清单.txt

# 4) 多 Sheet 一次排完，覆盖原文件（自动 .bak 备份）
python scripts/sort_test_cases.py cases.xlsx \
    --flow-config references/flow_config.eqi_aicoach_sw.json \
    --all-sheets --inplace --add-seq 执行序号
```

只依赖 `openpyxl`（仅处理 `.xlsx` 时需要）。

## 三、目录结构

```
test-case-sorter/
├── SKILL.md                        # 技能主文档（策略、判定优先级、IO 约定、边界处理）
├── README.md                       # 本文件（面向使用者）
├── LICENSE
├── scripts/
│   └── sort_test_cases.py          # 排序主脚本（五层模型 + 多 Sheet + 格式保真 + 自检）
└── references/
    ├── flow_config.eqi_travel.json        # 基准配置：1278 条 / 4 顶级 / 19 模块
    ├── flow_config.eqi_aicoach_sw.json    # AI Coach 软件版：2410 条 / 15 模块 / 三分类
    ├── flow_config.eqi_aicoach_v1.json    # AI Coach 早期版：1393 条 / 12 模块
    ├── flow_config.eqi_triclass.json      # EQi 三分类（公共→横屏→竖屏）
    ├── flow_config.eqi_func_business.json # EQi 15 功能模块业务流
    ├── flow_config.eqi_portrait.json      # EQi 竖屏专项业务流
    ├── flow_config.eqi_funcprefix.json    # EQi 层级前缀匹配示例
    ├── flow_config.ebike_handmade.json    # E-Bike 人工维护用例
    ├── flow_config.ebike_prd.json         # E-Bike PRD 生成用例
    └── flow_config.example.json           # 最小示例
```

## 四、配置怎么写

一份 `flow_config.json` 就三件事：**分区怎么排、模块怎么排、模块内怎么分测试点**。

```json
{
  "partition": { "column": "设备型号", "order": ["公共", "横屏专项", "竖屏专项"], "default": "公共" },
  "top_module_sequence": ["APP", "嵌入式固件", "联调功能", "系统后台"],
  "top_module_mode": "sub",
  "stages": [{ "name": "S1 账号与准入", "modules": ["APP-启动", "APP-登录"] }],
  "module_sequence": ["APP-启动", "APP-登录"],
  "module_options": { "APP-启动": { "keep_order": true } },
  "testpoint_rules": {
    "APP-登录": [
      { "group": "01 一键登录界面与入口", "match": ["一键登录界面", "进入一键登录"] },
      { "group": "02 密码登录与校验", "exclude": ["邮箱"], "match": ["密码登录", "密码位数"] }
    ]
  }
}
```

三个最容易踩的点：

1. **数组下标就是组顺序**。`02` 排在 `01` 后面，是因为它在数组第二位，不是靠名字里的数字。
2. **`rule.priority` 只改「谁先匹配」，不改「谁排前面」**。用于处理「安全夹脱落」要先于「系上安全夹」被识别、但组顺序仍然后者在前这类冲突。
3. **模块一个都不能漏**。漏写 `testpoint_rules` 的模块会退化成单组；确实只想分组保序的，请显式写 `keep_order: true`，否则脚本会告警。

## 五、输出与质量门禁

| 项 | 默认 | 可配置 |
|---|---|---|
| 输出路径 | `原名_sorted.xlsx` | `--output` / `--inplace`（自动 `.bak`） |
| 工作表 | 当前活动表 | `--sheet` / `--all-sheets` |
| 序号列 | 不追加 | `--add-seq "执行序号"` |
| 排序报告 | 不生成 | `--report x.md` |
| 未归类清单 | 不生成 | `--dump-unclassified x.txt` |

**格式承诺**：除行顺序外，单元格值、字体/填充/边框/对齐、行高、超链接、批注、冻结窗格、列宽、非目标工作表全部保持不变。

自检项（脚本自动跑）：内容零改动 · 条数一致 · 模块成块 · 未归类 0 · 每模块有规则或 `keep_order` · 格式保真。

## 六、适用与不适用

**适用**：用例按 ID/拼音/录入时间散乱需还原顺序；三分类/多机型库需按形态集中执行；手工维护的库需补排序但不想打乱原有测试点逻辑；需要一份可核对的排序依据。

**不适用**：增删列或改写用例内容；纯按优先级筛选；跨文件合并用例库。

---

详细规则、判定优先级、边界与异常处理、12 类场景行为表见 [SKILL.md](SKILL.md)。
