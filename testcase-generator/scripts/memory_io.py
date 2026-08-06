#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
memory_io.py — 测试用例生成 Skill 的项目记忆读写器（越用越懂你）

首次生成后，把歧义判断 / 端类型 / 步骤粒度 / 历史漏测 沉淀到项目
.workbuddy/memory/testcase_writer.md，后续生成先读后写，质量随使用提升。

子命令：
  init    创建记忆文件与四大类模板（若不存在）
  record  追加一条记忆。--category {ambiguity,endpoint,granularity,missed}
          --content "内容" [--date YYYY-MM-DD]
  load    打印记忆文件全文（供 Agent 在 Stage 1/2/4/5 读取）
  show    同 load

用法：
  python memory_io.py init  --root E:/WorkBuddy/Claw
  python memory_io.py record --root E:/WorkBuddy/Claw --category endpoint --content "APP（iOS/Android）"
  python memory_io.py load   --root E:/WorkBuddy/Claw
"""

import argparse
import os
import sys
from datetime import date

SECTIONS = {
    "ambiguity": "## 歧义判断",
    "endpoint": "## 端类型",
    "granularity": "## 步骤粒度",
    "missed": "## 历史漏测",
}
TEMPLATE = """# 测试用例生成记忆（testcase-generator）

> 本文件由 testcase-generator Skill 自动维护，沉淀「决策与偏好」而非具体用例。

## 歧义判断

## 端类型

## 步骤粒度

## 历史漏测
"""


def mem_path(root):
    return os.path.join(root, ".workbuddy", "memory", "testcase_writer.md")


def ensure_file(root):
    p = mem_path(root)
    d = os.path.dirname(p)
    os.makedirs(d, exist_ok=True)
    if not os.path.isfile(p):
        with open(p, "w", encoding="utf-8") as f:
            f.write(TEMPLATE)
    return p


def do_init(root):
    p = ensure_file(root)
    print(f"[✓] 记忆文件就绪：{p}")


def do_record(root, category, content, day):
    if category not in SECTIONS:
        print(f"[错误] 未知类别 {category}，可选：{', '.join(SECTIONS)}", file=sys.stderr)
        return 2
    p = ensure_file(root)
    text = open(p, encoding="utf-8").read()
    sec = SECTIONS[category]
    # 如该类别小节缺失则补建
    if sec not in text:
        text += f"\n{sec}\n"
    # 在该小节下追加一条（定位小节末尾：下一个 ## 之前）
    lines = text.splitlines()
    out = []
    appended = False
    for idx, ln in enumerate(lines):
        out.append(ln)
        if ln.strip() == sec and not appended:
            # 找下一行开始追加
            nxt = lines[idx + 1] if idx + 1 < len(lines) else ""
            if nxt.strip().startswith("- "):
                out.append(f"- {content}（{day}）")
            else:
                out.append(f"- {content}（{day}）")
            appended = True
    if not appended:
        out.append(f"- {content}（{day}）")
    with open(p, "w", encoding="utf-8") as f:
        f.write("\n".join(out).rstrip() + "\n")
    print(f"[✓] 已记录 [{category}] {content}（{day}）→ {p}")
    return 0


def do_load(root):
    p = mem_path(root)
    if not os.path.isfile(p):
        print("（无记忆文件，首次使用。运行 `init` 创建）")
        return 0
    print(open(p, encoding="utf-8").read())
    return 0


def main():
    ap = argparse.ArgumentParser(description="testcase-generator 项目记忆读写器")
    ap.add_argument("cmd", choices=["init", "record", "load", "show"])
    ap.add_argument("--root", default=os.getcwd(), help="项目根目录（默认当前目录）")
    ap.add_argument("--category", help="record 用：ambiguity/endpoint/granularity/missed")
    ap.add_argument("--content", help="record 用：记忆内容")
    ap.add_argument("--date", default=date.today().isoformat(), help="记录日期")
    args = ap.parse_args()

    if args.cmd == "init":
        return do_init(args.root)
    if args.cmd == "record":
        if not args.category or not args.content:
            print("[错误] record 需提供 --category 与 --content", file=sys.stderr)
            return 2
        return do_record(args.root, args.category, args.content, args.date)
    if args.cmd in ("load", "show"):
        return do_load(args.root)
    return 2


if __name__ == "__main__":
    sys.exit(main())
