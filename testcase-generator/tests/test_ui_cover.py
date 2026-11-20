"""第 9b 项（UI 覆盖分布）回归。

判据来源：某生成库 **745 条 UI 族 = 0 条**（test_type 全是功能/异常/边界/权限），
而预审当时全绿——因为 7b 只查「UI 族用例的预期质量」，库里一条 UI 族都没有时它就哑了。
优秀库基线：页面交互型模块 UI 占比 47%~88%、设备/流程类 30%+、纯后台模块（版本更新/
下载/物模型）为 0 —— 所以判据是「占比 <10% 且模块 ≥20 条」+ 整库零 UI 兜底 + 模块豁免。
"""
import json
import os
import subprocess
import sys
import tempfile

SKILL = os.environ.get("TC_SKILL") or os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(SKILL, "scripts", "prescreen.py")
PY = sys.executable
TMP = tempfile.mkdtemp(prefix="ui_cover_")

PASS = FAIL = 0
FAILS = []


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"PASS {name}")
    else:
        FAIL += 1
        FAILS.append(name)
        print(f"FAIL {name}  {detail}")


def mk(cid, module="订单", ttype="模块功能测试"):
    return {"id": cid, "name": "功能用例", "module": module, "priority": "P1",
            "test_type": ttype, "precondition": "已登录",
            "steps": "1. 点击按钮\n2. 查看结果", "expected": "1. 应提示成功",
            "test_data": {"账号": "test01"}, "coverage_rule": "R-001",
            "design_method": ["场景法"]}


RELAX = ["--coverage-min", "0", "--p0-min", "0", "--p0-max", "1",
         "--p2-min", "0", "--p2-max", "1", "--scene-min-cases", "99",
         "--single-case-mode", "off", "--min-cases-per-rule", "0"]


def run(cases, tag, extra=()):
    p = os.path.join(TMP, f"{tag}.json")
    json.dump(cases, open(p, "w", encoding="utf-8"), ensure_ascii=False)
    rp = os.path.join(TMP, "rules.json")
    json.dump(["R-001"], open(rp, "w", encoding="utf-8"), ensure_ascii=False)
    return subprocess.run([PY, SCRIPT, p] + RELAX + ["--requirement-rules", rp] + list(extra),
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace")


# ---------- 一、整库零 UI（实测场景复现）----------
# 30 条功能用例、0 条 UI 族 → 整库级命中（≥50 用例才触发整库判据，这里用模块级抓）
zero = ([mk(f"TC-A-{i:03d}", "订单") for i in range(25)]
        + [mk(f"TC-B-{i:03d}", "个人中心") for i in range(25)])
r = run(zero, "zero_ui")
check("整库零 UI → 告警点名", "UI 覆盖缺失" in r.stdout and "UI 族用例为 0 条" in r.stdout,
      r.stdout[-700:])
check("零 UI 模块被逐个列出", "订单(0/25" in r.stdout and "个人中心(0/25" in r.stdout,
      r.stdout[-700:])

# ---------- 二、占比达标 → 通过提示 ----------
mixed = ([mk(f"TC-C-{i:03d}", "订单") for i in range(20)]
         + [mk(f"TC-D-{i:03d}", "订单", "界面交互测试") for i in range(3)]
         + [mk(f"TC-E-{i:03d}", "订单", "UI测试") for i in range(1)])
# 订单 24 条、UI 4 条 = 17% ≥ 10%
r = run(mixed, "ui_ok")
check("模块 UI 占比 ≥ 下限 → 达标提示", "UI 覆盖达标" in r.stdout, r.stdout[-500:])
check("占比达标时不报缺失", "UI 覆盖缺失" not in r.stdout, r.stdout[-500:])

# ---------- 三、豁免模块 ----------
r = run(zero, "ui_exempt", extra=["--ui-exempt-modules", "订单,个人中心"])
check("豁免模块后不报", "UI 覆盖缺失" not in r.stdout, r.stdout[-500:])

# ---------- 四、小模块不判（< --ui-min-cases） ----------
small = [mk(f"TC-F-{i:03d}", "小模块") for i in range(10)]
r = run(small, "small_module")
check("模块 <20 条不触发占比检查", "UI 覆盖缺失" not in r.stdout, r.stdout[-500:])

# ---------- 五、off 关闭 ----------
r = run(zero, "ui_off", extra=["--ui-cover-mode", "off"])
check("--ui-cover-mode off 关闭", "UI 覆盖缺失" not in r.stdout, r.stdout[-500:])

# ---------- 六、block 模式阻断 ----------
r = run(zero, "ui_block", extra=["--ui-cover-mode", "block"])
check("block 模式阻断", r.returncode == 1, f"exit={r.returncode}")

# ---------- 七、整库判据的 50 条门槛 ----------
few = [mk(f"TC-G-{i:03d}", "订单") for i in range(15)]
r = run(few, "small_lib")
check("整库 <50 条且模块 <20 条 → 不误报", "UI 覆盖缺失" not in r.stdout, r.stdout[-500:])


# ---------- 八、9c test_type 值域校验 ----------
# SKILL.md 定义了「两族并存，不得自造」，但没有闸门执行 = 规则没长在必经之路上。
# 历史短写法（「功能」「异常」…）经 TT_ALIAS 归一后放行——test_prescreen9 夹具即用短写。
ok_tt = [mk("TC-H-001", "订单", "模块功能测试"), mk("TC-H-002", "订单", "功能"),
         mk("TC-H-003", "订单", "异常"), mk("TC-H-004", "订单", "界面交互测试")]
r = run(ok_tt, "tt_ok")
check("9c 合法类型（含短写归一）→ 通过", "test_type 不在值域内" not in r.stdout,
      r.stdout[-500:])

bad_tt = [mk("TC-I-001", "订单", "稳定性测试"), mk("TC-I-002", "订单", "功能测试")]
r = run(bad_tt, "tt_bad")
check("9c 自造类型（稳定性测试）→ 拦截并点名",
      "test_type 不在值域内" in r.stdout and "TC-I-001" in r.stdout
      and "稳定性测试" in r.stdout, r.stdout[-600:])
check("9c 拦截为 fail（阻断）", r.returncode == 1, f"exit={r.returncode}")

r = run(bad_tt, "tt_off", extra=["--ttype-mode", "off"])
check("9c --ttype-mode off 关闭", "test_type 不在值域内" not in r.stdout, r.stdout[-500:])

print("\n" + "=" * 30)
print(f"通过 {PASS}/{PASS + FAIL}")
if FAILS:
    print("失败:", FAILS)
sys.exit(1 if FAIL else 0)
