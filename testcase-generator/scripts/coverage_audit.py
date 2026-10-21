#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
coverage_audit.py — 用例覆盖率评审器（用例库 × 需求文档 → 覆盖率报告 + 缺失清单）

与 map_coverage.py 的分工：
  - map_coverage.py：给**生成中**的用例补 coverage_rule，服务于 prescreen 的全局覆盖率闸门。
  - coverage_audit.py：给**已有用例库 / 生成后终稿**做评审，输出**模块级**覆盖率与缺口报告，
    定位"哪个模块漏得最多、缺什么类型的用例"。全局 95% 会掩盖某模块 40%，本脚本专治这个。

三类缺口（见 references/coverage_audit.md）：
  G1 需求有、用例无         → 规则未被任何用例覆盖
  G2 覆盖了但场景失衡       → 模块缺异常/边界/权限类用例（用户例为 0 直接标红）
  G3 名义覆盖               → 1 条用例挂多个规则，实际颗粒度撑不住

输入：
  用例  —— .json（数组或 {"cases": [...]}）或 .xlsx（自动识别表头，兼容中文列名）
  需求  —— requirements.json（extract_requirements.py 产出：[{id, module, text, type, ...}]）

用法：
  python coverage_audit.py cases.xlsx requirements.json -o 覆盖率报告.md
  python coverage_audit.py test_cases.json requirements.json --module-min 0.8
  python coverage_audit.py cases.xlsx requirements.json --format json -o audit.json

退出码：0 全部模块达标；1 存在低于阈值的模块或 G1 缺口；2 输入/参数错误。
"""

import argparse
import json
import re
import sys
from datetime import datetime

DEFAULT_MODULE_MIN = 0.70

# 场景分类关键词（test_type 优先，缺失时回落到标题 + 步骤文本）
PERM_KEYS = ["权限", "越权", "角色", "未登录", "未授权", "鉴权", "登录态", "白名单", "游客"]
NEG_KEYS = ["异常", "边界", "失败", "错误", "超限", "超时", "为空", "空值", "非法",
            "不支持", "重复", "断网", "弱网", "逆向", "负向", "拒绝", "上限", "下限",
            "最大", "最小", "超出", "超过"]
POS_KEYS = ["正常", "成功", "正向", "主流程", "有效"]

# 需求文本 → 建议用例类型
TYPE_HINTS = [
    (["权限", "角色", "越权", "未登录", "鉴权", "白名单"], "权限校验"),
    (["边界", "最大", "最小", "上限", "下限", "超过", "超出", "长度", "范围"], "边界值分析"),
    (["异常", "失败", "错误", "不支持", "为空", "非法", "超时", "重复"], "异常处理"),
    (["状态", "流转", "切换", "恢复"], "状态迁移"),
    (["同时", "组合", "多项", "并行"], "正交分析"),
]
# 需求文本 → 建议优先级
PRIORITY_HINTS = [
    (["安全", "隐私", "加密", "越权", "支付", "扣费", "登录", "鉴权", "数据丢失"], "P0"),
    (["主流程", "核心", "边界", "超时", "上限", "异常", "失败", "权限"], "P1"),
    (["显示", "美观", "文案", "兼容", "响应式", "旋转"], "P3"),
]

HEADER_ALIASES = {
    "id": ["用例编号", "编号", "id", "用例id", "caseid"],
    "module": ["测试模块", "模块", "所属模块", "功能模块", "module"],
    "title": ["用例名称", "用例标题", "标题", "名称", "title", "name"],
    "priority": ["优先级", "priority", "级别"],
    "test_type": ["测试类型", "类型", "用例类型", "testtype"],
    "precondition": ["前置条件", "前置", "precondition"],
    "steps": ["测试步骤", "步骤", "操作步骤", "steps"],
    "expected": ["预期结果", "预期", "expected"],
}


# ---------------------------------------------------------------- 输入解析
def load_cases(path):
    low = path.lower()
    if low.endswith((".xlsx", ".xlsm")):
        return _load_cases_xlsx(path)
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict) and "cases" in data:
        data = data["cases"]
    if not isinstance(data, list):
        raise ValueError("用例文件需为数组，或含 cases 键的对象")
    return data


def _load_cases_xlsx(path):
    try:
        from openpyxl import load_workbook
    except ImportError:
        raise RuntimeError("读取 .xlsx 需要 openpyxl（pip install openpyxl）")
    wb = load_workbook(path, read_only=True, data_only=True)
    ws = wb[wb.sheetnames[0]]
    rows = list(ws.iter_rows(values_only=True))
    wb.close()
    if not rows:
        raise ValueError("Excel 首个工作表为空")

    header = [str(v or "").strip() for v in rows[0]]
    idx = {}
    for key, aliases in HEADER_ALIASES.items():
        for i, h in enumerate(header):
            if h and any(a.lower() == h.lower() or a in h for a in aliases):
                idx[key] = i
                break
    if "module" not in idx or "title" not in idx:
        raise ValueError(f"未能识别「测试模块 / 用例名称」列，实际表头: {header}")

    cases = []
    for r in rows[1:]:
        if not any(v not in (None, "") for v in r):
            continue
        c = {}
        for key, i in idx.items():
            v = r[i] if i < len(r) else None
            c[key] = "" if v is None else str(v).strip()
        cases.append(c)
    return cases


def load_rules(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict) and "rules" in data:
        data = data["rules"]
    if not isinstance(data, list):
        raise ValueError("需求规则清单需为数组，或含 rules 键的对象")
    rules = [r for r in data if isinstance(r, dict) and r.get("type", "included") != "excluded"]
    if not rules:
        raise ValueError("无 included 规则可评审")
    return rules


# ---------------------------------------------------------------- 匹配
def bigrams(s):
    s = re.sub(r"\s+", "", s or "")
    return set(s[i:i + 2] for i in range(len(s) - 1)) if len(s) > 1 else set(s)


def jaccard(a, b):
    A, B = bigrams(a), bigrams(b)
    if not A or not B:
        return 0.0
    return len(A & B) / len(A | B)


def norm_module(m):
    return re.sub(r"^\d+(\.\d+)*\s*", "", m or "").strip()


def case_text(c):
    return " ".join([
        str(c.get("title", "")), str(c.get("steps", "")),
        str(c.get("expected", "")), str(c.get("precondition", "")),
        str(c.get("coverage_rule", "")),
    ])


def classify(c):
    """返回 (是否负向, 是否权限类)。test_type 优先，缺失时用关键词。"""
    tt = str(c.get("test_type", ""))
    text = " ".join([tt, str(c.get("title", "")), str(c.get("steps", ""))])
    is_perm = any(k in text for k in PERM_KEYS)
    if "异常" in tt or "边界" in tt:
        return True, is_perm
    if "权限" in tt:
        return True, True
    if "功能" in tt or "正向" in tt or "正常" in tt:
        return False, is_perm
    return any(k in text for k in NEG_KEYS), is_perm


def suggest_type(text):
    for keys, name in TYPE_HINTS:
        if any(k in text for k in keys):
            return name
    return "等价类划分"


def suggest_priority(text, rule):
    p = str(rule.get("priority", "")).upper()
    if p in ("P0", "P1", "P2", "P3"):
        return p
    for keys, name in PRIORITY_HINTS:
        if any(k in text for k in keys):
            return name
    return "P2"


# ---------------------------------------------------------------- 评审
def audit(cases, rules, top=3, threshold=0.08, module_min=DEFAULT_MODULE_MIN):
    rule_by_id = {r["id"]: r for r in rules if r.get("id")}
    hit_count = {rid: 0 for rid in rule_by_id}          # 强匹配（文本相似度达标 / 显式标注）
    hit_cases = {rid: [] for rid in rule_by_id}
    weak_cases = {rid: [] for rid in rule_by_id}        # 弱匹配（仅模块名相同，需人工确认）

    # 1) 已有 coverage_rule 优先采信（视为强匹配）；未标注的用 bigram + 模块名匹配
    for c in cases:
        cid = str(c.get("id", "")) or "(无编号)"
        explicit = [t.strip() for t in str(c.get("coverage_rule", "")).split(";")
                    if re.fullmatch(r"R-\d+", t.strip()) and t.strip() in rule_by_id]
        if explicit:
            for rid in explicit:
                hit_count[rid] += 1
                hit_cases[rid].append(cid)
            continue
        cm = norm_module(c.get("module", ""))
        ctext = case_text(c)
        scored = []
        for rid, r in rule_by_id.items():
            rim = norm_module(r.get("module", ""))
            mod_hit = bool(cm and rim and (cm in rim or rim in cm))
            jac = jaccard(ctext, r.get("text", ""))
            if jac >= threshold:
                scored.append((1, jac, rid))            # 强：文本相似
            elif mod_hit:
                scored.append((0, 0.15, rid))           # 弱：仅模块相同
        scored.sort(reverse=True)
        for strong, _, rid in scored[:top]:
            if strong:
                hit_count[rid] += 1
                hit_cases[rid].append(cid)
            else:
                weak_cases[rid].append(cid)

    # 2) 按需求侧模块聚合
    mods = {}
    for rid, r in rule_by_id.items():
        m = norm_module(r.get("module", "")) or "(未分模块)"
        d = mods.setdefault(m, {"rules": [], "case_ids": set(), "pos": 0, "neg": 0,
                                "perm": 0, "cases_seen": set()})
        d["rules"].append(rid)
        if hit_count[rid] > 0:
            d["case_ids"].update(hit_cases[rid])

    # 3) 用例侧场景构成（按用例自身模块归集）
    case_mod = {}
    for c in cases:
        m = norm_module(c.get("module", "")) or "(未分模块)"
        case_mod.setdefault(m, []).append(c)
    for m, cs in case_mod.items():
        for c in cs:
            neg, perm = classify(c)
            # 归到最匹配的需求模块（模块名互相包含优先，否则精确同名）
            target = m if m in mods else next(
                (k for k in mods if m and (m in k or k in m)), None)
            if target is None:
                continue
            d = mods[target]
            if id(c) in d["cases_seen"]:
                continue
            d["cases_seen"].add(id(c))
            if neg:
                d["neg"] += 1
            else:
                d["pos"] += 1
            if perm:
                d["perm"] += 1

    rows = []
    for m in sorted(mods):
        d = mods[m]
        total = len(d["rules"])
        covered = sum(1 for rid in d["rules"] if hit_count[rid] > 0)
        ratio = covered / total if total else 0.0
        missing = [rid for rid in d["rules"] if hit_count[rid] == 0]
        weak_only = [rid for rid in missing if weak_cases[rid]]
        status = "❌ 零覆盖" if covered == 0 else ("⚠️ 低于阈值" if ratio < module_min else "✅ 达标")
        rows.append({
            "module": m, "rules_total": total, "rules_covered": covered,
            "coverage": ratio, "status": status,
            "case_count": len(d["case_ids"]) or len(d["cases_seen"]),
            "pos": d["pos"], "neg": d["neg"], "perm": d["perm"],
            "missing": missing, "weak_only": weak_only,
            "nominal": [rid for rid in d["rules"] if hit_count[rid] == 1],
        })

    total_rules = len(rule_by_id)
    covered_rules = sum(1 for rid in rule_by_id if hit_count[rid] > 0)
    return {
        "total_rules": total_rules,
        "covered_rules": covered_rules,
        "overall": covered_rules / total_rules if total_rules else 0.0,
        "modules": rows,
        "rule_by_id": rule_by_id,
        "hit_cases": hit_cases,
        "weak_cases": weak_cases,
        "module_min": module_min,
    }


# ---------------------------------------------------------------- 报告
def render_markdown(res, cases_path, rules_path):
    L = []
    a = L.append
    a("# 用例覆盖率评审报告")
    a("")
    a(f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    a(f"- 用例输入：`{cases_path}`")
    a(f"- 需求输入：`{rules_path}`")
    a(f"- 模块达标阈值：{res['module_min']:.0%}")
    a(f"- 全局覆盖率：**{res['overall']:.1%}**（{res['covered_rules']}/{res['total_rules']} 条需求规则）")
    a("")

    a("## 一、覆盖率概览")
    a("")
    a("| 模块 | 需求功能点数 | 已覆盖 | 覆盖率 | 关联用例数 | 状态 |")
    a("|---|---|---|---|---|---|")
    for r in res["modules"]:
        a(f"| {r['module']} | {r['rules_total']} | {r['rules_covered']} | "
          f"{r['coverage']:.1%} | {r['case_count']} | {r['status']} |")
    a("")

    low = [r for r in res["modules"] if r["coverage"] < res["module_min"]]
    a("## 二、低覆盖模块（重点补充对象）")
    a("")
    if low:
        for r in low:
            extra = f"，其中 {len(r['weak_only'])} 条疑似覆盖待确认" if r["weak_only"] else ""
            a(f"- **{r['module']}**：{r['coverage']:.1%}，缺 {len(r['missing'])} 条规则"
              f"（{r['status']}{extra}）")
    else:
        a("- 无，全部模块达到阈值。")
    a("")

    a("## 三、缺失用例清单（G1）")
    a("")
    if res["covered_rules"] == res["total_rules"]:
        a("无缺失：全部需求规则均有用例覆盖。")
        a("")
    else:
        for r in res["modules"]:
            if not r["missing"]:
                continue
            hard = [rid for rid in r["missing"] if rid not in r["weak_only"]]
            soft = r["weak_only"]
            a(f"### {r['module']}")
            a("")
            if hard:
                a("**完全缺失（无用例覆盖）**")
                a("")
                for i, rid in enumerate(hard, 1):
                    rule = res["rule_by_id"][rid]
                    text = (rule.get("text") or "").strip().replace("\n", " ")
                    a(f"{i}. `{rid}` {text[:80]}")
                    a(f"   - 建议用例类型：{suggest_type(text)}")
                    a(f"   - 建议优先级：{suggest_priority(text, rule)}")
                a("")
            if soft:
                a("**疑似覆盖（仅模块名相同，文本未匹配，需人工确认是否真覆盖）**")
                a("")
                for rid in soft:
                    rule = res["rule_by_id"][rid]
                    text = (rule.get("text") or "").strip().replace("\n", " ")
                    ids = "、".join(res["weak_cases"][rid][:5])
                    a(f"- `{rid}` {text[:70]}　→ 可能相关用例：{ids}")
                a("")

    a("## 四、场景构成缺口（G2）")
    a("")
    a("> 实证配额：每个功能点 **1 条正向 : ≥3 条异常/边界**（含权限校验）。模块级做代理评估。")
    a("")
    a("| 模块 | 正向 | 异常·边界 | 其中权限类 | 负正比 | 判定 |")
    a("|---|---|---|---|---|---|")
    balanced = True
    for r in res["modules"]:
        ratio = (r["neg"] / r["pos"]) if r["pos"] else float("inf")
        rs = "∞" if ratio == float("inf") else f"{ratio:.1f}"
        if r["pos"] == 0 and r["neg"] == 0:
            verdict = "— 无用例（见 G1）"
            a(f"| {r['module']} | {r['pos']} | {r['neg']} | {r['perm']} | {rs} | {verdict} |")
            continue
        if r["neg"] == 0:
            verdict = "❌ 无异常/边界用例"
            balanced = False
        elif r["perm"] == 0:
            verdict = "⚠️ 缺权限校验"
            balanced = False
        elif r["pos"] and ratio < 1.0:
            verdict = "⚠️ 负向偏少"
        else:
            verdict = "✅"
        a(f"| {r['module']} | {r['pos']} | {r['neg']} | {r['perm']} | {rs} | {verdict} |")
    a("")

    nominal = [(r["module"], rid) for r in res["modules"] for rid in r["nominal"]]
    a("## 五、名义覆盖风险（G3）")
    a("")
    if nominal:
        a("以下规则**仅有 1 条用例**覆盖，规则描述跨度大时属「名义覆盖」，建议拆分：")
        a("")
        for m, rid in nominal[:20]:
            rule = res["rule_by_id"][rid]
            a(f"- `{rid}` [{m}] {(rule.get('text') or '')[:70]}")
    else:
        a("无：每条规则至少有 2 条用例或无需拆分。")
    a("")

    a("## 六、总结与建议")
    a("")
    over = res["covered_rules"]
    total = res["total_rules"]
    a(f"1. 全局覆盖 {over}/{total}（{res['overall']:.1%}）；"
      f"{len(low)} 个模块低于 {res['module_min']:.0%}。")
    if low:
        worst = min(low, key=lambda x: x["coverage"])
        a(f"2. 最薄弱模块为 **{worst['module']}**（{worst['coverage']:.1%}），"
          f"优先补 {len(worst['missing'])} 条缺失规则对应用例。")
    no_neg = [r["module"] for r in res["modules"] if r["pos"] + r["neg"] > 0 and r["neg"] == 0]
    no_perm = [r["module"] for r in res["modules"] if r["neg"] > 0 and r["perm"] == 0]
    if not balanced:
        parts = []
        if no_neg:
            parts.append(f"**零异常/边界**的模块 {'、'.join(no_neg)}")
        if no_perm:
            parts.append(f"**有异常但无权限校验**的模块 {'、'.join(no_perm)}")
        a(f"3. 存在 {'；'.join(parts)}，须按「1 正向 : ≥3 异常/边界（含权限）」补齐后才能出库。")
    else:
        a("3. 各模块均已覆盖异常/边界场景，场景结构合理。")
    a("")
    return "\n".join(L)


def render_json(res):
    return json.dumps({
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "overall_coverage": round(res["overall"], 4),
        "total_rules": res["total_rules"],
        "covered_rules": res["covered_rules"],
        "module_min": res["module_min"],
        "modules": [{k: (round(v, 4) if isinstance(v, float) else v)
                     for k, v in r.items() if k != "nominal"} for r in res["modules"]],
    }, ensure_ascii=False, indent=2)


def main():
    ap = argparse.ArgumentParser(
        description="用例覆盖率评审器：用例库(.json/.xlsx) × requirements.json → 模块级覆盖率报告")
    ap.add_argument("cases", help="用例文件（.json 或 .xlsx）")
    ap.add_argument("requirements", help="requirements.json")
    ap.add_argument("-o", "--out", help="报告输出路径（默认打印到 stdout）")
    ap.add_argument("--format", choices=["markdown", "json"], default="markdown")
    ap.add_argument("--module-min", type=float, default=DEFAULT_MODULE_MIN,
                    help="模块覆盖率达标阈值（默认 0.70，低于即列为重点补充对象）")
    ap.add_argument("--top", type=int, default=3, help="每条用例最多匹配的规则数（默认 3）")
    ap.add_argument("--threshold", type=float, default=0.08, help="文本相似度阈值（默认 0.08）")
    args = ap.parse_args()

    try:
        cases = load_cases(args.cases)
        rules = load_rules(args.requirements)
    except Exception as e:
        print(f"[错误] 读取输入失败: {e}", file=sys.stderr)
        return 2
    if not cases:
        print("[错误] 未解析到任何用例", file=sys.stderr)
        return 2

    res = audit(cases, rules, args.top, args.threshold, args.module_min)
    text = render_markdown(res, args.cases, args.requirements) if args.format == "markdown" \
        else render_json(res)

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text + "\n")
        print(f"[✓] 报告已写入 {args.out}")
        print(f"    全局覆盖 {res['covered_rules']}/{res['total_rules']} "
              f"({res['overall']:.1%})，"
              f"{sum(1 for r in res['modules'] if r['coverage'] < args.module_min)} 个模块低于阈值")
    else:
        print(text)

    low = [r for r in res["modules"] if r["coverage"] < args.module_min]
    return 1 if low else 0


if __name__ == "__main__":
    sys.exit(main())
