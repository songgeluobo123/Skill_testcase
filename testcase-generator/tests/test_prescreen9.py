"""prescreen.py 第 9 项（场景构成配额）+ 编号唯一性 回归测试。

一组"规范样例"应零误伤；一组"反例"应逐条命中。
"""
import json
import os
import subprocess
import sys
import tempfile

# 技能目录：可用环境变量 TC_SKILL 覆盖，默认取 tests/ 的上级目录。
# 这样脚本在"本地技能目录"与"仓库克隆副本"两处都能跑，不再依赖本机绝对路径。
SKILL = os.environ.get("TC_SKILL") or os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(SKILL, "scripts", "prescreen.py")
PY = sys.executable


def mk(cid, module, title, pri, ttype, method="等价类划分", rule="R-001"):
    """夹具**只写规范字段 `name`**，不写 `title` 别名。

    2026-11-09 的教训：早期夹具同时写了 name 和 title，比实现更宽容，
    把「prescreen 只认 title、按规范只写 name 的用例被判标题为空」这个真 bug
    盖了几个月。夹具比实现宽松 = 回归失效。
    别名的兼容性由 test_schema_contract.py 专门覆盖，不在这里顺带测。
    """
    return {
        "id": cid, "name": title, "module": module,
        "priority": pri, "test_type": ttype,
        "precondition": "已登录且进入对应页面",
        "steps": f"在页面中执行{title}对应操作并观察结果",
        "expected": "应显示提示文案「操作成功」且列表刷新",
        "test_data": {"账号": "test01"},
        "coverage_rule": rule, "design_method": [method], "stage": "功能测试",
    }


good = []
# 模块A 7 条：正向1 + 异常/边界3 + 权限1 + 其余
for i, (t, tp, p) in enumerate([
    ("正常提交订单", "功能", "P1"),
    ("金额为空提交", "异常", "P1"),
    ("金额超上限提交", "边界", "P1"),
    ("未登录访问订单", "权限", "P0"),
    ("订单状态展示", "功能", "P2"),
    ("订单列表分页", "功能", "P2"),
    ("订单筛选", "功能", "P3"),
], 1):
    good.append(mk(f"TC-ORD-{i:03d}", "订单", t, p, tp))
# 模块B 7 条
for i, (t, tp, p) in enumerate([
    ("正常支付订单", "功能", "P1"),
    ("余额不足支付", "异常", "P1"),
    ("支付金额下限", "边界", "P2"),
    ("无权限支付他人订单", "权限", "P0"),
    ("支付方式展示", "功能", "P2"),
    ("支付结果页", "功能", "P2"),
    ("支付安全键盘", "功能", "P3"),
], 1):
    good.append(mk(f"TC-PAY-{i:03d}", "支付", t, p, tp))
# 模块C 6 条
for i, (t, tp, p) in enumerate([
    ("正常导出报表", "功能", "P1"),
    ("导出空数据报表", "异常", "P1"),
    ("导出超大报表", "边界", "P2"),
    ("无权限导出报表", "权限", "P2"),
    ("报表字段展示", "功能", "P2"),
    ("报表排序", "功能", "P3"),
], 1):
    good.append(mk(f"TC-RPT-{i:03d}", "报表", t, p, tp))

# 反例：模块 D 全正向（应触发第 9 项阻断）+ 重复编号（应触发 8b）
bad = [
    mk("TC-D-001", "订单", "订单查询", "P2", "功能"),
    mk("TC-D-001", "订单", "订单详情", "P2", "功能"),   # 编号重复
    mk("TC-D-002", "订单", "订单删除", "P2", "功能"),
    mk("TC-D-003", "订单", "订单编辑", "P2", "功能"),
    mk("TC-D-004", "订单", "订单新建", "P2", "功能"),
]

rules = [{"id": "R-001", "module": "订单", "type": "included", "text": "订单操作"}]
rul = ["R-001"]  # 只为验证第 8b/9 项，覆盖率用单一规则满足

tmp = tempfile.mkdtemp(prefix="prescreen9_")
rp = os.path.join(tmp, "rules.json")
json.dump(rul, open(rp, "w", encoding="utf-8"), ensure_ascii=False)


def run(cases, name):
    p = os.path.join(tmp, f"{name}.json")
    json.dump(cases, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    r = subprocess.run([PY, SCRIPT, p, "--requirement-rules", rp], capture_output=True, text=True)
    print("=" * 18, name, "=" * 18)
    print(r.stdout.strip()[:2000])
    if r.returncode not in (0, 1):
        print("STDERR:", r.stderr)
    return r


g = run(good, "good")
b = run(bad, "bad")

checks = {
    "规范样例零误伤（exit=0）": g.returncode == 0,
    "规范样例无「无任何异常/边界」误报": "无任何异常/边界用例" not in g.stdout,
    "规范样例编号唯一校验通过": "[✓] 用例编号唯一" in g.stdout,
    "规范样例展示各模块均含异常边界": "各模块均含异常/边界类用例" in g.stdout,
    "反例命中重复编号": "用例编号重复" in b.stdout,
    "反例命中无异常/边界模块": "无任何异常/边界用例" in b.stdout,
    "反例 exit=1": b.returncode == 1,
}
print("\n--- 断言 ---")
for k, v in checks.items():
    print(("PASS " if v else "FAIL ") + k)
print("\n临时目录:", tmp)
