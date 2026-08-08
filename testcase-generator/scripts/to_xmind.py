#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
to_xmind.py — 将结构化测试用例 JSON 转换为 .xmind（XMind 2020+ 格式）

树结构：根(项目名) → 模块 → 用例（标签 = 优先级，备注 = 前置/步骤/数据/预期/规则/方法）

用法：
  python to_xmind.py cases.json -o report.xmind --project "E-Bike 智能骑行"
  python to_xmind.py cases.json -o report.xmind --project "E-Bike" --no-labels

XMind 2020+ 文件本质是一个 ZIP，含：
  content.json   顶层数组，元素为 sheet
  metadata.json  创建者信息
  manifest.json  文件条目声明
"""

import argparse
import json
import sys
import uuid
import zipfile

VALID_LABELS = {"P0", "P1", "P2", "P3"}


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


def tid():
    return "t-" + uuid.uuid4().hex[:12]


def case_topic(c, with_labels):
    pri = norm_priority(c.get("priority")) or "P2"
    dm = c.get("design_method") or []
    if isinstance(dm, str):
        dm = [dm]

    lines = []
    if c.get("precondition"):
        lines.append("【前置条件】" + c["precondition"])
    if c.get("steps"):
        lines.append("【操作步骤】" + c["steps"])
    if c.get("test_data"):
        d = "; ".join(f"{k}={v}" for k, v in c["test_data"].items())
        lines.append("【测试数据】" + d)
    if c.get("expected"):
        lines.append("【预期结果】" + c["expected"])
    if c.get("coverage_rule"):
        lines.append("【覆盖规则】" + c["coverage_rule"])
    if dm:
        lines.append("【设计方法】" + " / ".join(dm))

    title = f"{c.get('id', '?')} · {pri}"
    topic = {"id": tid(), "class": "topic", "title": title}
    if with_labels and pri in VALID_LABELS:
        topic["labels"] = [pri]
    if lines:
        topic["notes"] = {"plain": {"content": "\n".join(lines)}}
    return topic


def build_content(cases, project, with_labels):
    mods = {}
    for c in cases:
        mods.setdefault(c.get("module", "未分类"), []).append(c)

    root_children = []
    for mod, cs in mods.items():
        root_children.append({
            "id": tid(),
            "class": "topic",
            "title": mod,
            "children": {"attached": [case_topic(c, with_labels) for c in cs]},
        })

    sheet = {
        "id": "sheet-1",
        "class": "sheet",
        "title": project,
        "rootTopic": {
            "id": "root-1",
            "class": "topic",
            "title": project,
            "children": {"attached": root_children},
        },
    }
    return [sheet]


def main():
    ap = argparse.ArgumentParser(description="测试用例 JSON → XMind 2020+")
    ap.add_argument("input", help="用例 JSON 文件路径")
    ap.add_argument("-o", "--output", required=True, help="输出 .xmind 路径")
    ap.add_argument("--project", default="测试用例", help="根节点 / 项目名")
    ap.add_argument("--no-labels", action="store_true", help="不为用例节点添加优先级标签")
    args = ap.parse_args()

    try:
        cases = load_cases(args.input)
    except Exception as e:
        print(f"[错误] {e}", file=sys.stderr)
        return 2

    content = build_content(cases, args.project, not args.no_labels)
    manifest = {
        "file-entries": {
            "content.json": {"full-path": "content.json", "media-type": "application/json"},
            "metadata.json": {"full-path": "metadata.json", "media-type": "application/json"},
        }
    }
    metadata = {
        "creator": {"name": "testcase-generator", "version": "1.0"},
        "dataStructureVersion": 2,
    }

    with zipfile.ZipFile(args.output, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("content.json", json.dumps(content, ensure_ascii=False))
        z.writestr("metadata.json", json.dumps(metadata, ensure_ascii=False))
        z.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False))

    n_mod = len({c.get("module") for c in cases})
    print(f"[✓] 已生成 {args.output}（{len(cases)} 条用例，{n_mod} 个模块）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
