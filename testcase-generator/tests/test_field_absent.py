#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""「字段整体缺失」与「字段填错」必须区别对待。

真实项目库常没有 `design_method` 列、也没有需求编号列。此时逐条判违规会得到
100% 失败——不是用例有问题，是这份库的字段形态不同。全部判红会让闸门失去信任，
最终被整体关掉。

本回归守住三条：
  A 字段整体缺失 -> 整项跳过，且**跳过必须可见**（不能静默）
  B 只要有任意一条填了 -> 仍按"填错的那些"判，跳过不能变成免罚出口
  C 跳过的闸门要在汇总里单独列段，而不是混进 warns
"""
import json
import os
import re
import subprocess
import sys
import tempfile

SKILL = os.environ.get("TC_SKILL") or os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))
PRESCREEN = os.path.join(SKILL, "scripts", "prescreen.py")
PY = sys.executable
TMP = tempfile.mkdtemp(prefix="field_absent_")

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


def case(i, module="登录", priority="P1", dm=None, rule=None, steps=None,
         expected=None):
    c = {
        "id": f"TC-LOG-{i:03d}",
        "module": f"设备端-{module}",
        "name": f"登录主流程{i}",
        "priority": priority,
        "type": "功能测试",
        "precondition": f"1.第 {i} 号设备已联网",
        # 每条用例的步骤与预期都要求互不相同，否则会撞上第 6 项「语义重复」闸门，
        # 把本回归要验的东西淹没在无关失败里。
        "steps": steps or f"1.点击第 {i} 号登录入口并输入账号 {i}",
        "expected": expected or f"1.应跳转到第 {i} 号首页并显示用户名 user{i}",
        "test_data": f"账号=138001{i:05d}",
    }
    if dm is not None:
        c["design_method"] = dm
    if rule is not None:
        c["coverage_rule"] = rule
    return c


def run(cases, extra=None):
    p = os.path.join(TMP, "c.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump({"cases": cases}, f, ensure_ascii=False)
    args = [PY, PRESCREEN, p] + (extra or [])
    return subprocess.run(args, capture_output=True, text=True,
                          encoding="utf-8", errors="replace",
                          env=dict(os.environ, PYTHONIOENCODING="utf-8"))


# 用例池：P0/P1/P2 各占合理比例，避开占比闸门干扰
def pool(**kw):
    out = []
    for i in range(1, 21):
        pr = "P0" if i <= 2 else ("P2" if i <= 8 else "P1")
        out.append(case(i, priority=pr, **kw))
    return out


# ---------- A：两个字段都缺 -> 整项跳过 ----------
r = run(pool())
check("无 design_method 时第 4 项跳过", "[–] 第 4 项跳过" in r.stdout, r.stdout[-500:])
check("无 coverage_rule 时第 10 项跳过", "[–] 第 10 项跳过" in r.stdout, r.stdout[-500:])
check("不再误报『未关联合法测试设计方法』",
      "未关联合法测试设计方法" not in r.stdout, r.stdout[-400:])
check("不再误报『条孤儿用例』", "条孤儿用例（无 coverage_rule" not in r.stdout, r.stdout[-400:])
check("跳过段有独立标题（可见，不静默）",
      "已跳过的闸门" in r.stdout and "不代表通过" in r.stdout, r.stdout[-400:])
# 不断言"整体通过"——这个夹具还会撞上负向配额等无关闸门。
# 要验的是「第 4/10 项不再因字段缺失产出 ✗」，其余闸门与本回归无关。
check("跳过后第 4/10 项均不再产出 ✗",
      "未关联合法测试设计方法" not in r.stdout
      and "条孤儿用例（无 coverage_rule" not in r.stdout,
      r.stdout[-600:])

# ---------- B：部分填了 -> 仍判违规，跳过不许当免罚出口 ----------
half = pool()
for c in half:
    c["design_method"] = ["等价类划分"]        # 先全给合法，避免"没填"混进来
for c in half[5:8]:
    c["design_method"] = ["拍脑袋"]            # 只把 3 条改成非法
r2 = run(half)
check("部分填了 -> 第 4 项不跳过", "[–] 第 4 项跳过" not in r2.stdout, r2.stdout[-400:])
check("部分填了 -> 3 条非法方法仍被判出",
      "3 条用例未关联合法测试设计方法" in r2.stdout, r2.stdout[-800:])
check("部分填了 -> 退出码 1", r2.returncode == 1, f"exit={r2.returncode}")

# ---------- B2：有 requirement_rules 时，全库无 coverage_rule 不能跳过 ----------
# 给了需求清单，说明这份库要做需求追溯，此时全无 coverage_rule 就是真孤儿。
req = os.path.join(TMP, "req.json")
with open(req, "w", encoding="utf-8") as f:
    json.dump({"requirements": [{"id": "R-1", "title": "登录"}]}, f, ensure_ascii=False)
p3 = os.path.join(TMP, "c3.json")
with open(p3, "w", encoding="utf-8") as f:
    json.dump({"cases": pool()}, f, ensure_ascii=False)
r3 = subprocess.run([PY, PRESCREEN, p3, "--requirement-rules", req],
                    capture_output=True, text=True, encoding="utf-8",
                    errors="replace", env=dict(os.environ, PYTHONIOENCODING="utf-8"))
check("给了需求清单 -> 第 10 项不跳过（孤儿照判）",
      "[–] 第 10 项跳过" not in r3.stdout, r3.stdout[-400:])

# ---------- D：xlsx_util 不吃 read_only（防"以为用了只读"） ----------
util = os.path.join(SKILL, "scripts", "xlsx_util.py")
src = open(util, encoding="utf-8").read()
check("xlsx_util 显式挡掉 read_only", "kw.pop(\"read_only\"" in src, "未见 pop('read_only')")

try:
    from openpyxl import Workbook, load_workbook
    sys.path.insert(0, os.path.join(SKILL, "scripts"))
    import xlsx_util
    xp = os.path.join(TMP, "t.xlsx")
    wb = Workbook()
    ws = wb.active
    for i in range(1, 51):
        ws.append([f"A{i}", f"B{i}"])
    wb.save(xp)
    got = xlsx_util.open_workbook(xp, read_only=True)   # 传了也应被挡掉
    ws2 = got[got.sheetnames[0]]
    n = sum(1 for _ in ws2.iter_rows(values_only=True))
    got.close()
    check("xlsx_util 传 read_only 仍读全 50 行", n == 50, f"读到 {n} 行")
except ImportError:
    print("[跳过] 无 openpyxl，xlsx_util 相关用例未执行")

print("\n" + "=" * 30)
print(f"通过 {PASS}/{PASS + FAIL}")
if FAILS:
    print("失败:", FAILS)
sys.exit(1 if FAIL else 0)
