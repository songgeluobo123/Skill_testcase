#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
read_xmind.py — 读取 .xmind 需求树（Step 1 需求输入解析，替代 xmind-reader）

XMind 2020+ 文件本质是 ZIP，含 content.json（顶层数组，元素为 sheet）。
每个 sheet 有 rootTopic，其 children.attached 为子节点（递归）。

用法：
  python read_xmind.py "test_input/v1.11 需求/prd/需求.xmind" -f tree
  python read_xmind.py "*.xmind" -f tree            # 支持通配（取首个匹配）
  python read_xmind.py req.xmind -o req_tree.json    # 输出结构化 JSON
  python read_xmind.py req.xmind --with-notes       # 树中附上节点备注

退出码：0 成功，2 输入/参数错误。
"""

import argparse
import glob
import json
import sys
import zipfile


def load_topics(xmind_path):
    with zipfile.ZipFile(xmind_path) as z:
        if "content.json" not in z.namelist():
            raise ValueError("不是合法的 XMind 2020+ 文件（缺 content.json）")
        content = json.loads(z.read("content.json"))
    sheets = content if isinstance(content, list) else content.get("sheet", [content])
    out = []
    for sh in sheets:
        root = sh.get("rootTopic", {})
        out.append({
            "sheet": sh.get("title", "Sheet"),
            "root": _topic_tree(root),
        })
    return out


def _topic_tree(node):
    title = node.get("title", "")
    notes = ""
    n = node.get("notes")
    if isinstance(n, dict):
        notes = (n.get("plain") or {}).get("content", "") or (n.get("html") or {}).get("content", "")
    children = []
    ch = node.get("children")
    if isinstance(ch, dict):
        for c in ch.get("attached", []) or []:
            children.append(_topic_tree(c))
    labels = node.get("labels", []) or []
    return {"title": title, "labels": labels, "notes": notes, "children": children}


def print_tree(sheets, with_notes=False, _depth=0):
    for sh in sheets:
        if len(sheets) > 1:
            print(("# " if _depth == 0 else "") + sh["sheet"])
        _walk(sh["root"], _depth, with_notes)


def _walk(node, depth, with_notes):
    pad = "  " * depth
    label = (" [" + ",".join(node["labels"]) + "]") if node["labels"] else ""
    print(f"{pad}- {node['title']}{label}")
    if with_notes and node["notes"]:
        for line in node["notes"].splitlines():
            if line.strip():
                print(f"{pad}    > {line}")
    for c in node["children"]:
        _walk(c, depth + 1, with_notes)


def main():
    ap = argparse.ArgumentParser(description="读取 .xmind 需求树")
    ap.add_argument("input", help=".xmind 路径，或通配符（取首个匹配）")
    ap.add_argument("-f", "--format", choices=["tree", "json"], default="tree")
    ap.add_argument("-o", "--output", help="输出 JSON 文件路径（format=json 时必填或默认打印）")
    ap.add_argument("--with-notes", action="store_true", help="树中附上节点备注")
    args = ap.parse_args()

    path = args.input
    if not path.endswith(".xmind"):
        matches = sorted(glob.glob(path))
        if not matches:
            print(f"[错误] 未找到匹配文件: {path}", file=sys.stderr)
            return 2
        path = matches[0]

    try:
        sheets = load_topics(path)
    except Exception as e:
        print(f"[错误] 读取 xmind 失败: {e}", file=sys.stderr)
        return 2

    if args.format == "tree":
        print_tree(sheets, args.with_notes)
    else:
        out = json.dumps(sheets, ensure_ascii=False, indent=2)
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(out)
            print(f"[✓] 已写出需求树 JSON: {args.output}")
        else:
            print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
