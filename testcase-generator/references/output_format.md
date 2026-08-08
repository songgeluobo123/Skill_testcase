# 输出格式规范（Excel 10 列模板）

Step 6 的强制主产物是 `.xlsx`，列定义如下。**打开即测试用例，无需二次整理。**

> 本文件只定义**列的容器与 JSON 字段映射**。每列"怎么写"（标题/前置/步骤/预期的写法与红线）见 `case_design.md` 四字段规范与 `naming_rules.md`，优先级口径见 `case_design.md` / `priority_p0_p3.md`，避免在此重复规定写法。

## 列定义（必需 8 项 + 质量追溯 2 项）

| 序号 | 列名 | 说明 | 来源字段 | 是否必需 |
|---|---|---|---|---|
| 1 | **用例编号** | 自动生成 `TC-001` 顺序号；用例 JSON 含 `id` 时优先用 `id` | `id` 或自动 | 必需 |
| 2 | **测试模块** | `/平台/模块` 路径 | `module` | 必需 |
| 3 | **用例名称** | 精简 ≤20 字；命名红线见 `naming_rules.md` | `name` | 必需 |
| 4 | **优先级** | P0 / P1 / P2 / P3（四级，统一口径见 `priority_p0_p3.md`） | `priority` | 必需 |
| 5 | **测试类型** | 功能测试 / 异常测试 / 边界测试 / 接口测试 / 兼容性测试 / 性能测试 等 | `test_type` | 必需（缺省"功能测试"） |
| 6 | **前置条件** | 1. 2. 3. 编号，换行分隔 | `precondition` | 必需 |
| 7 | **测试步骤** | 1. 2. 3. 编号，换行分隔 | `steps` | 必需 |
| 8 | **预期结果** | 与步骤一一对应，换行分隔 | `expected` | 必需 |
| 9 | **适用阶段** | 功能测试 / 集成测试 / 系统测试 / 回归测试（质量追溯） | `stage` | 可选（缺省"功能测试"） |
| 10 | **设计方法** | 用了什么方法得出的（6 方法之一或多，如 `等价类划分 / 边界值分析`，质量追溯） | `design_method` | 可选但建议 |

> 第 1–8 列为测试用例的标准必备元素；第 9–10 列为本技能的质量追溯列（覆盖阶段与设计方法可追溯），与 `prescreen.py` 的方法关联闸门、`score_testcases.py` 的评分相互印证。
> 若项目只需标准 8 列，导出后可手动隐藏第 9–10 列，不影响其它列。

## 格式硬约束（Excel 容器相关，非写法）

- 前置条件、测试步骤、预期结果：使用**实际换行**，不是 `\n` 字符。
- 测试步骤与预期结果严格一一对应（步骤数 = 预期数，写法详见 `case_design.md` 四字段规范）。
- 用例编号全局唯一、稳定（同一份 JSON 多次导出顺序一致）。
- 用例命名红线、优先级口径、预期可验证等**内容写法**见 `case_design.md` / `naming_rules.md`，不在此重复规定。

## 生成方式

```bash
# 由结构化用例 JSON 生成 xlsx（10 列）
python scripts/to_excel.py test_cases.json -o "test_output/v1.11 功能测试用例.xlsx"

# 仅生成空白模板（对照历史编写习惯）
python scripts/to_excel.py --emit-template "test-case-design/examples/testcases/模板.xlsx"
```

## 输入 JSON 字段（Step 5/6 结构化）

```json
{
  "cases": [
    {
      "id": "TC-001",
      "module": "登录",
      "name": "正确密码登录",
      "priority": "P1",
      "test_type": "功能测试",
      "precondition": "1. 用户已注册\n2. 网络正常",
      "steps": "1. 在登录页输入已注册手机号\n2. 输入正确密码\n3. 点击登录按钮",
      "expected": "1. 手机号输入框接受输入\n2. 密码输入框掩码显示\n3. 跳转至首页",
      "test_data": { "手机号": "13800138000", "密码": "Test@123" },
      "coverage_rule": "R-003",
      "design_method": ["场景法", "等价类划分"],
      "stage": "功能测试"
    }
  ]
}
```

> 说明：`id / test_type / stage` 为可选展示字段；`module / name / priority / precondition / steps / expected` 为必需；
> `test_data / coverage_rule / design_method` 供质量预审（`prescreen.py`）与覆盖分析（`map_coverage.py`）使用。
