"""coverage_audit.py 回归测试：json 与 xlsx 两条输入路径 + 三张缺口卡片。"""
import json
import os
import subprocess
import sys
import tempfile

# 技能目录：可用环境变量 TC_SKILL 覆盖，默认取 tests/ 的上级目录。
# 这样脚本在"本地技能目录"与"仓库克隆副本"两处都能跑，不再依赖本机绝对路径。
SKILL = os.environ.get("TC_SKILL") or os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(SKILL, "scripts", "coverage_audit.py")
PY = sys.executable

rules = [
    {"id": "R-001", "module": "登录", "type": "included", "text": "输入正确账号密码后登录成功并跳转首页"},
    {"id": "R-002", "module": "登录", "type": "included", "text": "密码错误时提示密码错误且不清空账号"},
    {"id": "R-003", "module": "登录", "type": "included", "text": "未登录用户访问个人中心应跳转登录页"},
    {"id": "R-004", "module": "支付", "type": "included", "text": "支付金额超过单笔上限 5000 元时拒绝下单"},
    {"id": "R-005", "module": "支付", "type": "included", "text": "支付成功后订单状态变更为已支付"},
    {"id": "R-006", "module": "报表", "type": "included", "text": "报表支持按日导出 CSV 文件"},
    {"id": "R-007", "module": "报表", "type": "included", "text": "报表数据与明细列表金额合计一致"},
    {"id": "R-008", "module": "订单", "type": "included", "text": "订单列表支持按状态筛选"},
    {"id": "R-009", "module": "订单", "type": "included", "text": "订单金额为空时提交应提示必填"},
]

cases = [
    # 登录：正向 + 异常 + 权限，齐全
    {"id": "TC-LOGIN-001", "module": "登录", "name": "正确账号密码登录",
     "test_type": "功能", "precondition": "已注册账号",
     "steps": "输入正确账号密码，点击登录", "expected": "应登录成功并跳转首页",
     "coverage_rule": "R-001"},
    {"id": "TC-LOGIN-002", "module": "登录", "name": "密码错误登录",
     "test_type": "异常", "precondition": "已注册账号",
     "steps": "输入正确账号与错误密码，点击登录", "expected": "应提示密码错误，账号不清空",
     "coverage_rule": "R-002"},
    {"id": "TC-LOGIN-003", "module": "登录", "name": "未登录访问个人中心",
     "test_type": "权限", "precondition": "未登录状态",
     "steps": "直接访问个人中心地址", "expected": "应跳转登录页",
     "coverage_rule": "R-003"},
    # 支付：只有正向，缺边界与权限 → G2
    {"id": "TC-PAY-001", "module": "支付", "name": "支付成功订单更新",
     "test_type": "功能", "precondition": "已下单待支付",
     "steps": "完成支付", "expected": "订单状态应为已支付",
     "coverage_rule": "R-005"},
    # 报表：完全没有用例 → G1 零覆盖
    # 订单：有正向 + 异常，但无权限校验 → G2（缺权限）
    {"id": "TC-ORD-001", "module": "订单", "name": "按状态筛选订单",
     "test_type": "功能", "precondition": "已有订单数据",
     "steps": "选择状态已支付，点击筛选", "expected": "列表应只显示已支付订单",
     "coverage_rule": "R-008"},
    {"id": "TC-ORD-002", "module": "订单", "name": "订单金额为空提交",
     "test_type": "异常", "precondition": "进入订单创建页",
     "steps": "金额留空，点击提交", "expected": "应提示金额不能为空",
     "coverage_rule": "R-009"},
]

tmp = tempfile.mkdtemp(prefix="audit_")
rp = os.path.join(tmp, "requirements.json")
cp = os.path.join(tmp, "cases.json")
op = os.path.join(tmp, "report.md")
json.dump(rules, open(rp, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
json.dump(cases, open(cp, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

print("=" * 20, "JSON 输入", "=" * 20)
p = subprocess.run([PY, SCRIPT, cp, rp, "-o", op], capture_output=True, text=True)
print(p.stdout.strip())
print("exit:", p.returncode)
if p.returncode == 0:
    report = open(op, encoding="utf-8").read()
else:
    report = open(op, encoding="utf-8").read() if os.path.exists(op) else ""
    print(p.stderr)

checks = {
    "含报告标题": "# 用例覆盖率评审报告" in report,
    "报表模块零覆盖被标出": "❌ 零覆盖" in report,
    "支付缺异常边界被标出": "❌ 无异常/边界用例" in report,
    "缺失清单含 R-004": "R-004" in report,
    "缺失清单含 R-006": "R-006" in report,
    "给出建议类型": "建议用例类型" in report,
    "给出建议优先级": "建议优先级" in report,
    "订单缺权限校验被标出": "缺权限校验" in report,
    "零用例模块不再重复计缺口": "— 无用例（见 G1）" in report,
    "总结区分两类缺口": "无权限校验" in report,
    "退出码=1": p.returncode == 1,
}
# 说明：json 用例都带显式 coverage_rule，脚本直接采信、不再做弱匹配，
# 因此"疑似覆盖"与"模块名兜底"两项断言放在无 coverage_rule 的 xlsx 输入上验证。
print("\n--- 断言 ---")
for k, v in checks.items():
    print(("PASS " if v else "FAIL ") + k)

# xlsx 输入路径
try:
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.append(["用例编号", "测试模块", "用例名称", "优先级", "测试类型", "前置条件", "测试步骤", "预期结果"])
    ws.append(["TC-LOGIN-001", "登录", "正确账号密码登录", "P0", "功能", "已注册账号",
               "输入正确账号密码，点击登录", "应登录成功并跳转首页"])
    ws.append(["TC-LOGIN-002", "登录", "密码错误登录", "P1", "异常", "已注册账号",
               "输入错误密码，点击登录", "应提示密码错误"])
    ws.append(["TC-LOGIN-003", "登录", "未登录访问个人中心", "P1", "权限", "未登录状态",
               "直接访问个人中心", "应跳转登录页"])
    ws.append(["TC-PAY-001", "支付", "支付成功订单更新", "P0", "功能", "已下单待支付",
               "完成支付", "订单状态应为已支付"])
    xp = os.path.join(tmp, "cases.xlsx")
    wb.save(xp)
    print("\n" + "=" * 20, "XLSX 输入", "=" * 20)
    p2 = subprocess.run([PY, SCRIPT, xp, rp], capture_output=True, text=True)
    ok = "覆盖率概览" in p2.stdout and "报表" in p2.stdout
    print(p2.stdout[:1200])
    print("exit:", p2.returncode)
    print(("PASS " if ok else "FAIL ") + "xlsx 表头识别与报告生成")
    r2 = p2.stdout
    extra = {
        "弱匹配不计入覆盖（标为疑似）": "疑似覆盖（仅模块名相同" in r2,
        "模块名兜底不抬高覆盖率": "| 支付 | 2 | 1 | 50.0% |" in r2,
        "xlsx 无 coverage_rule 仍能匹配": "| 登录 | 3 | 3 | 100.0% |" in r2,
    }
    for k, v in extra.items():
        print(("PASS " if v else "FAIL ") + k)
    if p2.returncode not in (0, 1):
        print(p2.stderr)
except ImportError:
    print("\n[跳过] 当前解释器无 openpyxl，xlsx 路径未测")

print("\n临时目录:", tmp)
