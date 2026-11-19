"""第 11b（单例规则）/ 11c（回归用例分离）/ 覆盖率审计模块名归集 回归。

三个判据都来自同一份真实失败复盘（用例数量归因分析）：
  - 87 条需求规则里 **38 条只有 1 条用例**，其中 27 条是有状态机/枚举的实质功能
    ——不是"需求简单"，是**没往下拆功能点**。密度阈值 ≥6 一刀切会误伤简单需求，
    所以单独盯"只有 1 条且没豁免"。
  - 553 条里 **381 条是存量回归**，挂在 10 条回归规则上；混算会把覆盖量虚胖 3 倍
    （真实覆盖只有 172 条 / 87 条规则 = 1.98 条/规则）。
  - 需求侧写「APP 系统设置」、用例侧叫「App 设置与个人中心」，规则其实覆盖了，
    只是模块名对不上 → 报告打成"无异常/边界用例"，让人去补早就有的用例。

每个断言只让目标项可能失败：其余闸门一律放宽。
"""
import json
import os
import subprocess
import sys
import tempfile

SKILL = os.environ.get("TC_SKILL") or os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(SKILL, "scripts", "prescreen.py")
AUDIT = os.path.join(SKILL, "scripts", "coverage_audit.py")
PY = sys.executable
TMP = tempfile.mkdtemp(prefix="density_caliber_")

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


RELAX = ["--coverage-min", "0", "--p0-min", "0", "--p0-max", "1",
         "--p2-min", "0", "--p2-max", "1", "--scene-min-cases", "99"]


def mk(cid, rule, n=1, module="订单"):
    return {"id": cid, "name": f"用例{cid}", "module": module, "priority": "P1",
            "test_type": "功能测试", "precondition": "已登录",
            "steps": "1. 进入页面\n2. 点击按钮\n3. 查看结果",
            "expected": "1. 页面应加载完成\n2. 应提示「操作成功」\n3. 列表应刷新",
            "test_data": {"账号": "test01"}, "coverage_rule": rule,
            "design_method": ["场景法"]}


def run(cases, tag, rules=None, extra=()):
    p = os.path.join(TMP, f"{tag}.json")
    json.dump(cases, open(p, "w", encoding="utf-8"), ensure_ascii=False)
    cmd = [PY, SCRIPT, p] + RELAX + list(extra)
    if rules:
        rp = os.path.join(TMP, "rules.json")
        json.dump(rules, open(rp, "w", encoding="utf-8"), ensure_ascii=False)
        cmd += ["--requirement-rules", rp]
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                          errors="replace")


# ---------- 一、单例规则 ----------
# R-001 有 2 条、R-002 只有 1 条 → 必须点名 R-002
cases = [mk("TC-A-001", "R-001"), mk("TC-A-002", "R-001"), mk("TC-A-003", "R-002")]
r = run(cases, "single", rules=["R-001", "R-002"])
check("单例规则 被点名（默认 warn）",
      "单例规则" in r.stdout and "R-002" in r.stdout, r.stdout[-500:])
check("单例规则 不误伤 2 条的规则",
      "R-001(1条" not in r.stdout, r.stdout[-500:])

r = run(cases, "single_exempt", rules=["R-001", "R-002"],
        extra=["--density-exempt", "R-002"])
check("单例规则 --density-exempt 豁免后不报",
      "[!] 单例规则" not in r.stdout, r.stdout[-500:])

r = run(cases, "single_off", rules=["R-001", "R-002"],
        extra=["--single-case-mode", "off"])
check("单例规则 --single-case-mode off 关闭",
      "[!] 单例规则" not in r.stdout, r.stdout[-500:])

r = run(cases, "single_block", rules=["R-001", "R-002"],
        extra=["--single-case-mode", "block"])
check("单例规则 block 模式阻断", r.returncode == 1, f"exit={r.returncode}")

# 关键：密度阈值默认关闭（--min-cases-per-rule 0），单例仍要生效
check("单例规则 独立于密度阈值（阈值 0 也照跑）",
      "[!] 单例规则" in r.stdout, r.stdout[-500:])

# 每条需求都 ≥2 条 → 不报
cases2 = [mk("TC-B-001", "R-001"), mk("TC-B-002", "R-001"),
          mk("TC-B-003", "R-002"), mk("TC-B-004", "R-002")]
r = run(cases2, "no_single", rules=["R-001", "R-002"])
check("无单例 时给出达标提示", "无单例规则" in r.stdout, r.stdout[-500:])

# ---------- 二、回归用例分离 ----------
# R-090 是回归规则，挂 10 条；R-001/R-002 是需求规则，各 2 条
mix = ([mk(f"TC-R-{i:03d}", "R-001") for i in range(2)]
       + [mk(f"TC-S-{i:03d}", "R-002") for i in range(2)]
       + [mk(f"TC-G-{i:03d}", "R-090") for i in range(10)])
r = run(mix, "reg_marked", rules=["R-001", "R-002", "R-090"],
        extra=["--regression-rules", "R-090", "--min-cases-per-rule", "6",
               "--density-mode", "block"])
check("回归分离 回归用例被单独统计",
      "回归用例 10 条" in r.stdout and "回归规则" in r.stdout, r.stdout[-600:])
check("回归分离 回归规则不进密度分母",
      "R-090" not in r.stdout.split("需求密度")[-1] if "需求密度" in r.stdout else True,
      r.stdout[-600:])
check("回归分离 需求规则仍按真实密度判（2 条 < 6 → 阻断）",
      r.returncode == 1, f"exit={r.returncode}")

# 不标回归时，R-090 的 10 条会把密度拉平（正是要避免的口径混淆）
r2 = run(mix, "reg_unmarked", rules=["R-001", "R-002", "R-090"])
check("未标回归 时不会打印回归统计", "回归用例" not in r2.stdout, r2.stdout[-400:])

# 前缀方式：REG- 编号的老库
reg_pref = [mk("TC-P-001", "R-001"), mk("TC-P-002", "R-001"),
            mk("TC-P-003", "REG-001"), mk("TC-P-004", "REG-001")]
r = run(reg_pref, "reg_prefix", rules=["R-001"],
        extra=["--regression-prefix", "REG-"])
check("回归前缀 REG- 被识别并单独统计",
      "回归用例 2 条" in r.stdout, r.stdout[-500:])

# ---------- 三、覆盖率审计：模块名归集不到 ----------
rules_json = [
    {"id": "R-001", "module": "APP 系统设置", "text": "主题设置应保存", "priority": "P1"},
    {"id": "R-002", "module": "报表", "text": "报表应导出", "priority": "P1"},
]
rcases = [
    # R-001 规则被覆盖了，但用例挂在「App 设置与个人中心」上，与需求侧名字对不上
    {"id": "TC-1", "module": "App 设置与个人中心", "name": "主题设置保存",
     "test_type": "功能", "steps": "a", "expected": "b", "coverage_rule": "R-001"},
    # 报表完全没有用例
    {"id": "TC-2", "module": "App 设置与个人中心", "name": "其它", "test_type": "功能",
     "steps": "a", "expected": "b", "coverage_rule": "R-001"},
]
cp = os.path.join(TMP, "audit_cases.json")
rp = os.path.join(TMP, "audit_rules.json")
json.dump(rcases, open(cp, "w", encoding="utf-8"), ensure_ascii=False)
json.dump(rules_json, open(rp, "w", encoding="utf-8"), ensure_ascii=False)
ra = subprocess.run([PY, AUDIT, cp, rp], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
out = ra.stdout + ra.stderr
check("模块名归集 报出「用例归集不到」", "归集不到" in out or "name_mismatch" in out,
      out[-800:])
check("模块名归集 真零覆盖仍然报「零覆盖」", "零覆盖" in out, out[-800:])

print("\n" + "=" * 30)
print(f"通过 {PASS}/{PASS + FAIL}")
if FAILS:
    print("失败:", FAILS)
sys.exit(1 if FAIL else 0)
