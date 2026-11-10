"""input_readiness.py 回归测试（M8）+ coverage_audit.py G3 放宽验证（M10）。

覆盖：四类输入的判定、空原型占位反例、严格模式退出码、json 输出、--require 子集，
以及 G3 从"恰好 1 条"放宽到"≤2 条且含多约束词"的正反两向。
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
READY = os.path.join(SKILL, "scripts", "input_readiness.py")
AUDIT = os.path.join(SKILL, "scripts", "coverage_audit.py")
PY = sys.executable

TMP = tempfile.mkdtemp(prefix="readiness_")
results = []


def run(script, *args):
    p = subprocess.run([PY, script, *args], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return p.returncode, p.stdout or "", p.stderr or ""


def check(name, cond, detail=""):
    results.append((name, bool(cond), detail))
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else f"   <<< {detail[:400]}"))


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


# ---------------------------------------------------------------- 夹具
full = os.path.join(TMP, "full")
write(os.path.join(full, "数据字典.md"), "# 字段表\n\n| 字段 | 类型 | 长度 | 必填 |\n|---|---|---|---|\n| 手机号 | string | 11 | 是 |\n")
write(os.path.join(full, "原型链接.md"), "# 原型\n\n- 主流程：https://www.figma.com/file/abc123/E-Bike\n")
write(os.path.join(full, "api接口文档.md"), "# 接口\n\nGET /v1/bike/status\n")
write(os.path.join(full, "缺陷清单.csv"), "缺陷编号,标题,模块,严重程度\nBUG-1,车辆解锁超时,车辆控制,严重\n")

# 空原型占位：文件名像原型，内容只有"待补充"
placeholder = os.path.join(TMP, "placeholder")
write(os.path.join(placeholder, "数据字典.md"), "# 字段表\n")
write(os.path.join(placeholder, "原型链接.md"), "原型链接\n\n待补充\n")
write(os.path.join(placeholder, "api.md"), "# 接口\n")
write(os.path.join(placeholder, "bug清单.md"), "# 缺陷\n")

empty = os.path.join(TMP, "empty")
os.makedirs(empty, exist_ok=True)

missing_dir = os.path.join(TMP, "not_exist_here")

print("=" * 18, "1. 全齐目录", "=" * 18)
code, out, err = run(READY, "--prd", full)
print(out[:600])
print("exit:", code)
check("全齐目录 → 完备度 4/4", "输入完备度 4/4" in out, out)
check("全齐目录 → exit 0", code == 0, f"exit={code} {err}")
check("全齐目录 → 四类证据被列出", all(k in out for k in ("数据字典", "原型链接.md", "api接口文档.md", "缺陷清单.csv")), out)

code, out, err = run(READY, "--prd", full, "--strict")
check("--strict 且四类齐备 → exit 0", code == 0, f"exit={code} {err}")

print("=" * 18, "2. 空目录（默认不阻断）", "=" * 18)
code, out, err = run(READY, "--prd", empty)
print(out[:400])
check("空目录 → 0/4", "输入完备度 0/4" in out, out)
check("空目录 → exit 0（默认非闸门）", code == 0, f"exit={code} {err}")
check("空目录 → 四项证据均为「未找到」", out.count("未找到") >= 4, out)

print("=" * 18, "3. --strict 有缺失", "=" * 18)
code, out, err = run(READY, "--prd", empty, "--strict")
check("--strict + 有缺失 → exit 1", code == 1, f"exit={code}")

print("=" * 18, "4. 空原型占位文档判缺失", "=" * 18)
code, out, err = run(READY, "--prd", placeholder, "--format", "json")
print(out[:800])
try:
    j = json.loads(out)
except Exception as e:
    j = {}
    print("[!] json 解析失败:", e)
check("空原型占位 → prototype 判缺失", "prototype" in j.get("missing", []), json.dumps(j.get("missing"), ensure_ascii=False))
check("空原型占位 → 其余三类齐备（1/4）", j.get("ready") == 3 and j.get("total") == 4, json.dumps(j.get("ready")))
check("空原型占位 → 报告点明空链接占位", "空链接占位" in out, out)

print("=" * 18, "5. 目录不存在", "=" * 18)
code, out, err = run(READY, "--prd", missing_dir)
check("目录不存在 → exit 2", code == 2, f"exit={code} err={err}")

print("=" * 18, "6. 报告结构 & json 字段", "=" * 18)
code, out, err = run(READY, "--prd", empty)
check("报告含四类输入名", all(k in out for k in ("数据字典", "原型", "API", "缺陷")), out[:200])
check("报告含「可回收上限」", "可回收上限" in out, out[:200])
check("报告含基准说明（47 需求 / 196 条）", "47 需求" in out and "196 条" in out, out[:400])
check("报告含可粘贴的声明段", "可直接粘贴进《测试分析报告》" in out and "本次输入完备度" in out, out[-800:])

code, out, err = run(READY, "--prd", empty, "--format", "json")
try:
    j2 = json.loads(out)
except Exception as e:
    j2 = {}
    print("[!] json 解析失败:", e)
check("--format json 可解析且含 ready/total",
      isinstance(j2.get("ready"), int) and isinstance(j2.get("total"), int) and j2["total"] == 4, out[:300])
check("json 含 reachable 区间", isinstance(j2.get("reachable"), list) and len(j2.get("reachable") or []) == 2, out[:300])

print("=" * 18, "7. --require 子集", "=" * 18)
code, out, err = run(READY, "--prd", placeholder, "--require", "dictionary", "--format", "json")
try:
    j3 = json.loads(out)
except Exception:
    j3 = {}
check("--require 单类 → 1/1", j3.get("ready") == 1 and j3.get("total") == 1, out[:300])
code, out, err = run(READY, "--prd", empty, "--require", "prototype", "--strict")
check("--require 单类缺失 + --strict → exit 1", code == 1, f"exit={code}")

# ---------------------------------------------------------------- G3：coverage_audit
print("=" * 18, "8. G3 名义覆盖口径放宽", "=" * 18)


def g3_case(rule_text, n_cases, tag):
    d = os.path.join(TMP, tag)
    os.makedirs(d, exist_ok=True)
    rules = [{"id": "R-001", "module": "订单", "type": "included", "text": rule_text}]
    cases = [{"id": f"TC-{i}", "module": "订单", "name": "订单筛选",
              "test_type": "功能", "steps": "选择状态筛选", "expected": "列表更新",
              "coverage_rule": "R-001"} for i in range(1, n_cases + 1)]
    rp, cp = os.path.join(d, "req.json"), os.path.join(d, "cases.json")
    json.dump(rules, open(rp, "w", encoding="utf-8"), ensure_ascii=False)
    json.dump(cases, open(cp, "w", encoding="utf-8"), ensure_ascii=False)
    return run(AUDIT, cp, rp)


# 2 条覆盖 + 含"分别" → 应报名义覆盖（旧口径只抓恰好 1 条，会漏）
code, out, _ = g3_case("订单可按待支付、已支付、已取消分别筛选", 2, "g3_multi")
check("2 条覆盖 + 多约束词 → 报名义覆盖", "覆盖 2 条" in out and "R-001" in out, out[-900:])
check("G3 口径说明已同步为「≤2 条且含多约束词」", "≤2 条" in out, out[-900:])

# 2 条覆盖 + 无多约束词 → 不报
code, out, _ = g3_case("登录成功后跳转首页", 2, "g3_plain")
check("2 条覆盖 + 无多约束词 → 不报名义覆盖", "无需拆分" in out, out[-900:])

# 1 条覆盖 + 无多约束词 → 不报（旧口径会误报）
code, out, _ = g3_case("登录成功后跳转首页", 1, "g3_single")
check("1 条覆盖 + 无多约束词 → 不报（比旧口径更准）", "无需拆分" in out, out[-900:])

# 1 条覆盖 + 含多约束词 → 仍报（保留原能力）
code, out, _ = g3_case("密码错误或账号不存在时提示登录失败", 1, "g3_single_multi")
check("1 条覆盖 + 多约束词 → 仍报（保留原能力）", "覆盖 1 条" in out, out[-900:])

print("\n" + "=" * 30)
ok = sum(1 for _, c, _ in results if c)
print(f"通过 {ok}/{len(results)}")
fails = [n for n, c, _ in results if not c]
if fails:
    print("失败项：")
    for n in fails:
        print("  -", n)
print("临时目录:", TMP)
sys.exit(0 if not fails else 1)
