#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
prescreen.py — 测试用例质量预审器（正式生成前的 8 项闸门）

检查项（详见 references/quality_prescreen.md）：
  1. 需求覆盖率 >= coverage_min（需 --requirement-rules 提供需求规则清单）
  2. P0 占比（最高优先级）在 [p0_min, p0_max]（安全攸关软件上调）
  3. P2 占比在 [p2_min, p2_max]
  4. 每条用例关联至少 1 种测试设计方法（design_method 非空且合法，6 方法之一或多）
  5. 无凭空编造（coverage_rule 必须落在需求规则清单内）
  6. 无语义重复（同 module+steps+expected 去重）
  7. 预期结果可判定（无"合理/美观/流畅"类不可判定词；缺断言标志仅告警）
  8. 标题规范与残缺检查（≤20 字 / 无编号前缀 / 无【】 / 无句末标点 / 无占位残留；
     缺标题或缺步骤即阻断；重名标题仅告警）

退出码：
  0  —— 全部通过（或仅警告）
  1  —— 存在不达标项（需修正后重跑）
  2  —— 输入/参数错误

用法：
  python prescreen.py cases.json --requirement-rules requirements.json
  python prescreen.py cases.json --p0-min 0.40 --p0-max 0.60
  python prescreen.py cases.json            # 仅做 2/3/4/6/7/8 检查

优先级采用 P0-P3（P0 最高，一票否决）；全技能统一，无 P4。
可判定性与标题检查的实证依据见 references/excellent_case_patterns.md。
"""

import argparse
import json
import re
import sys

DESIGN_METHODS = {"等价类划分", "边界值分析", "场景法", "状态迁移法", "判定表法", "正交分析法", "错误推测"}
PRIORITIES = {"P0", "P1", "P2", "P3"}

# 检查 7：不可判定词（见到即改，见 excellent_case_patterns.md 三、反面清单）
UNJUDGEABLE_WORDS = [
    "合理", "美观", "友好", "流畅", "良好", "正常显示", "显示正常", "工整", "整齐",
    "尽量", "适当", "无异常", "不卡顿", "体验好", "清晰明了", "符合预期", "正确无误",
]
# 检查 7：可判定标志（应/必须/需/数值/阈值/逐字文案/清单编号）
ASSERT_MARKERS = re.compile(r"应|必须|需|为[:：]|=\s*\d|>\s*\d|<\s*\d|\d|1[.、]|提示|显示为|保持")
# 检查 8：标题占位残留
TITLE_PLACEHOLDER = re.compile(r"待.{0,6}更新|TBD|TODO|XXX+|xxxx|【】|\[\]", re.IGNORECASE)



def norm_priority(p):
    return (p or "").strip().upper()


def load_cases(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict) and "cases" in data:
        return data["cases"]
    if isinstance(data, list):
        return data
    raise ValueError("输入需为用例数组，或含 'cases' 键的对象")


def norm(s):
    return re.sub(r"\s+", "", s or "")


def main():
    ap = argparse.ArgumentParser(description="测试用例质量预审器（8 项闸门）")
    ap.add_argument("input", help="用例 JSON 文件路径")
    ap.add_argument("--requirement-rules", help="需求规则清单 JSON（字符串数组）")
    ap.add_argument("--coverage-min", type=float, default=0.95)
    ap.add_argument("--p0-min", type=float, default=0.10)
    ap.add_argument("--p0-max", type=float, default=0.15)
    ap.add_argument("--p2-min", type=float, default=0.35)
    ap.add_argument("--p2-max", type=float, default=0.45)
    args = ap.parse_args()

    try:
        cases = load_cases(args.input)
    except Exception as e:
        print(f"[错误] 读取/解析输入失败: {e}", file=sys.stderr)
        return 2
    if not cases:
        print("[错误] 未找到任何用例", file=sys.stderr)
        return 2

    fails = []
    warns = []
    total = len(cases)

    # 1. 需求覆盖率（按规则 ID 匹配，支持 requirements.json 字符串列表）
    rule_ids = set()
    if args.requirement_rules:
        try:
            with open(args.requirement_rules, encoding="utf-8") as f:
                raw_rules = json.load(f)
        except Exception as e:
            print(f"[错误] 读取需求规则清单失败: {e}", file=sys.stderr)
            return 2
        if isinstance(raw_rules, dict) and "rules" in raw_rules:
            raw_rules = raw_rules["rules"]

        def rid_of(x):
            if isinstance(x, dict):
                return str(x.get("id", "")).strip()
            m = re.search(r"R-\d+", str(x))
            return m.group(0) if m else ""

        rule_ids = {rid_of(x) for x in raw_rules if rid_of(x)}
        covered_ids = set()
        for c in cases:
            for tok in str(c.get("coverage_rule", "")).split(";"):
                tok = tok.strip()
                if re.fullmatch(r"R-\d+", tok) and tok in rule_ids:
                    covered_ids.add(tok)
        ratio = len(covered_ids) / len(rule_ids) if rule_ids else 0
        if ratio < args.coverage_min:
            fails.append(f"需求覆盖率 {ratio:.0%} < 阈值 {args.coverage_min:.0%}（已覆盖 {len(covered_ids)}/{len(rule_ids)}）")
        else:
            print(f"[✓] 需求覆盖率 {ratio:.0%}（{len(covered_ids)}/{len(rule_ids)}）")
    else:
        linked = sum(1 for c in cases if (c.get("coverage_rule") or "").strip())
        print(f"[!] 未提供需求规则清单，跳过真实覆盖率计算；用例规则关联率 {linked/total:.0%}（仅供参考）")
        warns.append("未提供 --requirement-rules，覆盖率检查跳过")

    # 2/3. 优先级占比
    cnt = {p: sum(1 for c in cases if norm_priority(c.get("priority")) == p)
           for p in PRIORITIES}
    p0r = cnt["P0"] / total
    p2r = cnt["P2"] / total
    if not (args.p0_min <= p0r <= args.p0_max):
        fails.append(f"P0 占比 {p0r:.0%} 不在 [{args.p0_min:.0%},{args.p0_max:.0%}]（当前 {cnt['P0']} 条）")
    else:
        print(f"[✓] P0 占比 {p0r:.0%}（{cnt['P0']} 条）")
    if not (args.p2_min <= p2r <= args.p2_max):
        fails.append(f"P2 占比 {p2r:.0%} 不在 [{args.p2_min:.0%},{args.p2_max:.0%}]（当前 {cnt['P2']} 条）")
    else:
        print(f"[✓] P2 占比 {p2r:.0%}（{cnt['P2']} 条）")

    # 4. 设计方法关联
    bad_dm = []
    for c in cases:
        dm = c.get("design_method")
        if isinstance(dm, str):
            dm = [dm]
        if not dm or not (set(dm) & DESIGN_METHODS):
            bad_dm.append(c.get("id", "?"))
    if bad_dm:
        fails.append(f"{len(bad_dm)} 条用例未关联合法测试设计方法"
                     f"（6 方法之一或多）: {bad_dm[:10]}")
    else:
        print(f"[✓] 全部 {total} 条用例均关联测试设计方法")

    # 5. 编造场景（coverage_rule 中的 R-xxx 必须落在需求清单内）
    if args.requirement_rules:
        fab = []
        for c in cases:
            for tok in str(c.get("coverage_rule", "")).split(";"):
                tok = tok.strip()
                if re.fullmatch(r"R-\d+", tok) and tok not in rule_ids:
                    fab.append((c.get("id", "?"), tok))
        if fab:
            fails.append(f"{len(fab)} 条用例覆盖规则不在需求清单内（疑似编造）: {fab[:10]}")
        else:
            print(f"[✓] 无编造场景")

    # 6. 语义重复
    seen = {}
    for c in cases:
        key = (c.get("module", ""), norm(c.get("steps", "")), norm(c.get("expected", "")))
        seen.setdefault(key, []).append(c.get("id", "?"))
    dups = [v for v in seen.values() if len(v) > 1]
    if dups:
        fails.append(f"存在 {len(dups)} 组语义重复用例: {dups[:5]}")
    else:
        print(f"[✓] 无语义重复用例")

    # 7. 预期结果可判定（不可判定词一票否决；缺断言标志仅告警）
    vague, no_marker = [], []
    for c in cases:
        exp = str(c.get("expected", "") or "")
        if not exp.strip():
            vague.append((c.get("id", "?"), "预期为空"))
            continue
        hit = [w for w in UNJUDGEABLE_WORDS if w in exp]
        if hit:
            vague.append((c.get("id", "?"), "/".join(hit[:3])))
        elif not ASSERT_MARKERS.search(exp):
            no_marker.append(c.get("id", "?"))
    if vague:
        fails.append(f"{len(vague)} 条用例预期结果不可判定（命中不可判定词或为空）: {vague[:10]}")
    else:
        print(f"[✓] 全部 {total} 条用例预期结果可判定")
    if no_marker:
        warns.append(f"{len(no_marker)} 条用例预期缺少断言标志（应/数值/逐字文案/清单编号），建议改写: {no_marker[:10]}")

    # 8. 标题规范与残缺检查
    bad_title, no_steps, placeholder = [], [], []
    title_map = {}
    for c in cases:
        cid = c.get("id", "?")
        t = str(c.get("title", "") or "").strip()
        if not t:
            bad_title.append((cid, "标题为空"))
        else:
            reason = None
            if len(t) > 20:
                reason = f"超长 {len(t)} 字"
            elif re.match(r"^\s*\d+\s*[、.．]", t):
                reason = "含序号前缀"
            elif "【" in t or "】" in t:
                reason = "含【】标记"
            elif re.search(r"[，。；！？,;!?]\s*$", t):
                reason = "含句末标点"
            if reason:
                bad_title.append((cid, reason))
            if TITLE_PLACEHOLDER.search(t):
                placeholder.append((cid, t))
            title_map.setdefault((c.get("module", ""), norm(t)), []).append(cid)
        if not str(c.get("steps", "") or "").strip():
            no_steps.append(cid)

    if bad_title:
        fails.append(f"{len(bad_title)} 条用例标题不合规（≤20 字 / 无序号前缀 / 无【】 / 无句末标点）: {bad_title[:10]}")
    else:
        print(f"[✓] 全部 {total} 条用例标题合规")
    if no_steps:
        fails.append(f"{len(no_steps)} 条用例缺失测试步骤（残缺条目不得入库）: {no_steps[:10]}")
    if placeholder:
        fails.append(f"{len(placeholder)} 条用例标题含占位残留（待XX更新/TBD/XXX）: {placeholder[:5]}")
    dup_titles = [(k[1], v) for k, v in title_map.items() if len(v) > 1]
    if dup_titles:
        warns.append(f"{len(dup_titles)} 组同模块标题重名，须靠唯一用例编号区分: {dup_titles[:5]}")

    print()
    if fails:
        print("=== 预审不通过，需修正后重跑 ===")
        for f in fails:
            print(f"  ✗ {f}")
        for w in warns:
            print(f"  ! {w}")
        return 1
    print("=== 预审全部通过 ===")
    for w in warns:
        print(f"  ! {w}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
