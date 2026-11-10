#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""doc_stats.py — 文档里的"计数"不再靠手工维护。

治的是这一类反复出现的缺陷：加了脚本忘了改 README 的「16 个」、加了闸门忘了改
「13 项」、加了 lint 规则忘了改「L1–L9」。手工计数每加一个文件要记得改 4~6 处，
漏一次的后果是**文档在骗人，而没人发现**。

做法：计数只从代码/目录派生，`--check` 校验、`--apply` 自动回写。

  python scripts/doc_stats.py --check     # 只检查，有漂移 exit 1（适合放进 CI）
  python scripts/doc_stats.py --apply     # 直接把文档里的数字改对

退出码：0 一致（或已修复）｜1 存在漂移（--check）｜2 输入/参数错误｜3 脚本崩溃

口径（唯一真相源）：
  references 数   = references/*.md 的文件数
  scripts 数      = scripts/*.py 的文件数
  预审项数        = prescreen.py 主流程里 `# NN. ` 形式的检查项注释数
  矩阵规则数      = matrix_lint.py 里出现过的 L 代号（L1/L1b/L2…）的最大编号
"""
import argparse
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.environ.get("TC_SKILL") or os.path.dirname(HERE)


def read(p):
    return io.open(p, encoding="utf-8").read()


def count_references():
    d = os.path.join(SKILL, "references")
    return len([f for f in os.listdir(d) if f.endswith(".md")])


def count_scripts():
    d = os.path.join(SKILL, "scripts")
    return len([f for f in os.listdir(d) if f.endswith(".py")])


def count_prescreen_items():
    """数主流程里的检查项注释，形如 '    # 14. 范围性用例（M4 兜底）...'。

    比"数文档里写了几行表格"可靠：表格会漏行，注释漏了脚本本身就没编号。
    """
    src = read(os.path.join(SKILL, "scripts", "prescreen.py"))
    nums = [int(m.group(1)) for m in re.finditer(r"^    # (\d+)\. ", src, re.M)]
    return max(nums) if nums else 0


def count_matrix_rules():
    src = read(os.path.join(SKILL, "scripts", "matrix_lint.py"))
    nums = [int(x) for x in re.findall(r"\bL(\d+)b?\b", src)]
    return max(nums) if nums else 0


def stats():
    return {
        "references": count_references(),
        "scripts": count_scripts(),
        "prescreen_items": count_prescreen_items(),
        "matrix_rules": count_matrix_rules(),
    }


# (相对路径, 正则, 取值键)：正则里用命名组 `n` 标出"那个该被改的数字"，
# 其余部分原样保留。用命名组而不是按序号取，是因为这些模式里前缀本身常带括号。
def rules(s):
    P, R, S, M = (s["prescreen_items"], s["references"],
                  s["scripts"], s["matrix_rules"])
    return [
        # ---- 预审项数 ----
        ("scripts/prescreen.py", r"质量预审器（(?P<n>\d+) 项闸门）", P),
        ("scripts/prescreen.py", r"正式生成前的 (?P<n>\d+) 项闸门）", P),
        ("references/quality_prescreen.md", r"^## (?P<n>\d+) 项检查 \+ 默认阈值", P),
        ("SKILL.md", r"共 \*\*(?P<n>\d+)\*\* 项", P),
        ("README.md", r"质量预审闸门（(?P<n>\d+) 项）", P),
        ("README.md", r"# 质量预审 (?P<n>\d+) 项闸门与阈值", P),
        ("README.md", r"prescreen\.py             # 质量预审闸门（(?P<n>\d+) 项）", P),
        ("README.md", r"# 4\. 质量预审闸门（(?P<n>\d+) 项", P),
        ("README.en.md", r"Quality prescreen gate \((?P<n>\d+) checks\)", P),
        ("README.en.md", r"# Quality prescreen (?P<n>\d+) gates & thresholds", P),
        ("README.en.md", r"prescreen\.py             # Quality prescreen gate \((?P<n>\d+) checks\)", P),
        ("README.en.md", r"# 4\. quality prescreen gate \((?P<n>\d+) checks", P),
        ("references/workflow.md", r"prescreen\.py（(?P<n>\d+) 项检查", P),
        # ---- scripts 数 ----
        ("README.md", r"# 可执行脚本（(?P<n>\d+) 个，Python", S),
        ("README.en.md", r"# Executable scripts \((?P<n>\d+), Python", S),
        # ---- references 数 ----
        ("README.md", r"参考文档（(?P<n>\d+) 篇）", R),
        ("README.en.md", r"Reference docs \((?P<n>\d+) files\)", R),
        # ---- 矩阵规则数 ----
        ("SKILL.md", r"lint 规则 L1[–\-]L(?P<n>\d+)", M),
        ("references/equivalence_matrix.md", r"L1[–\-]L(?P<n>\d+)", M),
    ]


def main():
    ap = argparse.ArgumentParser(description="文档计数一致性检查 / 自动回写")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--check", action="store_true", help="只检查，有漂移返回 1")
    g.add_argument("--apply", action="store_true", help="把文档里的数字改成实际值")
    ap.add_argument("--format", choices=["text", "json"], default="text")
    args = ap.parse_args()

    if not os.path.isdir(SKILL):
        print(f"[错误] 技能目录不存在: {SKILL}", file=sys.stderr)
        return 2

    s = stats()
    if args.format == "text":
        print(f"实测：references {s['references']} 篇 / scripts {s['scripts']} 个 / "
              f"预审 {s['prescreen_items']} 项 / 矩阵规则 L1–L{s['matrix_rules']}")

    drift, missing = [], set()
    cache = {}

    def fix(m, want):
        whole = m.group(0)
        return whole[:m.start("n") - m.start()] + str(want) + whole[m.end("n") - m.start():]

    for rel, pat, want in rules(s):
        p = os.path.join(SKILL, rel)
        if not os.path.exists(p):
            missing.add(rel)
            continue
        if p not in cache:
            cache[p] = read(p)
        text = cache[p]
        for m in re.finditer(pat, text, re.M):
            if int(m.group("n")) != want:
                drift.append((rel, m.group(0), want))
        cache[p] = re.sub(pat, lambda m, w=want: fix(m, w), text, flags=re.M)

    for rel in sorted(missing):
        print(f"[!] 跳过（文件不存在）: {rel}")

    if not drift:
        if args.format == "text":
            print("[OK] 全部计数与代码一致")
        else:
            print('{"drift": 0, "ok": true}')
        return 0

    for rel, got, want in drift:
        print(f"[漂移] {rel}: 「{got}」应为 {want}")

    if args.apply:
        for p, text in cache.items():
            io.open(p, "w", encoding="utf-8", newline="\n").write(text)
        print(f"\n[已回写] {len(drift)} 处计数")
        return 0

    print(f"\n共 {len(drift)} 处漂移；用 --apply 自动修正")
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception:
        import traceback
        print("\n[内部错误] doc_stats.py 自身崩溃（exit 3），不是数据不达标。", file=sys.stderr)
        traceback.print_exc()
        sys.exit(3)
