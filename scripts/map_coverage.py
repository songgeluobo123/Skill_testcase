#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
map_coverage.py — 用例 → 需求规则映射器（让 prescreen 第 1 项覆盖率检查真正可运行）

读取用例集与需求规则清单(requirements.json)，为每条用例匹配其覆盖的需求规则 ID，
写回用例的 coverage_rule 字段，并报告：
  - 覆盖率 = 已覆盖 included 规则数 / included 规则总数
  - 未覆盖的 included 规则清单（建议补充用例）
  - 每条未覆盖规则给出 1 条「建议补充用例」提示

匹配策略：
  1. 模块名子串重叠（用例 module 与规则 module）
  2. 文本字符 bigram Jaccard（用例 steps+expected+coverage_rule vs 规则 text），阈值 0.08
取命中的 top-N 规则 ID 写入 coverage_rule（';' 分隔）。

用法：
  python map_coverage.py test_cases.json requirements.json -o test_cases.json
  python map_coverage.py test_cases.json requirements.json --top 3 --dry-run
"""

import argparse
import json
import re
import sys


def bigrams(s):
    s = re.sub(r"\s+", "", s or "")
    return set(s[i:i + 2] for i in range(len(s) - 1)) if len(s) > 1 else set(s)


def jaccard(a, b):
    A, B = bigrams(a), bigrams(b)
    if not A or not B:
        return 0.0
    return len(A & B) / len(A | B)


def load_cases(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict) and "cases" in data:
        return data["cases"]
    if isinstance(data, list):
        return data
    raise ValueError("用例文件需为数组或含 cases 键的对象")


def main():
    ap = argparse.ArgumentParser(description="用例→需求规则映射器")
    ap.add_argument("cases", help="用例 JSON 文件")
    ap.add_argument("requirements", help="requirements.json")
    ap.add_argument("-o", "--out", help="写回路径（默认不写回，仅报告）")
    ap.add_argument("--top", type=int, default=3)
    ap.add_argument("--threshold", type=float, default=0.08)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    try:
        cases = load_cases(args.cases)
        with open(args.requirements, encoding="utf-8") as f:
            rules = json.load(f)
    except Exception as e:
        print(f"[错误] 读取失败: {e}", file=sys.stderr)
        return 2

    included = [r for r in rules if r.get("type", "included") != "excluded"]
    if not included:
        print("[错误] 无 included 规则可映射", file=sys.stderr)
        return 2

    # 规则索引：按模块名子串
    def mod_key(m):
        return re.sub(r"^\d+(\.\d+)*\s*", "", m or "")

    uncovered = {r["id"]: r for r in included}
    matched = {r["id"]: 0 for r in included}

    for c in cases:
        cm = mod_key(c.get("module", ""))
        ctext = " ".join([str(c.get("steps", "")), str(c.get("expected", "")),
                          str(c.get("coverage_rule", "")), str(c.get("precondition", ""))])
        scores = []
        for r in included:
            rm = mod_key(r.get("module", ""))
            mod_hit = (cm and rm and (cm in rm or rm in cm))
            sim = jaccard(ctext, r["text"])
            if mod_hit:
                sim = max(sim, 0.15)
            if sim >= args.threshold or mod_hit:
                scores.append((sim, r["id"]))
        scores.sort(reverse=True)
        top_ids = [rid for _, rid in scores[:args.top]]
        if top_ids:
            for rid in top_ids:
                uncovered.pop(rid, None)
                matched[rid] = matched.get(rid, 0) + 1
            if not args.dry_run:
                c["coverage_rule"] = ";".join(top_ids)

    covered_n = len(included) - len(uncovered)
    ratio = covered_n / len(included) if included else 0
    print(f"[覆盖率] {ratio:.0%}（已覆盖 {covered_n}/{len(included)} 条 included 规则）")
    if uncovered:
        print(f"\n[未覆盖 {len(uncovered)} 条] 建议补充用例：")
        for r in uncovered.values():
            print(f"  - {r['id']} [{r['module']}] {r['text'][:60]}")
    else:
        print("[✓] 全部 included 规则均已覆盖")

    if not args.dry_run and args.out:
        # 保留原始文件结构
        with open(args.cases, encoding="utf-8") as f:
            raw = json.load(f)
        if isinstance(raw, dict) and "cases" in raw:
            raw["cases"] = cases
            out_data = raw
        else:
            out_data = cases
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(out_data, f, ensure_ascii=False, indent=2)
        print(f"\n[✓] 已写回 coverage_rule → {args.out}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
