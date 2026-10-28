# Changelog

本文件记录 Skills 仓库（WorkBuddy 技能集合）的发布历史。格式参考 [Keep a Changelog](https://keepachangelog.com/)。

## [1.5.0] - 2026-10-28

### 新增

- **双向需求追溯（RTM）+ 孤儿用例检测**（`testcase-generator`）— 在「模块级覆盖率」之外补上需求级、双向的追溯链路：需求→用例查漏测，用例→需求查"为什么存在"。
  - **`scripts/coverage_audit.py`**：新增 `build_rtm()` / `append_rtm_sheet()` / `write_rtm_xlsx()` 与 CLI `--rtm-xlsx`。覆盖状态四分类：**全覆盖**（≥1 条异常/边界/权限用例）、**部分覆盖**（仅有正向用例，不计真覆盖）、**未覆盖**、**孤儿用例**（无 `coverage_rule` 且未标 `exploratory`）；仅模块名相同的记**疑似映射**单列待确认。高优缺口按 P0→P3 置顶。
  - **`scripts/to_excel.py`**：新增 `--with-rtm requirements.json`，把「需求追溯」写为用例 Excel 的**第二个 sheet**（状态着色：未覆盖红 / 部分覆盖黄 / 全覆盖绿，含孤儿与疑似映射区块）。
  - **`scripts/prescreen.py`**：预审 **9 项 → 10 项**，新增第 10 项「孤儿用例」；默认 `--orphan-max 0.0`（**任何孤儿直接阻断**），`exploratory: true` 可豁免，阈值可放宽为告警。
  - **文档**：`references/coverage_audit.md` 新增「四·五 双向追溯（RTM）与 Excel 第二 sheet」；`references/quality_prescreen.md` 更新为 10 项表并补 `--orphan-max` 示例；`SKILL.md` / `README.md` / `workflow.md` 同步口径。
  - **新增 `scripts/selftest_rtm.py`**：覆盖 RTM 状态判定（全覆盖/部分/未覆盖/孤儿/疑似/exploratory 豁免）、Excel 第二 sheet、预审第 10 项阻断，共 16 项断言。

### 修改

- `SKILL.md` Step 6：导出 Excel 增加 `--with-rtm requirements.json`；覆盖率评审增加 `--rtm-xlsx <用例Excel>`。
- 预审项数由 9 项统一更新为 10 项（`SKILL.md` / `references/quality_prescreen.md` / `references/workflow.md` / `README.md`）。

## [1.4.0] - 2026-10-22

### 新增

- **新增技能 `test-case-sorter/`（测试用例流程排序 v3.0）** — 把散乱的用例集合，按**业务执行链路 + 测试点依赖**还原成能照着跑的执行清单。只重排行，不改内容与格式。
  - **五层排序模型**：`分类分区 → 顶级模块 → 功能模块 → 测试点 → 组内次序`。分区解决「公共/横屏专项/竖屏专项」或「公共/BB2/BB3」的同形态集中执行；模块层解决「个人中心跑到训练前面」；测试点层解决「同一页面的用例散落各处」。
  - **六级判定优先级 R1–R6**：R1 分区 → R2 模块（精确匹配 > 最长前缀 > 排末尾）→ R3 顶级端（`sub` 模块内聚块 / `group` 提到模块前 / `weak` 不参与）→ R4 测试点（`priority` 升序试匹配、同值按声明序、`exclude` 否决）→ R5 未命中兜底 → R6 组内（显式序号 > 类型序 > 优先级序 > 原始行号）。同时明确「`rule.priority` 只决定谁先匹配，不决定谁排前面」。
  - **策略有实证依据**：从《测试用例管理.xlsx》（1278 条 / 4 顶级 / 19 模块 / 23 列）反推——某模块 58 条中测试类型切换 21 次、优先级 P0/P2/P4/P3 混排，证明**类型与优先级不是排序主轴**。故 `sort_by_type` / `sort_by_priority` 均默认关闭，只在需要时按模块开启（如该库中唯一做了类型分层的「APP-版本更新」）。
  - **保序兜底（关键取舍）**：未命中规则的用例默认「承接上一个测试点、保持原相对位置」，仅显式 `fallback="tail"` 才排到模块末尾。因为原库顺序本身承载了作者的测试点逻辑，甩到末尾等同于二次打乱。
  - **幂等**：排序键末位固定为原始行号，同一文件反复排序结果逐行一致（已实测两 Sheet × 2431 行完全一致）。
  - **格式保真**：值、样式、行高、超链接、批注、冻结窗格、列宽随行搬迁；超链接若只搬值会「粘」在原行造成错位，已专门处理。
  - **工程能力**：`.xlsx/.xlsm/.json/.csv` 多格式、`--all-sheets` 多表批处理、`--report` 排序依据树、`--dump-unclassified` 待补清单、`--add-seq` 执行序号列、`--inplace` 自动 `.bak`、六项自动自检（内容零改动/条数/模块成块/未归类/缺规则模块/格式）。
  - **配套 10 份实战流程配置**：EQi 智能出行基准配置（1278 条）、AI Coach 软件版（2410 条 / 三分类）、AI Coach 早期版（1393 条）、EQi 三分类/功能模块轴/竖屏专项、E-Bike 人工维护与 PRD 版、层级前缀示例、最小示例。
  - **文档**：`SKILL.md` 含策略来源、判定优先级、排序键定义、功能范围、输入输出约定、12 类边界与异常场景行为表、三步收敛工作流；`README.md` 为面向使用者的快速上手与配置要点。

### 修改

- **`README.md`** — 技能集合表新增 `test-case-sorter/` 一行。

## [1.3.0] - 2026-10-21

### 新增

- **`references/coverage_audit.md` + `scripts/coverage_audit.py`（用例覆盖率评审 / 逆向评审）** — 补齐「拿已有用例库回审需求」这条逆向链路，回答"哪个模块漏得最多、缺什么类型的用例"：
  - **两个使用时机**：生成后自审（Step 6 可选）· 存量用例库评审（接手项目 / 版本回归前）。
  - **多格式输入**：用例支持 `.json` 与 `.xlsx`（自动识别中文表头，存量库无需先补 `coverage_rule`）；需求用 `extract_requirements.py` 产出的 `requirements.json`。
  - **模块级覆盖率**：`模块覆盖率 = 已覆盖规则 / 该模块规则总数`，阈值默认 70%（`--module-min`），低于即列「重点补充对象」。
  - **三类缺口**：**G1 需求有、用例无**；**G2 覆盖了但场景失衡**（模块无异常/边界，或负向用例里无权限校验）；**G3 名义覆盖**（1 条用例挂多条规则，颗粒度撑不住）。
  - **匹配口径（防假阳性的关键）**：显式 `coverage_rule` 优先采信；文本 bigram Jaccard ≥ 阈值计**强匹配**；**仅模块名相同只记为「疑似覆盖」单列待人工确认，不计入覆盖率**——否则任何同模块用例都会"覆盖"同模块所有规则，覆盖率虚高、报告失去意义。
  - **六节报告**：覆盖率概览（表）· 低覆盖模块 · 缺失清单（含建议用例类型与建议优先级）· 场景构成缺口 · 名义覆盖风险 · 总结与建议。支持 `--format json` 供流水线消费。
  - 回归验证 15 项断言全过：JSON/XLSX 双输入、零覆盖模块、无异常边界模块、缺权限模块、疑似覆盖、模块名兜底不抬高覆盖率、退出码语义。

### 修改

- **`scripts/prescreen.py`：预审 8 项 → 9 项** —
  - 新增**第 9 项「场景构成配额」**：按模块统计正向 / 异常·边界 / 权限三类；模块用例数 ≥ `--scene-min-cases`（默认 4）且**无任何异常/边界/权限用例 → 阻断**；负向偏少（`负/正 < 1/3`）或缺权限校验类仅告警。
  - 第 8 项增补**用例编号唯一性**：重复编号即阻断（编号是缺陷挂单 / 覆盖率映射 / 备注注入的追溯锚点）。
  - 回归验证：20 条规范样例零误伤（exit 0），反例逐条命中重复编号与无异常/边界模块。
- **`references/testpoint_checklist.md`：新增「四类场景强制配额」**（位于五维度之后，原二/三节顺延为三/四）——每功能点 **正常流程 ≥1 条 · 异常操作 + 边界条件合计 ≥3 条 · 权限校验 ≥1 条**；并新增「权限校验覆盖清单」（未登录 / 无权限 / 跨角色 / 横向纵向越权 / 权限变更即时性）；无账号体系的离线产品可豁免但须写明理由。
- **`references/naming_rules.md`：新增「用例编号规范」**（第三节）——`TC-{模块缩写}-{3 位序号}`（如 `TC-LOGIN-001` / `TC-C00-003`）；**必须显式写 `id`**（默认顺序号会随增删整体漂移，导致历史缺陷单号对不上）；全局唯一；编号不进标题。
- `references/quality_prescreen.md` — 8 项 → 9 项清单，补第 9 项规则与 `--scene-min-cases` 示例。
- `references/workflow.md` — 预审检查项数同步为 9；新增「补充：模块级下钻」说明（`coverage_audit.py` 是诊断工具，不是闸门）。
- `SKILL.md` — Step 3 补四类场景配额；Step 5 预审改 9 项；Step 6 新增第 5 步「可选：覆盖率评审」与第 6 步记忆写入；「它解决什么」表新增「如何证明没测漏」一行；资源索引新增 `coverage_audit.md` / `coverage_audit.py`，`naming_rules.md`、`testpoint_checklist.md`、`quality_prescreen.md`、`workflow.md` 描述同步；门禁排障速查新增第 15 条（第 9 项整模块报错与覆盖率"假覆盖"的处理）。
- `README.md` / `README.en.md` — 特性新增「四类场景配额」「覆盖率评审（逆向）」；目录 references 16→17 篇、scripts 9→10 个；分层表 `coverage_audit.md` 归入 E 质量保障；6 步工作流表第③⑥步产出同步；快速开始新增 4b 覆盖率评审命令。

### 说明

- 本次不改变既有优先级口径（仍以 `priority_p0_p3.md` 唯一权威）、不改变用例字段写法（`case_design.md` 唯一权威）、不动分析闸门与预审其余 7 项阈值。
- 第 9 项对**小模块**（用例数 < 4）不判定负向缺失，属故意设计：避免为"消灭告警"硬塞低价值异常用例。
- 覆盖率评审的「建议用例类型 / 建议优先级」是文本推断的**推荐值**，最终定级仍以五维评分 + R1–R7 为准。

## [1.2.0] - 2026-10-21

### 新增

- **`references/analysis_gate.md`（分析闸门：两阶段流程 + 硬约束）** — 参考业界 `test-case-design` 类实践（分析报告 → 用户确认 → 生成 的硬闸门），与本技能既有检查点机制融合，把"分析"与"生成"硬性分开：
  - **两阶段流程**：阶段 1 分析（输入解析 → 多源获取 → 业务规则咨询 → 产出《测试分析报告》）→ 🚧 **STOP & ASK 硬闸门** → 阶段 2 生成（设计规范 → 自评 → 落盘 JSON → 导出 Excel → 总结报告）。确认前禁止进入生成、禁止产出 `test_cases.json`、禁止导出 Excel。
  - **《测试分析报告》六节模板**：输入确认 / 关键要点（每条带来源）/ 信息缺口待澄清 / 建议测试范围与 P0–P3 优先级 / 设计方法预选 / 待办 A–B。
  - **五条硬约束 H1–H5**：H1 禁止假设（缺口只进待澄清，最多标 `[假设]` 待确认）· H2 业务规则咨询必须执行 · H3 术语一致性（服务名/接口名/字段名/错误码原样保留）· H4 来源可追溯（章节/URL/知识库条目/MR 号/需求规则 ID）· H5 多源融合须显式标注"由 XX 补充"。
  - **业务规则咨询三知识源**（项目记忆 → 既有用例库/知识库 → 需求资料）+ 固定问题两句 + 动态缺口逐条提问；三源皆无答案时须声明"无既有知识可用"，**不得用通用经验填充**。
  - **变更分析**（可选，有 MR/diff 时）：受影响逻辑 → 补调用例 → 备注标 `来源：MR !123`。
  - **生成后五项自评**（与预审互补）：优先级是否覆盖最高风险点 / 术语是否保留原文 / 是否混入未确认假设 / 正负向与边界是否齐备且同构组 ≥3 / 每条能否指回需求规则 ID。
  - **阶段 2 固定四交付物**：用例 JSON · Excel（单文件覆盖原文件）· 总结报告（含"咨询回顾"如实记录哪些问题拿到有效信息）· 分析报告终稿留档。
- **`scripts/to_excel.py` 新增 `--with-remark`（备注列 / 场景展开模式）** — 针对**范围性用例**（一条用例需逐个构造/遍历多个并列子场景，步骤含 `逐一/逐个/依次/分别/遍历/逐项/逐条`）在末列追加「备注」列，承载子场景展开；可与 `--with-environment` 叠加（此时 12 列）。配套 `references/output_format.md` 新增「可选 11 列变体：备注列」章节，给出三段式结构（`【场景展开·N 项】总述` → `序号) 场景名：操作 → 观测点` → `【判定】通过标准`）与"子场景清单必须回需求源表取、非范围性用例留空"两条纪律。
- **`SKILL.md` 门禁排障速查由 6 条扩至 14 条** — 新增 8 条实战踩坑：8) `title`/`name` 字段双写（否则预审报标题全空）；9) `test_data` 不能为空（否则可执行性封顶 80 分）；10) 步骤含"正确"与预期含"失败/错误"被判矛盾致准确率 40；11) 「适用阶段」列只允许四值；12) 无屏设备/协议类项目需另设优先级阈值；13) 范围性用例补备注列做场景展开（含识别口径与可重跑落地方式）；14) 导出时目标 xlsx 被本地预览器占用导致 `PermissionError` 的处理链。

### 修改

- `SKILL.md` — 「六步工作流」头部声明两阶段划分与 STOP & ASK；Step 1 第 5 步改写为「业务规则咨询」、新增第 6 步「产出《测试分析报告》」，并内嵌硬闸门与五条硬约束摘要；Step 1 输出改为《测试分析报告》；Step 6 导出命令补充 `--with-remark`；资源索引新增 `analysis_gate.md`。
- `references/workflow.md` — 「三道质量闸门」扩为**四道闸门**（新增"分析闸门"位于 Step 1 出口，作用为"方向闸门"）；检查点由两处扩为三处（新增**检查点⓪**：《测试分析报告》确认）。
- `references/quality_prescreen.md` — 检查点列表同步增加检查点⓪。
- `README.md` / `README.en.md` — 特性条目新增"分析闸门（两阶段）"；目录结构 references 15→16 篇，新增分层「F. 流程闸门」；6 步工作流表第①步产出补《测试分析报告》与 STOP & ASK 标注。

### 说明

- 本次改动只增加**流程闸门与约束**，不改变用例字段写法（仍以 `case_design.md` 为唯一权威）、不改动优先级口径（仍以 `priority_p0_p3.md` 为唯一权威）、不改动预审 8 项与评分 4 维阈值。
- 用户在一句话指令里已明确授权"按此范围直接生成、不必再确认"时，可跳过等待，但仍须先产出报告并随交付附上。

## [1.1.0] - 2026-09-17

### 新增

- **`references/excellent_case_patterns.md`（优秀用例实证模式）** — 从一份真实优秀用例库（EQI 智能出行，1278 条，跨 APP / 嵌入式固件 / 联调功能 / 系统后台 4 个技术域）逐行统计反推出的可复制做法，作为技能的经验证据层：
  - 10 个可复制做法：双前置列分离（测试环境 53 个模板值覆盖 1271 条）、步骤动词白名单、预期"应…"断言化（83%）与 UI 清单/数值/逐字文案三形态、同构组批量产出（等价类/边界/权限矩阵/多入口/多模式 ≥3 条）、标题句式、非功能"场景化前置 + 量化预期 + 数据外置"三件套、维度标签均衡、行内缺陷闭环、优先级纪律、生成即体检。
  - 生成后自检清单（9 项）+ 反面清单速查（不可判定预期、条件堆进标题、实际结果填执行困难、无唯一 ID 致重名、维度列大面为空、占位残留入库、枚举顺序不统一、前置条件碎片化）。

### 修改

- **`scripts/prescreen.py`：预审由 6 项扩至 8 项** — 新增第 7 项「预期结果可判定」（不可判定词 `合理/美观/友好/流畅/良好/正常显示/工整/尽量/适当/无异常` 一票否决、预期为空即阻断、缺断言标志仅告警）与第 8 项「标题规范与残缺」（≤20 字 / 无序号前缀 / 无【】 / 无句末标点；`steps` 为空阻断；占位残留 `（待XX更新）/TBD/XXX` 阻断；同模块重名仅告警）。已用正反两组样例回归：规范样例零误伤，反例逐条命中。
- **`scripts/to_excel.py`：新增 `--with-environment`** — 导出 11 列变体，在「前置条件」前插入「测试环境」列实现"双前置列"；默认仍为 10 列，模板导出同样支持该开关。
- `references/case_design.md` — 原则 10 增加"禁止不可判定词"硬约束；「二、四 预期结果」补充可判定的三种写法；新增「六、优秀用例的实证模式（生成时强制引用）」6 条。
- `references/quality_prescreen.md` — 检查清单由 6 项更新为 8 项（含第 7/8 项规则与处理方式）。
- `references/output_format.md` — 新增「可选 11 列变体：双前置列（--with-environment）」章节与两列语义边界。
- `references/workflow.md` — 预审闸门描述同步为 8 项。
- `SKILL.md` — Step 5 增加 6 条写法强制要求（双前置列/动词白名单/预期断言化/同构组/非功能三件套/维度均衡）；Step 6 导出命令补充 `--with-environment`；资源索引新增 `excellent_case_patterns.md`；门禁排障速查新增第 7 条（第 7/8 项批量报错的处理）。
- `README.md` / `README.en.md` — 特性条目、目录结构（references 14→15 篇）、分层职责表同步。

## [1.0.6] - 2026-09-07

### 修改

- **分级口径残留修正**：`SKILL.md`「门禁排障速查 → 3. 优先级分布卡闸门」中“先杀 P0（保留核心业务流 + 安全相关）”改为“保留横屏主流程 + 竖屏移植等价 + 各端联调”，消除与新口径（数据安全属 P1）的冲突。
- 同步补推此前仅在本地的「门禁排障速查（踩坑记录）」章节（6 条：进程替换传参失败、coverage_rule 空导致 0 分、分布卡闸门、中文正则失效、点击歧义扣分、必须重跑生成脚本）。

## [1.0.5] - 2026-09-07

### 修改

- **`testcase-generator` 分级口径收口（控制面补全四级名称）**：`SKILL.md` 资源索引与四核心质量标准「优先级合理」条目、`README.md` / `README.en.md` 特性条目补充四级语义名称（P0 可行性/概念性测试、P1 主流程必测、P2 显示完整性、P3 美观与兼容），与 `references/priority_p0_p3.md` 新口径一致；未新增规则，仅让控制面可见分级语义。

## [1.0.4] - 2026-08-31

### 修改

- **`testcase-generator` 测试分级标准重定义（P0–P3 横屏版口径）** — 以 `references/priority_p0_p3.md`（优先级分级唯一权威来源）为准，按横屏版产品重新定义四级语义并全技能同步：
  - P0（可行性/概念性测试）：横屏版主流程功能（用户基本使用流程、横屏主界面与关键交互）、竖屏功能移植横屏后的等价可用性、各端联调测试。
  - P1（主流程必测）：按主流程步骤逐步拆解的必须执行功能（依据横屏 UI 流程图）、等价类相关功能（含异常执行场景）、横屏布局与适配、AI 数据准确性、设备监控灵敏度、数据安全。
  - P2（显示完整性）：横屏界面 UI 显示完整性、不影响主流程的基本功能（控件不遮挡、不溢出）。
  - P3（美观与兼容）：UI 显示正确性与布局美观（文字/Logo/图片/按钮/链接、旋转后布局）、横屏响应式、Android 与 iOS 版本兼容、产品认证标准性能测试。
  - `priority_p0_p3.md`：分级总览、硬规则决策表（R1–R7 全部改写）、各级详细定义、质量属性映射、各端映射、评分示例、速查卡全部对齐新口径；保留"唯一权威来源、无 P4、五维评分 D1–D5、占比建议、执行轮次、分级 SOP"框架不变。
  - `README.md` / `README.en.md` / `references/case_design.md` / `references/quality_prescreen.md`：分级总览表与口径描述同步更新。

## [1.0.3] - 2026-08-10

### 修改

- **`testcase-generator` 优先级文档修正（README 为主）** — 以 `references/priority_p0_p3.md`（P0–P3 四级、无 P4，优先级分级唯一权威来源）为准，统一全技能优先级表述与执行顺序：
  - `README.md` / `README.en.md`：特性条目去除“安全攸关场景自动上调 P0 占比 / auto-escalate P0 share”的错误表述（实为检查点①手动确认的阈值）；新增「优先级模型 / Priority model（P0–P3 四级）」小节，含各级范围 / 执行要求 / 占比建议（P0 10–15%、P1 25–35%、P2 35–45%、P3 10–20%）与执行顺序（冒烟 = P0 → 主测试 SIT = P0+P1 → 回归 = P0+P1+抽样P2 → 全量/探索 = P0~P3）。
  - `references/case_design.md`：删除与权威五维评分模型（D1–D5 + R1–R7 硬规则）不一致的“业务影响度 × 用户频率”二因子映射，改指向 `priority_p0_p3.md` 为唯一定级口径。
  - 校验：全仓库 grep 确认无残留“自动上调 / auto-escalate”与二因子映射；`scripts/prescreen.py` 实证 `PRIORITIES = {P0,P1,P2,P3}`，与文档一致。

## [1.0.2] - 2026-08-10

### 修改
- **`testcase-generator` 质量评分规则：每项维度均需 ≥90**：将合格判定口径由"总分过线"收紧为"每个质量维度均须 ≥ 阈值（默认 90）"，任一维度不足即判定不通过并回退重生成。
  - `scripts/score_testcases.py`：合格判定由"总分 < --threshold 不通过"改为"任一维度 breakdown < --threshold 即不通过"；`--threshold` 默认值 70→90，语义变为"每个维度合格阈值"；输出增加维度低于阈值的 `⚠低于阈值` 标注；退出码 0/1 语义同步为"每维是否达标"。
  - `references/quality_standards.md`：评级动作由"≥70 通过 / <70 不通过"改为"每个维度均 ≥90 通过 / 任一维度 <90 不通过"。
  - `SKILL.md` / `README.md` / `README.en.md`：同步"每项维度需 ≥90，任一不足回退"说明，抹掉残留的"<70 触发回退"旧表述。

### 维护
- **统一仓库行尾为 LF**（提交 `48433c9`）：新增 `.gitattributes`（`* text=auto eol=lf`），消除 Windows 下 CRLF 转换警告，仓库内文件统一以 LF 存储。

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
- **`testcase-generator` 四字段编写规范**：新增 `references/case_fields.md`，定义用例「标题 / 前置条件 / 测试步骤 / 预期结果」四字段编写规则，用于优化用例生成逻辑。
  - 标题：三种写法（功能点 / 功能-流程 / 状态-结果）+ 模块名结合 + 锁定中心点
  - 前置条件：确定方法（保留关键步骤、之前内容归纳前置）+ 四大典型场景 + 两大原则（条件成立且能支撑后续步骤）
  - 测试步骤：线性操作、无「和/或/且」连词、不含预期、页面/按钮明确
  - 预期结果：检查点、至少 1 条、可验证表现（界面 / 数据 / 文件）
  - 新增「生成时字段联动自检」链路，使四字段一致、不重不漏
  - 同步在 `SKILL.md` 的 references 索引、Step 4 编写习惯、Step 5 用例设计中引用该文件

- **`testcase-generator` 技能结构重构（去重与分层）**：将 `case_fields.md` 四字段规范合并进 `case_design.md`（后者成为用例编写规范唯一权威来源），删除冗余 `case_fields.md`；`data_rules.md` 移除重复的优先级模型与评分 rubric（分别收敛至 `case_design.md` / `priority_p0_p3.md` / `quality_standards.md`）；`workflow.md` 由 6 步复述改为质量保障机制总览；`output_format.md` / `testpoint_checklist.md` 去除与 `case_design.md` 重复的规则、改为引用。明确控制面 / 编写规范 / 方法论 / 优先级 / 数据规则 / 质量保障 六层职责边界（单一真相源）。

- **移除 P1-P4 优先级体系，统一为 P0-P3 四级**：删除 `case_design.md` 中的 P1-P4 分级表与 P0->P1 归一映射；`priority_p0_p3.md` 定为优先级分级唯一权威（移除与 P1-P4 的映射章节）。`output_format.md` / `SKILL.md` / `data_rules.md` / `quality_prescreen.md` / `quality_standards.md` / `README(.en)` 同步改为 P0-P3；脚本 `to_excel.py` / `to_xmind.py` / `prescreen.py` / `score_testcases.py` 移除 P0->P1 归一逻辑与 P4 校验集合，改为仅接受 P0-P3，且预审最高优先级闸门由 P1 调整为 P0（`--p0-min`/`--p0-max`）。


### 修复
- **`testcase-generator` 一致性检测修复（本地检测、本次补提交）**：全面检测技能全目录，修正一处致命脚本 bug 与多项口径 / 术语不一致。
  - **致命 bug**：`quality_prescreen.md` 示例命令误用 `--p1-min/--p1-max`，但 `prescreen.py` 无此参数（仅接受 `--p0-min/--p0-max`、`--p2-min/--p2-max`），原命令会直接报错；已改为 `--p0-min 0.40 --p0-max 0.60` 并实测通过。
  - **优先级口径对齐**：`priority_p0_p3.md`（唯一权威）规定 P2 占 35%~45%，但 `quality_prescreen.md` 与 `prescreen.py` 默认 30%~40%；已统一为 35%~45%（脚本默认 `p2_min`/`p2_max`=0.35/0.45）。
  - **术语一致**：`workflow.md` / `quality_prescreen.md` "上调 P1 占比" → "上调 P0 占比"；`quality_prescreen.md` "Stage 2/4 出口"、`xmind_output.md` "Stage 4 产出"、`extract_requirements.py` / `memory_io.py` 注释"Stage 1/2/4/5" → 统一为六步工作流的 "Step"。
  - **笔误 / 残留**：`test_methods.md` 删除残留"见 `quality_prescreen.md` 之前的实现"乱尾引用；`README.md` "Excel（9→10 列）" → "Excel（10 列）"；`README.en.md` "Stage1" → "Step1"；`data_rules.md` 优先级收敛指向由 `case_design.md` 改为 `priority_p0_p3.md`（真正权威源）；`output_format.md` 示例"正确密码登录"优先级 P1 → P0（符合 R4 核心冒烟）；`SKILL.md` 清理对不存在的 `scripts/testpoint_md.py` 的强制引用（保留可扩展说明）。

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

[1.0.6]: https://github.com/songgeluobo123/Skill_testcase/releases/tag/v1.0.6
[1.0.5]: https://github.com/songgeluobo123/Skill_testcase/releases/tag/v1.0.5
[1.0.4]: https://github.com/songgeluobo123/Skill_testcase/releases/tag/v1.0.4
[1.0.3]: https://github.com/songgeluobo123/Skill_testcase/releases/tag/v1.0.3
[1.0.2]: https://github.com/songgeluobo123/Skill_testcase/releases/tag/v1.0.2
[1.0.1]: https://github.com/songgeluobo123/Skill_testcase/releases/tag/v1.0.1
[1.0.0]: https://github.com/songgeluobo123/Skill_testcase/releases/tag/v1.0.0

[1.1.0]: https://github.com/songgeluobo123/Skill_testcase/releases/tag/v1.1.0
