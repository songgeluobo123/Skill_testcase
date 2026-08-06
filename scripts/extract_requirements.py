#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
extract_requirements.py — Stage 1 需求规则清单抽取器

从 PRD 文档(.md/.txt，尽力支持 .docx)中抽取结构化「需求规则清单」，供
prescreen.py 的覆盖率检查(第 1 项)与用例-规则映射(map_coverage.py)使用。

抽取来源：
  - 表格（功能对比表、参数表、状态表…）
  - 列表项（bullet / 编号）
  - 代码块中的决策规则行（含 → / ├ / └ / 触发 / 持续 / 丢弃 / 切断 / 锁定…）
  - 含强约束关键词的普通段落（必须 / 禁止 / 不支持 / 仅 / ❌ …）

规则粒度（关键设计：表头-数据行合并）：
  默认开启「表格合并」——一个 markdown 表格（表头 + 其下所有数据行）被合并为
  「一条」需求规则。因为对测试而言，一个表格本质是一句需求陈述（如「骑行模式
  档位范围表」），其每行只是该陈述的规格实例。合并后：
    - 覆盖率分母 = 需求陈述级（表格数 + 列表项数 + 代码规则数 + 强约束段数），
      而非被每行表格拆碎的细粒度，更接近"这条需求有没有被用例覆盖"。
    - 一条命中该表概念的用例即视为覆盖整条表格需求，避免"覆盖了 3 行却说漏了 7 行"。
  可用 --no-merge-tables 关闭，回到「表格每行独立成规则」的旧行为做对照。

规则类型：
  - included ：MVP 包含的功能/约束规则（计入覆盖率分母）
  - excluded ：§11.2「不包含」等排除项（不计入覆盖率分母）

输出：
  requirements.json      — 富对象列表 [{id, module, section, type, text, source_line}]
  requirement_rules.json — 供 prescreen 的字符串列表 ["R-001 | <module> | <text>", ...]（仅 included）
  requirements.md         — 人读的需求规则清单

用法：
  python extract_requirements.py PRD.md
  python extract_requirements.py PRD.md -o ./out
  python extract_requirements.py PRD.md --no-merge-tables   # 对照用：表格每行独立成规则
"""

import argparse
import json
import os
import re
import sys

EXCLUDE_SEC_HINTS = ("11.2",)          # 章节号前缀，命中即排除项
STRONG_KW = ("必须", "禁止", "不支持", "仅", "❌", "不可覆写", "硬件级")


def read_text(path):
    if path.lower().endswith(".docx"):
        try:
            import docx  # python-docx
            return "\n".join(p.text for p in docx.Document(path).paragraphs)
        except Exception:
            try:
                import zipfile
                z = zipfile.ZipFile(path)
                xml = z.read("word/document.xml").decode("utf-8", "ignore")
                return re.sub(r"<[^>]+>", "\n", xml)
            except Exception as e:
                print(f"[warn] docx 解析失败，按纯文本读取: {e}", file=sys.stderr)
    with open(path, encoding="utf-8", errors="ignore") as f:
        return f.read()


def clean(t):
    t = re.sub(r"`([^`]*)`", r"\1", t)
    t = re.sub(r"\*\*([^*]+)\*\*", r"\1", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def heading_module(text):
    m = re.match(r"^(#{1,6})\s+(.*)$", text)
    if not m:
        return None
    body = re.sub(r"^\d+(\.\d+)*\s*", "", m.group(2)).strip()
    return body


def is_table_row(line):
    s = line.strip()
    return s.startswith("|") and not re.match(r"^\|[\s:|-]+\|?$", s)


def is_separator(line):
    return bool(re.match(r"^\|[\s:|-]+\|?$", line.strip()))


def is_decorative(line):
    # 纯装饰框线（仅含 ─│├└ 等 + 空格），无实际语义
    return re.sub(r"[│├└┤┐┌┘─\s]", "", line) == ""


def parse_table_row(line):
    return [c.strip() for c in line.strip().strip("|").split("|")]


def find_table_blocks(lines, code_lines):
    """返回表格块区间 [start, end) 列表；排除代码块内的 | 行（如 ASCII 树）。"""
    blocks = []
    i, n = 0, len(lines)
    while i < n:
        if i in code_lines:
            i += 1
            continue
        if is_table_row(lines[i]) or is_separator(lines[i]):
            j = i
            while j < n and (j not in code_lines) and \
                  (is_table_row(lines[j]) or is_separator(lines[j])):
                j += 1
            # 至少两行（表头+分隔符 或 多行数据）；单行非分隔符也视为单表
            if j - i >= 2 or (j - i == 1 and not is_separator(lines[i])):
                blocks.append((i, j))
            i = j
        else:
            i += 1
    return blocks


def merged_table_text(lines, s, e):
    """将一个表格块合并为单条需求规则文本：表【表头】：数据行1；数据行2；..."""
    rows = []
    for k in range(s, e):
        ln = lines[k]
        if is_separator(ln):
            continue
        cells = [c for c in parse_table_row(ln) if c]
        if cells:
            rows.append(cells)
    if not rows:
        return None
    if len(rows) == 1:
        return "表：" + " | ".join(rows[0])
    header, data = rows[0], rows[1:]
    return "表【" + " | ".join(header) + "】：" + "；".join(" | ".join(r) for r in data)


def main():
    ap = argparse.ArgumentParser(description="Stage 1 需求规则清单抽取器")
    ap.add_argument("prd", help="PRD 文件路径 (.md/.txt/.docx)")
    ap.add_argument("-o", "--out", default=".", help="输出目录 (默认当前目录)")
    ap.add_argument("--no-merge-tables", action="store_true",
                    help="关闭表格合并：表格每行独立成规则（旧行为，用于对照）")
    args = ap.parse_args()

    if not os.path.isfile(args.prd):
        print(f"[错误] 找不到文件: {args.prd}", file=sys.stderr)
        return 2

    text = read_text(args.prd)
    lines = text.splitlines()

    # 预计算代码块行（用于把代码块内的 | 排除出表格检测，并供主循环跳过围栏行）
    in_code = False
    code_lines = set()
    for i, raw in enumerate(lines):
        if raw.strip().startswith("```"):
            in_code = not in_code
            code_lines.add(i)
        elif in_code:
            code_lines.add(i)

    if args.no_merge_tables:
        blocks = []
    else:
        blocks = find_table_blocks(lines, code_lines)
    block_lines = set()
    for (s, e) in blocks:
        block_lines.update(range(s, e))
    block_starts = {s: (s, e) for (s, e) in blocks}

    # 表头行（其下一行为分隔符）——仅 --no-merge-tables 时用于跳过表头
    header_idx = {j for j in range(len(lines) - 1)
                  if is_table_row(lines[j]) and is_separator(lines[j + 1])}

    rules = []
    seen = set()
    cur_mod = "(未分类)"
    cur_sec = ""
    excluded = False
    rid = 0

    def add(text_cand, line_no):
        nonlocal rid
        cand = clean(text_cand)
        if len(cand) < 4 or cand in seen:
            return
        seen.add(cand)
        rid += 1
        rules.append({
            "id": f"R-{rid:03d}",
            "module": cur_mod,
            "section": cur_sec,
            "type": "excluded" if excluded else "included",
            "text": cand,
            "source_line": line_no,
        })

    for i, raw in enumerate(lines, 1):
        idx = i - 1
        # 表格块：合并为单条规则（表头+数据行）
        if idx in block_lines:
            if idx in block_starts:
                txt = merged_table_text(lines, *block_starts[idx])
                if txt:
                    add(txt, i)
            continue

        line = raw.rstrip()
        if re.match(r"^#{1,6}\s+", line):
            cur_mod = heading_module(line) or cur_mod
            msec = re.search(r"^\#{1,6}\s+(\d+(?:\.\d+)*)", line)
            cur_sec = msec.group(1) if msec else cur_sec
            excluded = cur_sec.startswith(EXCLUDE_SEC_HINTS) or ("不包含" in line)
            in_code = False
            continue
        if line.strip().startswith("```"):
            in_code = not in_code
            continue
        if is_table_row(line):
            # 仅 --no-merge-tables 路径会到达此处（合并模式下表格已被 block_lines 拦截）
            if (i - 1) in header_idx:
                continue
            cells = [c for c in parse_table_row(line) if c]
            add(" | ".join(cells), i)
            continue
        m = re.match(r"^\s*[-*]\s+(.*)$", line)
        if m:
            add(m.group(1), i)
            continue
        if in_code:
            s = clean(line)
            if not s:
                continue
            if is_decorative(s):
                continue
            if re.search(r"(→|├|└|│|触发|持续|丢弃|切断|锁定|>=|<=)", s) or \
               any(k in s for k in ("触发", "持续", "丢弃", "切断", "锁定", "限制", "降级", "切换")):
                add(s, i)
            continue
        # 强约束关键词段落
        if any(k in line for k in STRONG_KW):
            add(line, i)

    # 输出
    os.makedirs(args.out, exist_ok=True)
    rich_path = os.path.join(args.out, "requirements.json")
    rules_path = os.path.join(args.out, "requirement_rules.json")
    md_path = os.path.join(args.out, "requirements.md")

    with open(rich_path, "w", encoding="utf-8") as f:
        json.dump(rules, f, ensure_ascii=False, indent=2)

    included = [r for r in rules if r["type"] == "included"]
    with open(rules_path, "w", encoding="utf-8") as f:
        json.dump([f"{r['id']} | {r['module']} | {r['text']}" for r in included],
                  f, ensure_ascii=False, indent=2)

    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# 需求规则清单（自动抽取）\n\n")
        mode = "表格合并（需求陈述级）" if not args.no_merge_tables else "表格每行独立"
        f.write(f"- 抽取模式：{mode}\n")
        f.write(f"- 总规则数：{len(rules)}（included={len(included)}，excluded={len(rules)-len(included)}）\n\n")
        last_mod = None
        for r in rules:
            if r["module"] != last_mod:
                f.write(f"\n## {r['module']}（§{r['section']}）\n")
                last_mod = r["module"]
            tag = "【排除】" if r["type"] == "excluded" else ""
            f.write(f"- {r['id']} {tag}{r['text']}\n")

    print(f"[✓] 抽取规则 {len(rules)} 条（included={len(included)}，excluded={len(rules)-len(included)}）"
          f"  模式={'合并' if not args.no_merge_tables else '不合并'}")
    print(f"    ├ requirements.json      ({rich_path})")
    print(f"    ├ requirement_rules.json({rules_path})")
    print(f"    └ requirements.md        ({md_path})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
