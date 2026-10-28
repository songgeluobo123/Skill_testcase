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
| **如何保证输出格式统一？** | 精确格式模板 + 负向约束：列容器见 `references/output_format.md`（10 列 Excel）；内容写法见 `references/case_design.md`（四字段编写规范 + 10 条设计原则）；命名红线见 `references/naming_rules.md`；优先级口径（P0–P3 四级）见 `priority_p0_p3.md`。 |
| **如何证明"没漏测"？** | 正向靠预审的全局覆盖率（≥95%），**模块级下钻**靠 `references/coverage_audit.md` + `scripts/coverage_audit.py`——输出模块覆盖率与三类缺口（G1 缺失 / G2 场景失衡 / G3 名义覆盖），专治"全局 95% 掩盖某模块 40%"。 |

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

> 全程分两阶段（见 `references/analysis_gate.md`）：**阶段 1 分析**（Step 1 → 出《测试分析报告》）→ 🚧 **STOP & ASK 硬闸门**（用户确认）→ **阶段 2 生成**（Step 2–6）。未经确认不得生成用例或导出 Excel。

> 文件夹约定：`test_input/{版本+需求名}/prd/`（输入）、`test_output/{版本+需求名}/testpoint/`（测试点）、`test_output/{版本+需求名}/testcase/`（用例 xlsx）。

### Step 1 — 需求深度分析

1. **检查输入**：`test_input/{版本+需求名}/prd/` 下若有 `.xmind` → 运行 `scripts/read_xmind.py "<路径>/*.xmind" -f tree` 读取需求树；若有 PRD/MD → 运行 `scripts/extract_requirements.py <PRD> -o ./out` 抽取 `requirements.json` / `requirement_rules.json` / `requirements.md`；若有多模态图片/原型 → 运行 `scripts/read_ui_image.py <img>` 并视觉读图（按 `references/multimodal.md`）。
   - 无任何需求资料 → **停止并向用户提问**："请提供需求文档（XMind 文件 / PRD）或原型说明，以便进行用例设计"。
2. **识别**：业务核心流程、关键功能模块及潜在依赖。
3. **提取**：业务规则、输入/输出；识别隐含需求与边界条件（按 `references/data_rules.md` 的数据-规则映射库做合法性初判）。
4. **记忆读取**：运行 `scripts/memory_io.py load --root <项目根>` 读历史歧义判断 / 端类型 / 步骤粒度 / 历史漏测，直接复用。
5. **业务规则咨询**：按 `references/analysis_gate.md` 第四节，依次查「项目记忆 → 既有用例库/知识库 → 需求资料」，固定问两句（该域注意事项 / 关键业务规则）+ 针对缺口逐条动态提问。查不到就**明说"无既有知识可用"**，不得用通用经验填充。
6. **产出《测试分析报告》**：按 `references/analysis_gate.md` 第二节模板输出六节（输入确认 / 关键要点带来源 / 信息缺口 / 建议范围与优先级 / 方法预选 / 待办 A-B）。

> 🚧 **STOP & ASK 硬闸门（强制）**：报告交付后**必须停下等用户明确确认**。确认前 ❌ 不得进入 Step 2 起的生成阶段、❌ 不得产出 `test_cases.json`、❌ 不得导出 Excel。用户已在指令中明确授权"按此范围直接生成"时可跳过等待，但报告仍须产出并随交付附上。
>
> **五条硬约束（违反即返工，详见 `analysis_gate.md` 第三节）**：H1 禁止假设（缺口只进待澄清，最多标 `[假设]` 待确认）· H2 业务规则咨询必须执行 · H3 术语一致性（服务名/接口名/字段名/错误码原样保留）· H4 来源可追溯（章节/URL/知识库条目/MR 号/需求规则 ID）· H5 多源融合须显式写"由 XX 补充"。

**本步输出**：《测试分析报告》（供用户确认；确认后作为 Step 2 输入，并随阶段 2 交付留档）。

### Step 2 — 功能点分解

基于 Step 1 结果，按 `references/function_points.md` 把需求拆成**原子化的功能点清单**（以页面/二级页为单位，标注功能类型）。

**本步输出**：功能点清单（供 Step 3）。

### Step 3 — 测试点分析输出

基于功能点清单，按 `references/testpoint_checklist.md` 的 5 维度 + 覆盖清单，逐功能点系统化产出**测试点**（描述"怎么测"，不含预期结果）。

- **四类场景强制配额**（每功能点，见 `testpoint_checklist.md` 第二节）：正常流程 ≥1 条 · 异常操作 + 边界条件合计 ≥3 条 · **权限校验 ≥1 条**（未登录 / 无权限 / 跨角色越权；无账号体系的离线产品可豁免，须写明理由）。只测顺利路径是最常见的返工来源。
- **输出路径（强制）**：`test_output/{版本+需求名}/testpoint/{版本} 测试点.md`。
- 直接写 Markdown（如需程序化生成可扩展 `scripts/testpoint_md.py`）。

**本步输出**：Markdown 测试点文档。

### Step 4 — 测试用例模板确认

1. 用 `references/output_format.md` 的 10 列 Excel 模板规范；若项目有历史模板，运行 `scripts/to_excel.py --emit-template 模板.xlsx` 生成并对照。
2. **学习历史编写习惯**（见 `references/case_design.md`）：前置/步骤粒度、四字段编写规范（标题/前置/步骤/预期，见第二节）、步骤数=预期数、命名 ≤20 字无前缀无【】（详见 `references/naming_rules.md` 七条强制红线）、优先级统一采用 P0–P3 四级（见 `references/priority_p0_p3.md`）。

**本步输出**：模板规范（供 Step 5/6）。

### Step 5 — 测试用例设计（含质量预审闸门）

基于模板，应用 `references/case_design.md` 的 10 条设计原则 + 四字段编写规范（标题 / 前置条件 / 步骤 / 预期），把 Step 3 测试点转化为可执行用例：

- 每条用例写 `priority`（P0–P3 四级之一，定级规则见 `references/priority_p0_p3.md` 的五维评分 + R1–R7 硬规则）、`design_method`（6 方法之一或多）、`module`、`precondition`、`steps`、`expected`、`test_data`、`coverage_rule`。
- **写法强制要求**（实证模式，完整见 `references/excellent_case_patterns.md`，生成时逐条比对）：① 双前置列分离——`测试环境` 写可整块复用的编号式环境清单，`前置条件` 写本条界面/状态；② 步骤以动词白名单开头（点击/输入/勾选/查验/进入/设置/选择/关闭/上传/下载/对比/记录），按钮名与界面名写具体；③ 预期一律"应…"或数值断言，UI 给元素清单、文案给逐字内容、数据给具体值，**禁止**"合理/美观/流畅/友好/正常显示"等不可判定词；④ 每个等价类 / 边界值 / 权限矩阵 / 多入口 / 多模式测试点**成组输出 ≥3 条**同构用例；⑤ 非功能用例走"场景化前置 + 量化预期 + 统计表引用"三件套；⑥ 版本/端/机型标签列分布均衡，多语言用例预期带差异要求。
- **质量预审闸门**：运行 `scripts/prescreen.py cases.json --requirement-rules requirement_rules.json`（见 `references/quality_prescreen.md`）。**10 项**不达标 → 自动修正后重跑；阈值按项目在**检查点①**确认（安全攸关软件上调 P0 占比）。第 10 项为**孤儿用例**（无 `coverage_rule` 且未标 `exploratory: true`），默认**直接阻断**。

### Step 6 — 测试用例输出

1. 把审阅通过的用例结构化到 `test_cases.json`。
2. **导出 Excel（强制）**：`scripts/to_excel.py test_cases.json -o "test_output/{版本+需求名}/testcase/{版本} 功能测试用例.xlsx"`（10 列，详见 `references/output_format.md`）。项目要求"环境准备 / 界面状态"分列时加 `--with-environment` 输出 11 列（双前置列，见 `excellent_case_patterns.md` 做法 1）；用例中存在**范围性用例**（一条覆盖多个并列子场景）时加 `--with-remark` 在末列输出「备注」列承载场景展开（见门禁速查 13）；需要**双向需求追溯**时加 `--with-rtm requirements.json`，在**第二个 sheet「需求追溯」**输出需求→用例 / 用例→需求 / 孤儿用例矩阵（见 `coverage_audit.md` 四·五）。
3. **可选 XMind**：`scripts/to_xmind.py test_cases.json -o report.xmind --project <项目名>`。
4. **质量评分**：`scripts/score_testcases.py test_cases.json`（**每项维度均需 ≥90**，任一不足即回退重生成）。
5. **可选：覆盖率评审**：`scripts/coverage_audit.py test_cases.json requirements.json -o 覆盖率报告.md`（见 `references/coverage_audit.md`）。做**模块级**下钻，防"全局 95% 掩盖某模块 40%"；接手**存量用例库**时把第一个参数换成历史 `.xlsx` 即可直接评审。需要**双向追溯**时加 `--rtm-xlsx <用例Excel>`，把需求→用例 / 用例→需求 / 孤儿用例写入第二个 sheet。
6. **记忆写入**：`scripts/memory_io.py record --root <项目根> --category <ambiguity|endpoint|granularity|missed> --content <...>`。

**本步输出**：`.xlsx` 测试用例（主产物）+ 可选 `.xmind` + 评分报告 + 可选覆盖率评审报告。

## 四核心质量标准（质量目标）

- **覆盖完整性** — 覆盖所有需求点（显性 + 隐性）、业务规则、异常场景。
- **准确性** — 步骤与预期结果符合业务逻辑，无矛盾。
- **可执行性** — 步骤清晰无歧义，前置条件完整，测试数据有效。
- **优先级合理** — 按 P0 可行性/概念性测试 → P1 主流程必测 → P2 显示完整性 → P3 美观与兼容 定级；主流程与必测项不被显示/美观类用例挤占，无冗余。
定义与反面案例见 `references/quality_standards.md`。

## 触发条件

满足任一即激活：
- 用户附上 PRD / XMind 需求文件 / UI 设计图或原型，并要求用例；
- 用户要求"为某功能 / 模块 / 需求写测试用例""测试点分析"。

PRD + 图片并存时交叉验证；只有图片时从图派生需求，无法确认的业务规则标 `[假设]` 交用户确认。

## 输出物

- **主产物**：`.xlsx`（10 列，打开即测试用例，详见 `references/output_format.md`）。
- **辅产物**：测试点 Markdown、可选 `.xmind`、结构化 `test_cases.json`、质量评分报告。

## 门禁排障速查（踩坑记录）

跑 `prescreen.py` / `score_testcases.py` 反复失败时，先按本节自查，可省数轮返工。

**1. `prescreen.py` 报 `[错误] 读取需求规则清单失败: '/dev/fd/63'`**
- 原因：用 Bash 进程替换 `--requirement-rules <(echo '[...]')` 传参，Python 读不到 fd。
- 解法：**先写临时 JSON 文件再传路径**。
  ```bash
  python -c "import json;json.dump([r['id'] for r in json.load(open('test_cases.json'))['rules']],open('_rules_ids.json','w'))"
  python prescreen.py test_cases.json --requirement-rules _rules_ids.json
  ```
- `--requirement-rules` 只需规则 ID 数组（`["R-001", ...]`），不必是完整规则对象。

**2. `coverage_rule` 为空导致 score 全 0 分**
- 生成脚本若靠函数名/标题关键词自动推断，极易漏配。循环 `for` 生成的用例（如 6 个状态徽标）用正则按 ID 批量注入也会漏。
- 解法：**在 `_case()` 调用里显式写 `coverage_rule="R-009"`**，不要依赖推断；循环体内直接把 `coverage_rule` 作为常量传参。

**3. 优先级分布卡闸门（P0∈[10%,15%]、P2∈[35%,45%]）**
- 调分布时**先算总量再定条数**，改一条就重跑一次，别批量改完再验（容易来回震荡：P0 降完 P2 又超）。
- 建议顺序：先杀 P0（保留横屏主流程 + 竖屏移植等价 + 各端联调）→ 再看 P2（不足就从 P1 拉，超出就退回 P1）→ P3 留 1 条即可。

**4. 批量改优先级时 Python 正则对中文匹配失败**
- 现象：`re.search(rf'{cid}, "[^"]+",\s*"P0"', src)` 对中文标题返回 `None`；即使 `rf'TC-AC-L-008", "[\u4e00-\u9fa5]+", "P0"'` 也失败，只有 `.*?` lazy 模式能匹配。
- 解法：**改用行级替换，别跟正则较劲**。
  ```python
  lines = src.split('\n')
  for i, line in enumerate(lines):
      if cid in line and '"P0"' in line:
          lines[i] = line.replace('"P0"', '"P1"', 1)
  src = '\n'.join(lines)
  ```

**5. score 报「步骤含'点击按钮'但未说明位置，存在歧义」（可执行性扣 20 分）**
- 判据：`"点击" in steps and "按钮" in steps and not ("导航"/"页面"/"右侧"/"左侧" in steps)`。
- 坑：写「点击**右下角**语音按钮」不算过——「右下角」不含「右侧」。
- 解法：统一写成「**页面**右下角的 XX 按钮」或「**页面**右侧的 XX 按钮」，命中「页面」最稳。

**6. 改生成脚本后必须重跑生成**
- 任何优先级 / 步骤 / coverage_rule 的修改都要落到**生成脚本**再重跑，禁止只手改 `test_cases.json` 或只改 Excel，否则下次重生成会回滚。

**7. 预审新增的第 7/8 项（预期可判定 / 标题规范）批量报错**
- 第 7 项：预期里写了 `合理/美观/友好/流畅/良好/正常显示/工整/尽量/适当/无异常` 等不可判定词 → 改成"应…"断言 + 具体值 / 清单 / 逐字文案；主观类必须补判定基线。
- 第 8 项：标题 >20 字、带 `1、` 序号前缀、含【】或句末标点、`steps` 为空、标题含 `（待XX更新）` 类占位 → 逐条改写；同模块标题重名只是告警，但必须靠唯一用例编号区分。

**8. 「预审全过但标题全为空」——`title` 与 `name` 字段双写**
- 原因：`prescreen.py` 第 8 项读 `c.get("title")`，而 `to_excel.py` 读 `c.get("name")`，字段名不一致。
- 解法：生成脚本里**同时写入** `name` 与 `title`（同值）。否则预审报「N 条用例标题为空」且 `steps` 检查失效。

**9. `score_testcases.py` 可执行性必挂 80 分——`test_data` 不能为空**
- 计分：`precondition`(40) + `steps` 长度 ≥15 字(40) + **`test_data` 非空**(20)；`test_data` 为空则封顶 80 < 90 阈值。
- 解法：**每条用例都要带非空 `test_data`**（如 `{"命令":"0x20","期望灯态":"绿色"}`）；key 避开内置规则键 `手机号`/`订单金额`/`用户等级`（未知 key 不扣分，已知 key 值不合法会扣分）。

**10. 准确率被压到 40——步骤含「正确」而预期含「失败/错误」被判矛盾**
- 判据：`re.search("正确", steps) and re.search("(失败|错误|不通过)", expected)` → `accuracy = 40`，总分 ≈85 < 90。
- 解法：改写**步骤**侧的「正确」为可判定表述——「校验和一致」「合法值」「符合定义」；预期侧的「失败/错误」可保留（表达反向场景是必要的）。

**11. 「适用阶段」列混入非法值**
- 只允许 `功能测试 / 集成测试 / 系统测试 / 回归测试` 四值。若把 `性能测试`/`数据一致性测试`/`稳定性测试`/`安全测试`/`兼容性测试` 写进 `stage`，列口径会被污染。
- 解法：在生成器的用例构造函数里做归一跳转（非四值一律落 `系统测试`），而不是逐条手改。

**12. 无屏设备 / 协议类规范的优先级阈值要另设**
- 手环、网关、固件协议等**无 UI** 产品：P3（美观与兼容）可覆盖面天然窄（无界面美观、旋转布局类），P0 却因安全与互斥规则密集而偏高。
- 解法：按项目调整预审阈值，例如安全攸关/协议类用 `--p0-min 0.15 --p0-max 0.28 --p2-min 0.18 --p2-max 0.32`，并在报告里写明源需求表自带优先级分布作为依据，而不是硬凑应用类项目的 10%~15% / 35%~45%。

**13. 范围性用例必须补「备注」列做场景展开**
- 症状：用例步骤写成聚合式——「逐一构造非运动类场景，记录各场景灯态」「依次下发 0x01/0x02/0x05/0x07」；单条覆盖 6~24 个子场景，执行人**无法照做**，也无法判断是否漏测。
- 识别口径：步骤中含枚举动作词 `逐一 / 逐个 / 依次 / 分别 / 遍历 / 逐项 / 逐条`（本项目 564 条中命中 41 条 ≈ 7%）。注意 `全部 / 任一 / 所有` 是**断言词**不是枚举词，不要据此命中。
- 解法：把子场景展开为备注，统一结构 `【场景展开·N 项】总述` → 每行 `序号) 场景名：具体操作 → 观测点` → `【判定】通过标准`。子场景清单**必须回到需求表取**（本项目取自灯语映射 / 命令索引 / 参数与阈值三表），不得臆造。
- 落地（可重跑，不手改 Excel）：备注单独存 `scripts/<项目>_range_remarks.py` 的 `REMARKS` 字典（id → 文本）→ 生成器 main 里按 id 注入 `remark` 字段（无命中写空串，保证 JSON 结构统一）→ `to_excel.py --with-remark` 导出 11 列。
- 例外：**不要**给非范围性用例硬凑备注——留空即可，避免备注列沦为冗余。

**14. 导出时目标 xlsx 被本地预览器占用 → 写入失败**
- 症状：`PermissionError: [Errno 13] Permission denied: '…功能测试用例.xlsx'`，`os.replace` / 直接 `open(...,'wb')` 均失败；根因是本地文档预览器（editor_sdk / Office）/ Excel 正打开该文件持有句柄。
- 解法：先写到临时名（`_tmp_*.xlsx`）完成导出与校验，再尝试重试覆盖原名 2~3 次；仍被锁则落回 `…（含备注）.xlsx` 之类的明确副本名，并在交付说明中告知用户关闭预览后即可覆盖同名主文件。**不要**因写入失败而中断整条生成链（JSON 与闸门结果均已有效）。

**15. 第 9 项（场景构成）整模块报错 / 覆盖率评审出现"假覆盖"**
- 第 9 项阻断口径是"模块内用例数 ≥ `--scene-min-cases`（默认 4）且**无任何**异常·边界·权限用例"。小模块（1~3 条）不会触发，属故意设计，不要为了"消灭告警"硬塞负向用例。
- 若某模块判定长期失灵：多半是 `test_type` 没写或写了非法值，脚本回落到"标题 + 步骤"关键词猜测。**先把 `test_type` 按 `功能/异常/边界/权限/兼容/性能/接口` 规范化**，再重跑。
- 覆盖率评审的**假覆盖**根因：`coverage_audit.py` 只把"显式 `coverage_rule` 命中"或"文本 bigram 相似度达标"算强匹配；**仅模块名相同只列为疑似覆盖**。若发现报告里覆盖率虚高，检查是不是用例自带 `coverage_rule` 但标注过宽——脚本会直接采信显式标注，不会二次校验。
- 存量 `.xlsx` 用例库无 `coverage_rule` 属正常，走文本匹配即可；但**表头必须含「测试模块」与「用例名称」**，否则直接报错退出（表头别名见脚本 `HEADER_ALIASES`）。

## Resources

### references/
- `analysis_gate.md` — **流程闸门与硬约束**：阶段 1《测试分析报告》→ 🚧 STOP & ASK → 阶段 2 生成的两阶段流程、报告六节模板、五条硬约束 H1–H5（禁止假设 / 咨询必做 / 术语一致 / 来源可追溯 / 多源融合显式标注）、业务规则咨询三知识源、变更分析、生成后五项自评。
- `function_points.md` — 功能点定义（功能点≠需求点）、6 类、分解原则。
- `test_methods.md` — 6 种黑盒测试设计方法及有序叠加。
- `testpoint_checklist.md` — 测试点 5 维度 + **四类场景强制配额**（1 正向 : ≥3 异常·边界 + ≥1 权限）+ 权限校验覆盖清单 + 列表/表单/导入导出/文件上传覆盖清单。
- `case_design.md` — **用例编写规范唯一权威来源**：10 条设计原则 + 四字段编写规范（标题/前置条件/步骤/预期，已合并原 case_fields.md）+ 测试类型转化要点 + 优先级 P0–P3 四级（完整口径见 priority_p0_p3.md）+ 粒度学习要点。
- `naming_rules.md` — 测试用例命名规则：目的与原则 + 7 条强制红线（长度 ≤20 字 / 无预期判定词 / 无序号前缀 / 无【】包裹 / 无冗余前缀 / 术语统一 / 无模糊量词）+ **用例编号规范**（`TC-{模块缩写}-{序号}`、必须显式写 `id`、全局唯一、编号不进标题）。命名评审必查。
- `output_format.md` — Excel 10 列模板规范与字段定义。
- `quality_standards.md` — 四核心质量标准 + 0–100 评分 rubric（定义 + 反面案例 + 评审清单 + 量化评分）。
- `quality_prescreen.md` — 质量预审 10 项清单与阈值、三个检查点。
- `coverage_audit.md` — **用例覆盖率评审（逆向评审）**：两个使用时机（生成后自审 / 存量用例库评审）、三项能力（多格式解析 / 模块级覆盖率 / 三类缺口 G1·G2·G3）、匹配口径（显式标注优先、模块名只作候选）、六节报告结构、**双向追溯（RTM）与 Excel 第二 sheet**（需求→用例 / 用例→需求 / 部分覆盖 / 孤儿用例）、报告如何用（不要平摊工作量）。
- `workflow.md` — 质量保障机制总览：分析 / 预审 / 评分 / 记忆四道闸门如何衔接 + 可选技术加速器（6 步流程细节见本 SKILL.md）。
- `data_rules.md` — 数据-规则映射库（测试数据校验规则）；优先级模型见 `case_design.md` / `priority_p0_p3.md`，评分 rubric 见 `quality_standards.md`。
- `priority_p0_p3.md` — **P0–P3 分级策略**（优先级分级的唯一权威来源）：P0 可行性/概念性测试（横屏主流程 + 竖屏移植等价 + 各端联调）→ P1 主流程必测（横屏 UI 流程图拆解 / 等价类含异常 / 横屏布局适配 / AI 数据准确性 / 设备监控灵敏度 / 数据安全）→ P2 显示完整性 → P3 美观与兼容（旋转布局 / 响应式 / Android·iOS 兼容 / 认证性能）；含五维评分 D1–D5 + 硬规则 R1–R7 + 各级范围/执行/评审/示例 + 质量属性与分端映射 + 分级 SOP。全技能统一采用 P0–P3 四级（无 P4）。
- `multimodal.md` — 多模态读图：UI 图 / 流程图 / 规则表 → 用例的识别映射。
- `excellent_case_patterns.md` — **优秀用例的实证模式**（经验证据层）：从真实优秀用例库（1278 条）反推的 10 个可复制做法 + 生成后自检清单 + 反面清单速查。支撑预审第 7/8 项与 case_design 第六节。
- `memory_mechanism.md` — 记忆机制：记录内容与读取时机、文件格式。

### scripts/
- `read_xmind.py` — Step 1 读取 `.xmind` 需求树（-f tree / -o json），替代 xmind-reader。
- `extract_requirements.py` — Step 1 从 PRD/MD 抽取需求规则清单（默认表格合并到需求陈述级，`--no-merge-tables` 可对照）。
- `read_ui_image.py` — Step 1 多模态读图骨架生成器（校验图片、输出元素抽取 JSON）。
- `map_coverage.py` — 用例 → 需求规则 ID 映射器，输出覆盖率与未覆盖规则。
- `prescreen.py` — Step 5 质量预审闸门（10 项：覆盖率 / P0 / P2 占比 / 方法关联 / 无编造 / 无重复 / 预期可判定 / 标题规范·编号唯一 / 场景构成配额 / 孤儿用例；P0、P2、场景门槛、孤儿上限均可配，支持 6 方法）。
- `coverage_audit.py` — Step 6 覆盖率评审（模块级下钻）：用例 `.json`/`.xlsx` × `requirements.json` → Markdown/JSON 报告，识别 G1 缺失 / G2 场景失衡 / G3 名义覆盖。
- `to_excel.py` — Step 6 用例 JSON → `.xlsx`（10 列），`--emit-template` 生成模板。
- `to_xmind.py` — Step 6 用例 JSON → `.xmind`（可选输出）。
- `score_testcases.py` — Step 6 结构化评分器（4 维逐项判定，任一维度 <90 触发回退）。
- `memory_io.py` — 项目记忆读写器（init / record / load）。
