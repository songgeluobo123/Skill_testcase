#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
input_readiness.py — 输入完备度自检（M8）

解决的问题：
  用例生成完只有 196 条，事后才争论"是不是漏了"。
  本脚本在**开工前**把四类输入的到位情况探明，并把"缺一类输入 = 少多少条用例"
  显式量化。损失定位在输入侧，而不是回到用例侧反复返工。

四类输入（只用文件存在性 + 内容特征判定，不联网）：
  dictionary  数据字典/字段表  → 缺则等价类只能划 3 档，字段级边界写不出
  prototype   原型/UI 设计稿   → 缺则 UI 元素级用例（控件状态/文案/布局/反馈）写不出
  api         自有云 API 文档  → 缺则接口级参数校验/状态码/幂等/鉴权用例写不出
  defect      历史缺陷/TAPD    → 缺则回归题库与缺陷易复发场景无从下手

用法：
  python input_readiness.py --prd 需求目录
  python input_readiness.py --prd 需求目录 --require dictionary,prototype
  python input_readiness.py --prd 需求目录 -o 输入完备度报告.md
  python input_readiness.py --prd 需求目录 --format json
  python input_readiness.py --prd 需求目录 --strict      # CI 用：不足 4/4 即失败

退出码：默认恒 0（观测工具，不做闸门）；--strict 且完备度 < 满分 → 1；目录不存在 → 2。
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime

DOC_EXTS = {".md", ".markdown", ".txt", ".doc", ".docx"}
SHEET_EXTS = {".xlsx", ".xlsm", ".xls", ".csv", ".tsv"}
JSON_EXTS = {".json"}
IMG_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}
TEXT_EXTS = DOC_EXTS | {".csv", ".tsv", ".json"}

# 基准：47 条需求 / 196 条用例库的实测回放（单一项目实测，可按项目规模等比缩放）
BASE_CASES = 196
BASE_RULES = 47

PLACEHOLDER_RE = re.compile(r"^(待补充|待定|待确认|暂无|无|空|todo|tbd|none|null|n/?a|-+|—+|/+|\*+)$", re.I)

# key: (中文名, 缺失可回收上限(低,高), 缺失影响, 补充动作, 投入产出比)
CATS = [
    ("dictionary", "数据字典/字段表", (40, 60), 1.5,
     "无字段表 → 等价类只能划「有/无/异常」3 档，无法按长度/类型/格式/枚举划等价类与边界值，字段级用例整体缺失",
     "补一页字段表（Excel 即可）：字段名 / 类型 / 长度 / 必填 / 取值范围或枚举 / 校验失败文案。"
     "只需覆盖核心实体（账号、车辆、订单等）的主表，不必求全。投入最小、回收最大，优先做。"),
    ("prototype", "原型/UI 设计稿", (50, 80), 1.2,
     "无原型 → UI 元素级用例写不出：控件状态（禁用/置灰/加载中）、文案、布局与自适应、交互反馈均无从设计，用例只能停在流程级",
     "补齐可访问的原型链接（Figma/即时设计/Axure），或至少每屏一张静态截图。"
     "注意：只给「原型链接.md」这类空壳文档无效——文件里必须有真实可打开的 http(s) 链接，否则等同于没有。"),
    ("api", "自有云 API/接口文档", (40, 60), 0.9,
     "无接口文档 → 无法设计接口级参数校验、状态码、幂等、并发与鉴权类用例，前后端联调期问题只能靠手点发现",
     "导出 Swagger/OpenAPI（json 或 yapi 导出），或让后端提供接口清单（路径 / 方法 / 入参及校验规则 / 错误码）。"
     "有 OpenAPI 文件时本脚本可直接识别，否则先补一份最小清单。"),
    ("defect", "历史缺陷/TAPD 导出", (20, 30), 1.0,
     "无历史缺陷 → 回归题库为空，已知的易复发场景与历史事故点识别不到，同类缺陷容易二次上线",
     "从 TAPD/禅道导出近一年缺陷（Excel，含标题/模块/严重程度/状态），"
     "筛选「已修复」且严重及以上者，逐条转成回归用例。成本低，可直接复用现成导出。"),
]

DICT_NAME = re.compile(r"数据字典|字段|数据项|dictionary|schema", re.I)
API_NAME = re.compile(r"api|接口|swagger|openapi", re.I)
DEFECT_NAME = re.compile(r"缺陷|bug|tapd|defect|jira|禅道", re.I)
PROTO_NAME = re.compile(r"原型|prototype|设计稿", re.I)
PROTO_UI_TOKEN = re.compile(r"(?i)(^|[^a-z0-9])ui([^a-z0-9]|$)")


# ---------------------------------------------------------------- 扫描
def scan(root):
    """递归收集文件，跳过隐藏目录、缓存与依赖目录。"""
    skip = {"__pycache__", "node_modules", ".git", ".idea", ".vscode", "venv", ".venv"}
    files = []
    for cur, dirs, names in os.walk(root):
        dirs[:] = [d for d in dirs if not d.startswith(".") and d not in skip]
        for n in names:
            if n.startswith(".") or n.startswith("~$"):
                continue
            files.append(os.path.join(cur, n))
    return files


def read_text(path, limit=200000):
    try:
        with open(path, encoding="utf-8", errors="ignore") as f:
            return f.read(limit)
    except OSError:
        return ""


def json_has_key(path, keys):
    txt = read_text(path)
    return any(f'"{k}"' in txt for k in keys)


def xlsx_header_has(path, words):
    """读表头行（首个 sheet 第一行），判断是否含关键词。无 openpyxl 时静默跳过。"""
    try:
        from openpyxl import load_workbook
    except ImportError:
        return False
    try:
        wb = load_workbook(path, read_only=True, data_only=True)
        ws = wb[wb.sheetnames[0]]
        head = ""
        for row in ws.iter_rows(values_only=True, max_row=1):
            head = " ".join(str(v) for v in row if v is not None)
            break
        wb.close()
    except Exception:
        return False
    return any(w.lower() in head.lower() for w in words)


def csv_header_has(path, words):
    for enc in ("utf-8-sig", "gbk", "utf-8"):
        try:
            with open(path, encoding=enc) as f:
                head = f.readline()
            break
        except (UnicodeDecodeError, OSError):
            continue
    else:
        return False
    return any(w.lower() in head.lower() for w in words)


def is_placeholder_doc(path):
    """空链接占位文档：无 http(s) 链接，且正文去掉标题/分隔符后只剩占位词。

    真实踩过的坑：5 份「原型链接.md」全是空占位，若按文件名判定会误报"原型已具备"。
    """
    txt = read_text(path)
    if re.search(r"https?://\S+", txt):
        return False
    body = []
    for line in txt.splitlines():
        s = line.strip().strip("#*->|`~ \t:：")
        if not s or PLACEHOLDER_RE.match(s):
            continue
        body.append(s)
    return len("".join(body)) < 20


# ---------------------------------------------------------------- 判定
def detect(files):
    """返回 {key: {"ready": bool, "evidence": [文件名...], "note": str}}"""
    res = {k: {"ready": False, "evidence": [], "note": ""} for k, *_ in CATS}

    for p in files:
        name = os.path.basename(p)
        ext = os.path.splitext(name)[1].lower()

        # dictionary
        if not res["dictionary"]["ready"]:
            if DICT_NAME.search(name) and ext in (DOC_EXTS | SHEET_EXTS | JSON_EXTS):
                res["dictionary"]["evidence"].append(name)
            elif ext in JSON_EXTS and json_has_key(p, ("fields", "dictionary")):
                res["dictionary"]["evidence"].append(name)

        # prototype：图片直接算；文档需含真实链接；UI 名需词边界（避免 build/guide 误命中）
        if not res["prototype"]["ready"]:
            if ext in IMG_EXTS:
                res["prototype"]["evidence"].append(name)
            elif PROTO_NAME.search(name) or PROTO_UI_TOKEN.search(name):
                if ext in (TEXT_EXTS | SHEET_EXTS):
                    if is_placeholder_doc(p):
                        res["prototype"]["note"] = f"「{name}」为空链接占位（无 http/https），按缺失计"
                    else:
                        res["prototype"]["evidence"].append(name)
                else:
                    res["prototype"]["evidence"].append(name)

        # api
        if not res["api"]["ready"]:
            if API_NAME.search(name) and ext in (DOC_EXTS | SHEET_EXTS | JSON_EXTS):
                res["api"]["evidence"].append(name)
            elif ext in JSON_EXTS and json_has_key(p, ("paths", "openapi")):
                res["api"]["evidence"].append(name)

        # defect
        if not res["defect"]["ready"]:
            if DEFECT_NAME.search(name) and ext in (DOC_EXTS | SHEET_EXTS | JSON_EXTS):
                res["defect"]["evidence"].append(name)
            elif ext in (".xlsx", ".xlsm", ".xls") and xlsx_header_has(p, ("缺陷", "bug", "defect")):
                res["defect"]["evidence"].append(name)
            elif ext in (".csv", ".tsv") and csv_header_has(p, ("缺陷", "bug", "defect")):
                res["defect"]["evidence"].append(name)

    for k, v in res.items():
        v["ready"] = bool(v["evidence"])
    return res


# ---------------------------------------------------------------- 报告
def build(root, required):
    files = scan(root)
    found = detect(files)
    items = []
    for key, cname, gains, roi, impact, action in CATS:
        d = found[key]
        items.append({
            "key": key, "name": cname, "required": key in required,
            "ready": d["ready"], "evidence": d["evidence"], "note": d["note"],
            "gain": list(gains), "roi": roi, "impact": impact, "action": action,
        })
    req_items = [i for i in items if i["required"]]
    ready = sum(1 for i in req_items if i["ready"])
    total = len(req_items)
    missing = [i for i in req_items if not i["ready"]]
    lo = BASE_CASES + sum(i["gain"][0] for i in missing)
    hi = BASE_CASES + sum(i["gain"][1] for i in missing)
    return {
        "root": os.path.abspath(root),
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "ready": ready, "total": total,
        "items": items, "missing": [i["key"] for i in missing],
        "ready_list": [i["key"] for i in req_items if i["ready"]],
        "file_count": len(files),
        "base": {"cases": BASE_CASES, "rules": BASE_RULES},
        "reachable": [lo, hi],
    }


def statement(r):
    if r["ready"] == r["total"]:
        return (f"本次输入完备度 {r['total']}/{r['total']}，四类输入齐备，"
                f"用例池理论规模可达 {r['reachable'][0]}~{r['reachable'][1]} 条（基准 {r['base']['rules']} 需求/"
                f"{r['base']['cases']} 条），未见输入侧导致的系统性缺口。")
    miss_cn = "、".join(i["name"] for i in r["items"] if i["key"] in r["missing"])
    impacts = "；".join(i["impact"].split("→")[0].strip() for i in r["items"] if i["key"] in r["missing"])
    return (f"本次输入完备度 {r['ready']}/{r['total']}（缺{miss_cn}），"
            f"用例池理论可达 {r['reachable'][0]}~{r['reachable'][1]} 条，"
            f"未覆盖部分主要为{impacts}。")


def render_markdown(r):
    L = []
    a = L.append
    a("# 输入完备度报告")
    a("")
    a(f"- 生成时间：{r['generated_at']}")
    a(f"- 需求目录：`{r['root']}`（扫描 {r['file_count']} 个文件）")
    a("- 判定口径：仅依据文件存在性与内容特征（文件名关键词 / 图片后缀 / JSON 键 / 表头），不联网、不解析正文语义")
    a("")
    a("## 一、总览")
    a("")
    a("| 输入类 | 状态 | 证据 | 缺失影响 | 可回收上限 |")
    a("|---|---|---|---|---|")
    for i in r["items"]:
        if not i["required"]:
            continue
        status = "✅ 已具备" if i["ready"] else "❌ 缺失"
        ev = "、".join(i["evidence"][:3]) if i["evidence"] else "未找到"
        if i["note"]:
            ev += f"（{i['note']}）"
        if i["ready"]:
            gain = "—（无损失）"
            impact = "—"
        else:
            gain = f"−{i['gain'][0]}~{i['gain'][1]} 条"
            impact = i["impact"]
        a(f"| {i['name']} | {status} | {ev} | {impact} | {gain} |")
    a("")
    a("> 可回收上限基准来自 47 需求 / 196 条库的实测回放，可按项目规模等比缩放"
      "（如需求数翻倍则同比例放大）。该数值是「补齐后理论上能多产出的用例量」，不等于必须补齐。")
    a("")
    a("## 二、结论")
    a("")
    a(f"**输入完备度 {r['ready']}/{r['total']}**")
    a("")
    if r["ready"] == r["total"]:
        a(f"四类输入齐备。用例池理论规模 {r['reachable'][0]}~{r['reachable'][1]} 条"
          f"（基准 {r['base']['rules']} 需求 / {r['base']['cases']} 条）。")
    else:
        a(f"缺 {len(r['missing'])} 类输入，理论可回收 {r['reachable'][0] - r['base']['cases']}"
          f"~{r['reachable'][1] - r['base']['cases']} 条；"
          f"用例池理论可达 {r['reachable'][0]}~{r['reachable'][1]} 条。")
    a("")
    a("## 三、建议动作")
    a("")
    miss = sorted([i for i in r["items"] if i["required"] and not i["ready"]],
                  key=lambda x: -x["roi"])
    if not miss:
        a("无需补充动作：四类输入均已具备，可直接进入设计阶段。")
        a("")
    else:
        for n, i in enumerate(miss, 1):
            tier = "高" if i["roi"] >= 1.2 else ("中" if i["roi"] >= 1.0 else "低")
            a(f"{n}. **补{i['name']}**（投入产出比：{tier}，预计回收 {i['gain'][0]}~{i['gain'][1]} 条）")
            a(f"   - {i['action']}")
            a(f"   - 不补的代价：{i['impact']}")
            a("")
        a("排序说明：按「单位投入的用例回收量」降序，数据字典与原型投入最小、损失最大，应优先补齐；"
          "接口文档次之；历史缺陷可用现成导出，但单类回收量最小。")
        a("")
    a("## 四、声明")
    a("")
    a("可直接粘贴进《测试分析报告》：")
    a("")
    a(f"> {statement(r)}")
    a("")
    return "\n".join(L)


def render_json(r):
    return json.dumps({
        "generated_at": r["generated_at"],
        "prd": r["root"],
        "ready": r["ready"],
        "total": r["total"],
        "complete": r["ready"] == r["total"],
        "ready_list": r["ready_list"],
        "missing": r["missing"],
        "reachable": r["reachable"],
        "base": r["base"],
        "statement": statement(r),
        "items": [{
            "key": i["key"], "name": i["name"], "required": i["required"],
            "ready": i["ready"], "evidence": i["evidence"], "note": i["note"],
            "gain": i["gain"], "roi": i["roi"],
        } for i in r["items"]],
    }, ensure_ascii=False, indent=2)


def main():
    ap = argparse.ArgumentParser(
        description="输入完备度自检：四类输入（数据字典/原型/API/缺陷）到位情况 + 缺失损失量化")
    ap.add_argument("--prd", required=True, help="需求/项目目录")
    ap.add_argument("--require", default="dictionary,prototype,api,defect",
                    help="要求必备的输入类，逗号分隔（默认四类全要）")
    ap.add_argument("-o", "--out", help="报告输出路径（默认打印到 stdout）")
    ap.add_argument("--format", choices=["markdown", "json"], default="markdown")
    ap.add_argument("--strict", action="store_true",
                    help="严格模式：完备度不足返回 1（默认恒 0，仅作观测）")
    args = ap.parse_args()

    if not os.path.isdir(args.prd):
        print(f"[错误] 需求目录不存在或不是目录: {args.prd}", file=sys.stderr)
        return 2

    valid = [c[0] for c in CATS]
    required = [x.strip() for x in args.require.split(",") if x.strip()]
    bad = [x for x in required if x not in valid]
    if bad:
        print(f"[错误] 未知输入类: {bad}，可选: {valid}", file=sys.stderr)
        return 2
    if not required:
        print(f"[错误] --require 不能为空，可选: {valid}", file=sys.stderr)
        return 2

    r = build(args.prd, required)
    text = render_markdown(r) if args.format == "markdown" else render_json(r)

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text + "\n")
        print(f"[✓] 报告已写入 {args.out}")
        print(f"    输入完备度 {r['ready']}/{r['total']}，"
              f"缺失：{'、'.join(r['missing']) or '无'}"
              f"（理论可达 {r['reachable'][0]}~{r['reachable'][1]} 条）")
    else:
        print(text)

    if args.strict and r["ready"] < r["total"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
