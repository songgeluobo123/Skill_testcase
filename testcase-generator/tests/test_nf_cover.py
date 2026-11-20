"""第 9d 项（非功能五特性覆盖）与 test_type 非功能族值域回归。

背景（实测）：某生成库 745 条用例里 性能 1 条、兼容 9 条、可靠性 0 条、安全性 0 条、
易用性 0 条，而其真实缺陷大头恰好是断连挂死、弱网升级失败、日志明文密码——
非功能维度是缺陷主产区，但生成侧从无规则、预审从不点名。
优秀库本身也缺这四类（回放：兼容/可靠/安全/易用全 0）——所以本判据的依据是
质量模型（ISO 25010）与缺陷反哺，不是优秀库实证。

守住的方向：
  - 五特性各需 ≥1 条，缺类逐项点名；安全组并入权限测试（权限是安全的子集）
  - 小库（< --nf-min-cases）不判，避免误伤
  - 值域含「可靠性测试 / 安全性测试 / 易用性测试」，短写（可靠/安全/易用）经别名归一放行
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
TMP = tempfile.mkdtemp(prefix="nf_cover_")

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


def mk(cid, ttype, module="订单"):
    return {"id": cid, "name": f"用例{cid}", "module": module, "priority": "P1",
            "test_type": ttype, "precondition": "已登录",
            "steps": f"1. 点击按钮{cid}\n2. 查看结果",
            "expected": f"1. 应提示成功{cid}", "test_data": {"账号": "test01"},
            "coverage_rule": "R-001", "design_method": ["场景法"]}


RELAX = ["--coverage-min", "0", "--p0-min", "0", "--p0-max", "1",
         "--p2-min", "0", "--p2-max", "1", "--scene-min-cases", "99",
         "--single-case-mode", "off", "--min-cases-per-rule", "0",
         "--ui-cover-mode", "off"]


def run(cases, tag, extra=()):
    p = os.path.join(TMP, f"{tag}.json")
    json.dump(cases, open(p, "w", encoding="utf-8"), ensure_ascii=False)
    rp = os.path.join(TMP, "rules.json")
    json.dump(["R-001"], open(rp, "w", encoding="utf-8"), ensure_ascii=False)
    return subprocess.run([PY, SCRIPT, p, "--requirement-rules", rp] + RELAX + list(extra),
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace")


# ---------- 一、五特性缺四类 ----------
only_fn = [mk(f"TC-A-{i:03d}", "模块功能测试") for i in range(25)] + \
          [mk("TC-P-001", "性能测试")]
r = run(only_fn, "nf_missing")
check("缺 4 特性 → 逐个点名",
      "非功能覆盖缺失" in r.stdout and "可靠性" in r.stdout and "易用性" in r.stdout,
      r.stdout[-700:])
check("已覆盖特性也一并报数", "性能1条" in r.stdout, r.stdout[-700:])

# ---------- 二、五特性齐全 → 通过 ----------
full = [mk(f"TC-B-{i:03d}", "模块功能测试") for i in range(20)] + [
    mk("TC-NF-1", "性能测试"), mk("TC-NF-2", "兼容测试"),
    mk("TC-NF-3", "可靠性测试"), mk("TC-NF-4", "安全性测试"),
    mk("TC-NF-5", "易用性测试")]
r = run(full, "nf_ok")
check("五特性齐全 → 达标提示", "非功能五特性均有覆盖" in r.stdout, r.stdout[-600:])
check("齐全时不报缺失", "非功能覆盖缺失" not in r.stdout, r.stdout[-600:])

# ---------- 三、权限测试计入安全组 ----------
perm_as_sec = [mk(f"TC-C-{i:03d}", "模块功能测试") for i in range(20)] + [
    mk("TC-NF-1", "性能测试"), mk("TC-NF-2", "兼容测试"),
    mk("TC-NF-3", "可靠性测试"), mk("TC-NF-4", "权限测试"),
    mk("TC-NF-5", "易用性测试")]
r = run(perm_as_sec, "nf_perm")
check("权限测试计入安全组 → 不报安全缺失",
      "非功能五特性均有覆盖" in r.stdout and "[!] 非功能覆盖" not in r.stdout,
      r.stdout[-600:])

# ---------- 四、非功能族值域（9c） ----------
r = run(full, "nf_types_ok")
check("可靠性/安全性/易用性测试 在值域内",
      "test_type 不在值域内" not in r.stdout, r.stdout[-500:])

short = [mk("TC-D-001", "可靠"), mk("TC-D-002", "安全"), mk("TC-D-003", "易用"),
         mk("TC-D-004", "模块功能测试")]
r = run(short, "nf_short")
check("短写（可靠/安全/易用）经别名归一放行",
      "test_type 不在值域内" not in r.stdout, r.stdout[-500:])

# ---------- 五、小库不判 / off / block ----------
small = [mk(f"TC-E-{i:03d}", "模块功能测试") for i in range(10)]
r = run(small, "nf_small")
check("库 <20 条不判非功能", "非功能覆盖" not in r.stdout, r.stdout[-500:])

r = run(only_fn, "nf_off", extra=["--nf-cover-mode", "off"])
check("--nf-cover-mode off 关闭", "非功能覆盖" not in r.stdout, r.stdout[-500:])

r = run(only_fn, "nf_block", extra=["--nf-cover-mode", "block"])
check("block 模式阻断", r.returncode == 1, f"exit={r.returncode}")

print("\n" + "=" * 30)
print(f"通过 {PASS}/{PASS + FAIL}")
if FAILS:
    print("失败:", FAILS)
sys.exit(1 if FAIL else 0)
