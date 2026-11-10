#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""结果码语义回归：NP 是「待执行」，不是「失败」，也不是「已执行」。

为什么值得单独立一个文件：
某正式库 1669 条已执行记录里有 45 条 NP。早年实现是 `executed = [c for c in cases
if c["result"]]`——只要填了就算执行过。于是：
  1. 执行率虚高：本阶段还没排上的，被算成"已经跑过了"；
  2. 死用例分析出假阳性：`非通过 -> continue` 的写法让 NP 在"是否通过"上判错；
  3. 缺陷漏测口径被污染："还没测"和"测了没拦住"混成一个数。
本回归钉死这三点。
"""
import os
import sys

SKILL = os.environ.get("TC_SKILL") or os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(SKILL, "scripts"))

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


try:
    import defect_audit as da
except Exception as e:
    print(f"[错误] 无法导入 defect_audit: {e}")
    sys.exit(1)

cls = da.classify_result

# ---------- 五类结果码 ----------
CASES = [
    # (原值, 期望分类)
    ("PASS", "pass"),
    ("pass", "pass"),
    ("通过", "pass"),
    ("PASS ", "pass"),          # 尾部空格
    ("PASS（见备注）", "pass"),  # 包含式兜底
    ("FAIL", "fail"),
    ("失败", "fail"),
    ("NG", "fail"),
    ("NP", "pending"),
    ("np", "pending"),
    ("NT", "not_run"),
    ("未测试", "not_run"),
    ("BLOCK", "blocked"),
    ("阻塞", "blocked"),
    ("", "empty"),
    (None, "empty"),
]
bad = []
for raw, want in CASES:
    got = cls(raw)
    if got != want:
        bad.append(f"{raw!r} -> {got}（期望 {want}）")
check(f"结果码分类 {len(CASES)} 例全部正确", not bad, str(bad))

# ---------- 核心区分：NP 绝不等价于 fail ----------
check("NP 不算 fail", cls("NP") != "fail", f"got={cls('NP')}")
check("NP 不算 pass", cls("NP") != "pass", f"got={cls('NP')}")
check("NP 归 pending（本阶段应测未测）", cls("NP") == "pending", f"got={cls('NP')}")
check("NT/BLOCK 也不计入已执行",
      cls("NT") in ("not_run",) and cls("BLOCK") == "blocked",
      f"NT={cls('NT')} BLOCK={cls('BLOCK')}")

# ---------- 源码级：executed 不得再用「有值即执行」 ----------
import io
src = io.open(os.path.join(SKILL, "scripts", "defect_audit.py"),
              encoding="utf-8").read()
check("executed 不再用 `if c[\"result\"]` 粗判",
      'executed = [c for c in cases if c["result"]]' not in src,
      "仍存在旧的「有值即已执行」写法")
check("死用例候选按 classify_result == pass 判",
      'kinds.get(c["id"]) != "pass"' in src,
      "死用例候选未按分类判定")
check("报告含「阶段内待执行」段", "阶段内待执行（NP）" in src, "报告未出现 NP 段")
check("报告把 NP 与漏测分开表述", "不是漏测" in src, "缺少口径说明")

print("\n" + "=" * 30)
print(f"通过 {PASS}/{PASS + FAIL}")
if FAILS:
    print("失败:", FAILS)
sys.exit(1 if FAIL else 0)
