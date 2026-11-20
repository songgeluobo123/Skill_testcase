#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""存量用例库体检（Step 7.1）：只读诊断，不改原库。

回答「接手的历史库哪里走形、先改什么」，输出七类问题清单 + 修复顺序建议。

七类（与 references/legacy_normalize.md 一一对应）：
  1 结构与语义错位（前置里写了操作动作）
  2 标题含空泛判定词（成功/正确/正常/通过/无异常）
  3 步骤不可执行（无动词白名单 / 点按钮未说位置）
  4 测试数据无效（占位符）
  5 优先级失衡（P0/P2 占比越界）
  6 语义重复（同模块+同前置+同步骤+同预期）
  7 范围性用例（逐一/分别/全部 + 只 1 条断言）

用法：
  python normalize_legacy.py 存量库.xlsx -o 体检报告.md
  python normalize_legacy.py 存量库.json -o 体检报告.md --top 10
  python normalize_legacy.py 存量库.xlsx                 # 只打印摘要

退出码：0 体检完成 / 2 输入错误 / 3 脚本崩溃 / 4 环境缺依赖（xlsx 输入需 openpyxl）

设计原则：**复用现有判据，不另立一套**——正则与工具从 prescreen.py / score_testcases.py
导入，保证体检结论与正式闸门一致。本脚本只诊断，不提供 --apply（改写属判断性工作，
见 legacy_normalize.md 7.2）。
"""

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import prescreen as ps
except Exception as e:                                    # pragma: no cover
    print(f"[错误] 无法导入 prescreen.py: {e}", file=sys.stderr)
    sys.exit(3)

try:
    import score_testcases as sc
    STEP_VERBS, POS_WORDS = sc.STEP_VERBS, sc.POS_WORDS
except Exception:                                         # 旧版本兜底
    STEP_VERBS = ["点击", "输入", "勾选", "查验", "进入", "设置", "选择", "关闭"]
    POS_WORDS = ["导航", "页面", "右侧", "左侧"]

PLACEHOLDER_DATA = re.compile(r"^(test\d*|xxx+|待定|TBD|示例|abc|123|1)$", re.I)
ACTION_IN_PRE = re.compile(r"^\s*\d*[.、]?\s*(点击|输入|勾选|进入|选择|打开|关闭|滑动)")


def load_cases(path):
    """读 xlsx 或 json，返回统一用例 dict 列表（列别名按 coverage_audit 口径）。"""
    if path.lower().endswith((".xlsx", ".xlsm", ".xltx")):
        try:
            from openpyxl import load_workbook
        except ImportError:
            print("[错误] 读 xlsx 需要 openpyxl: pip install openpyxl", file=sys.stderr)
            sys.exit(4)
        wb = load_workbook(path, data_only=True)
        ws = wb[wb.sheetnames[0]]
        header = [str(c.value).strip() if c.value is not None else "" for c in ws[1]]
        alias = {
            "id": ["用例编号", "编号", "id"],
            "module": ["功能模块", "测试模块", "所属模块", "模块"],
            "name": ["测试用例标题", "用例名称", "用例标题", "title", "name"],
            "priority": ["测试优先级", "优先级", "priority"],
            "test_type": ["测试类型", "test_type"],
            "environment": ["测试环境", "环境"],
            "precondition": ["前置条件", "precondition"],
            "steps": ["测试步骤", "步骤", "steps"],
            "expected": ["预期结果", "预期", "expected"],
            "test_data": ["测试数据", "test_data"],
            "remark": ["备注", "remark"],
        }
        idx = {}
        for key, names in alias.items():
            for i, h in enumerate(header):
                if h in names:
                    idx[key] = i
                    break
        if "name" not in idx or "steps" not in idx:
            print(f"[错误] 未识别到「用例标题/测试步骤」列，实际表头: {header}", file=sys.stderr)
            sys.exit(2)
        cases = []
        for r in ws.iter_rows(min_row=2, values_only=True):
            if not any(v not in (None, "") for v in r):
                continue
            def g(k):
                i = idx.get(k)
                if i is None or i >= len(r) or r[i] is None:
                    return ""
                return re.sub(r"\r", "\n", str(r[i])).strip()
            cases.append({k: g(k) for k in alias})
        return cases

    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict) and "cases" in data:
        return data["cases"]
    if isinstance(data, list):
        return data
    print("[错误] JSON 需为用例数组或含 cases 键的对象", file=sys.stderr)
    sys.exit(2)


def is_placeholder_data(v):
    if not v:
        return False
    if isinstance(v, dict):
        return any(PLACEHOLDER_DATA.match(str(x).strip()) for x in v.values())
    return bool(PLACEHOLDER_DATA.match(str(v).strip()))


def diagnose(cases):
    """返回七类问题 dict：{类名: {"count": n, "items": [(id, 说明)], "mech": bool}}"""
    out = {k: {"count": 0, "items": [], "mech": mech} for k, mech in [
        ("结构与语义错位", False), ("标题含空泛判定词", True),
        ("步骤不可执行", False), ("测试数据无效", True),
        ("优先级失衡", True), ("语义重复", False), ("范围性用例", False)]}

    p0 = sum(1 for c in cases if str(c.get("priority", "")).upper() == "P0")
    p2 = sum(1 for c in cases if str(c.get("priority", "")).upper() == "P2")
    total = max(1, len(cases))

    seen = {}
    for c in cases:
        cid = c.get("id") or "?"
        name = str(c.get("name", "") or "")
        pre = str(c.get("precondition", "") or "")
        steps = str(c.get("steps", "") or "")
        exp = str(c.get("expected", "") or "")

        # 1 前置里写操作
        bad_pre = [ln for ln in pre.split("\n") if ACTION_IN_PRE.match(ln)]
        if bad_pre:
            out["结构与语义错位"]["count"] += 1
            if len(out["结构与语义错位"]["items"]) < 99:
                out["结构与语义错位"]["items"].append((cid, bad_pre[0].strip()[:40]))

        # 2 标题空泛
        hit = [w for w in ("成功", "正确", "通过", "正常", "无异常") if w in name]
        if hit:
            out["标题含空泛判定词"]["count"] += 1
            if len(out["标题含空泛判定词"]["items"]) < 99:
                out["标题含空泛判定词"]["items"].append((cid, f"{name[:24]}（{hit[0]}）"))

        # 3 步骤不可执行
        if steps:
            has_verb = any(v in steps for v in STEP_VERBS)
            vague_pos = ("点击" in steps and "按钮" in steps
                         and not any(w in steps for w in POS_WORDS))
            if not has_verb or vague_pos:
                out["步骤不可执行"]["count"] += 1
                if len(out["步骤不可执行"]["items"]) < 99:
                    why = "无明确动词" if not has_verb else "点击按钮未说位置"
                    out["步骤不可执行"]["items"].append((cid, f"{why}：{steps[:36]}"))

        # 4 数据占位
        if is_placeholder_data(c.get("test_data")):
            out["测试数据无效"]["count"] += 1
            if len(out["测试数据无效"]["items"]) < 99:
                out["测试数据无效"]["items"].append((cid, str(c.get("test_data"))[:30]))

        # 6 语义重复
        key = (str(c.get("module", "")), ps.norm(pre), ps.norm(steps), ps.norm(exp))
        seen.setdefault(key, []).append(cid)

        # 7 范围性（复用 prescreen 的 range_evidence，保证与第 14 项同口径）
        r_hit, r_objs, r_nexp, _rw = ps.range_evidence(c)
        if r_hit and r_objs >= 3 and r_nexp <= 1:
            out["范围性用例"]["count"] += 1
            if len(out["范围性用例"]["items"]) < 99:
                out["范围性用例"]["items"].append((cid, steps[:40]))

    # 5 优先级失衡（整库级）
    p0r, p2r = p0 / total, p2 / total
    if p0r > 0.25 or p0r < 0.10 or not (0.25 <= p2r <= 0.40):
        out["优先级失衡"]["count"] = 1
        out["优先级失衡"]["items"] = [("整库", f"P0 {p0r:.0%} / P2 {p2r:.0%}（P0 应 10%~25%，P2 应 25%~40%）")]

    # 6 汇总重复组
    dups = [(k, v) for k, v in seen.items() if len(v) > 1]
    if dups:
        out["语义重复"]["count"] = len(dups)
        out["语义重复"]["items"] = [(v[0], f"重复 {len(v)} 条：{','.join(v[:5])}") for _k, v in dups[:20]]

    return out


def render(path, cases, res, top):
    lines = [f"# 存量用例库体检报告", "",
             f"> 对象：`{os.path.basename(path)}`　|　用例总数：**{len(cases)}**",
             f"> 口径：七类判据与 `prescreen.py` / `score_testcases.py` 同源（`legacy_normalize.md`）", ""]
    from collections import Counter
    mods = Counter(str(c.get("module", "") or "(未分模块)") for c in cases)
    lines += ["## 一、概况", "",
              "| 模块 | 条数 |", "|---|---|"]
    lines += [f"| {m} | {n} |" for m, n in mods.most_common(20)]
    lines += ["", "## 二、七类问题", "",
              "| # | 问题 | 影响 | 可机械修 |", "|---|---|---|---|"]
    order = list(res)
    for i, k in enumerate(order, 1):
        d = res[k]
        lines.append(f"| {i} | {k} | {d['count']} | {'是' if d['mech'] else '否（人工）'} |")
    lines.append("")

    for i, k in enumerate(order, 1):
        d = res[k]
        lines += [f"### {i}. {k}（{d['count']} 条）", ""]
        if not d["items"]:
            lines += ["- 无。", ""]
            continue
        for cid, why in d["items"][:top]:
            lines.append(f"- `{cid}` {why}")
        if d["count"] > top:
            lines.append(f"- … 其余 {d['count'] - top} 条见原始库")
        mech = "可脚本批量修复" if d["mech"] else "需逐条判断"
        lines += ["", f"> 修复方式：{mech}（见 `legacy_normalize.md` 7.2）", ""]

    lines += ["## 三、建议顺序", "",
              "1. **结构与语义错位** → 2. 标题空泛词 → 3. 步骤可执行性 → 4. 测试数据 "
              "→ 5. 优先级统一重算 → 6. 语义重复合并 → 7. 范围性拆分", "",
              "**顺序不可颠倒**：先合并再改标题会让合并判据失真。", "",
              "## 四、复查命令", "",
              "```bash",
              f"python scripts/prescreen.py <修复后.json> --requirement-rules <需求规则.json> \\",
              "       --min-cases-per-rule 4 --density-mode block --single-case-mode block \\",
              "       --ui-cover-mode warn --nf-cover-mode warn --range-mode block",
              "python scripts/score_testcases.py <修复后.json>",
              "```", ""]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="存量用例库体检（只读，不改原库）")
    ap.add_argument("input", help="存量库 .xlsx / .xlsm 或用例 JSON")
    ap.add_argument("-o", "--output", help="体检报告 .md 路径（不给则只打印摘要）")
    ap.add_argument("--top", type=int, default=8, help="每类列出的样本数（默认 8）")
    args = ap.parse_args()

    if not os.path.exists(args.input):
        print(f"[错误] 文件不存在: {args.input}", file=sys.stderr)
        return 2
    cases = load_cases(args.input)
    if not cases:
        print("[错误] 未读到任何用例", file=sys.stderr)
        return 2

    res = diagnose(cases)
    print(f"[i] 体检 {len(cases)} 条用例")
    for k, d in res.items():
        print(f"    {k:12s} {d['count']:4d} 条  {'机械可修' if d['mech'] else '需人工'}")

    if args.output:
        md = render(args.input, cases, res, args.top)
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(md)
        print(f"[✓] 体检报告: {args.output}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception:
        import traceback
        print("\n[内部错误] normalize_legacy.py 自身崩溃（exit 3），不是数据问题。", file=sys.stderr)
        traceback.print_exc()
        sys.exit(3)
