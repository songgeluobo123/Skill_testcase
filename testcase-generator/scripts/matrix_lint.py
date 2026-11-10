#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
matrix_lint.py — 等价类 / 边界值矩阵（Step 3.5 中间产物）的 lint 闸门

为什么需要它：密度闸门（prescreen 第 11 项）只会逼出"同一条需求复制 6 遍"，
除非有一条矩阵规定"这 6 条各测哪个类/哪个边界点"。矩阵是密度闸门唯一的燃料。

矩阵格式（**一行一项**，Markdown 表格）：
  | # | 字段 | 类型 | 取值域 | 类/边界点 | 类别 | 预期要点 | 覆盖 R-ID | 用例 ID |

  · 一行 = 一个等价类 或 一个边界点，不是"一行一个字段"。
    字段级一行无法判"每个类都被用例消费"，会退化成"有 ID 就算覆盖"的假覆盖
    ——这正是本技能在覆盖率评审里已经踩过的坑（见 references/coverage_audit.md）。
  · 类别只认三值：有效类 / 无效类 / 边界
  · 预期要点：这一项该断言什么（含具体值/阈值/逐字文案）
  · 覆盖 R-ID：该行服务哪条需求（可多个，分号分隔）
  · 用例 ID：哪些用例消费了这一行（可多个，分号分隔）；为空即"未消费等价类"

检查项：
  L1 表头完整性（必需列缺失 → 退出码 2）
  L2 每个数值/枚举类字段的边界点数 >= --min-boundary（默认 3）→ 阻断
  L3 每行必须有「用例 ID」，否则报「未消费等价类」→ 只在 --stage full 阻断
     （--stage design 是 Step 3.5 建矩阵时的默认档：此刻用例还没生成，用例 ID 必然为空，
      若在此档就阻断会造成"用例没写→矩阵过不了→不许写用例"的死锁）
  L4 「覆盖 R-ID」必须落在 --requirement-rules 清单内 → 阻断（查编造）
  L5 标 [假设] 的行占比 > --assume-max（默认 30%）→ 阻断；否则告警并单列
  L6 字段类型不在白名单 → 告警（提示口径不统一）
  L7 同一字段内「类/边界点」重复 → 告警
  L8 字段缺「无效类」行 → 告警（越界/非法取值是否漏测）
  L9 --cases：矩阵引用的用例 ID 在用例库中不存在 → 阻断（回指闭环）

退出码：0 通过（可能带告警）｜1 不达标｜2 输入/参数错误
"""
import argparse
import io
import json
import re
import sys
from collections import OrderedDict

# ---------- 表头别名 ----------
HEADER_ALIASES = {
    "field": ["字段", "字段名", "数据项", "参数", "field"],
    "type": ["类型", "字段类型", "数据类型", "type"],
    "domain": ["取值域", "取值范围", "有效范围", "domain"],
    "point": ["类/边界点", "等价类/边界点", "类或边界点", "取值", "类", "边界点", "point"],
    "kind": ["类别", "类型类别", "类归属", "kind"],
    "expect": ["预期要点", "断言要点", "预期", "验证要点", "expect"],
    "rule": ["覆盖 R-ID", "覆盖R-ID", "需求规则", "覆盖规则", "R-ID", "rule"],
    "case": ["用例 ID", "用例ID", "关联用例", "用例", "case"],
}
REQUIRED = ["field", "point", "kind", "case"]

# 类别三值（容忍空格与"边界值/边界点"写法）
KIND_ALIASES = {
    "有效类": "有效类", "有效等价类": "有效类", "合法类": "有效类",
    "无效类": "无效类", "无效等价类": "无效类", "非法类": "无效类",
    "边界": "边界", "边界值": "边界", "边界点": "边界", "临界": "边界",
}

# 必须给足边界点的类型（否则每次生成都会漏掉越界/临界场景）
BOUNDARY_REQUIRED = {"数值", "整数", "小数", "浮点", "金额", "百分比", "时长",
                     "版本号", "枚举", "档位", "电量"}
TYPE_WHITELIST = BOUNDARY_REQUIRED | {"布尔", "字符串", "文本", "日期", "时间",
                                      "时间戳", "颜色", "路径", "URL", "列表", "对象"}

ASSUME_RE = re.compile(r"[\[［]\s*假设\s*[\]］]")
SPLIT_RULE = re.compile(r"[;；]")
SPLIT_ID = re.compile(r"[;；,，、\s]+")
SEP_ROW = re.compile(r"^[:\-\s|]+$")


def norm_header(s):
    s = re.sub(r"[`*_\s]", "", s or "")
    return s.strip()


def base_type(t):
    """'数值(0–100%)' → '数值'。"""
    return re.split(r"[(（\[［]", str(t or "").strip())[0].strip()


def read_tables(path):
    """解析 Markdown 里所有表格（跳过 ``` 代码块），返回 [(headers, rows), ...]。"""
    tables, cur, headers = [], [], None
    in_code = False
    with io.open(path, encoding="utf-8") as f:
        for raw in f:
            line = raw.rstrip("\n")
            if line.strip().startswith("```"):
                in_code = not in_code
                if cur:
                    tables.append((headers, cur))
                    cur, headers = [], None
                continue
            if in_code:
                continue
            if not line.strip().startswith("|"):
                if cur:
                    tables.append((headers, cur))
                    cur, headers = [], None
                continue
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if SEP_ROW.match(line.replace("|", "")):
                continue
            if headers is None:
                headers = cells
                continue
            if all(not c for c in cells):
                continue
            cur.append(cells)
    if cur:
        tables.append((headers, cur))
    return tables


def map_headers(cells):
    """把表头映射成标准名；未识别的列忽略。"""
    m = {}
    for i, c in enumerate(cells):
        n = norm_header(c)
        for key, alist in HEADER_ALIASES.items():
            if key in m:
                continue
            if n in [norm_header(a) for a in alist]:
                m[key] = i
                break
    return m


def load_matrix(path):
    tables = read_tables(path)
    collected, mapping, used = [], None, 0
    for headers, rows in tables:
        m = map_headers(headers)
        if not all(k in m for k in ("field", "point", "kind")):
            continue
        if mapping is None:
            mapping = m
        # 只合并与首个矩阵表同构的表（分模块多张表时仍能汇总）
        if all(k in m for k in mapping):
            collected.extend(rows)
            used += 1
    return mapping, collected, used


def cell(row, m, key):
    i = m.get(key)
    if i is None or i >= len(row):
        return ""
    return str(row[i]).strip()


def lint(rows, m, args, rule_ids=None, case_ids=None):
    issues = []          # (level, code, msg)  level: block / warn
    per_field = OrderedDict()

    total = len(rows)
    assume_rows = []
    field_rows = {}          # 字段 → 数据行数（含 [假设] 行），供 --assume-stats 用
    need_len = max(m.values()) + 1

    for idx, row in enumerate(rows, 1):
        # L1b 列数校验：少一列就会整体错位，静默误判比报错更危险
        if len(row) < need_len:
            issues.append(("block", "L1b",
                           f"第 {idx} 行只有 {len(row)} 列，表头需要 {need_len} 列"
                           f"（列错位会让类别/预期/用例 ID 全部读错）"))
            continue
        f = cell(row, m, "field")
        field_rows[f or "(空字段)"] = field_rows.get(f or "(空字段)", 0) + 1
        tp = base_type(cell(row, m, "type"))
        pt = cell(row, m, "point")
        kd_raw = cell(row, m, "kind")
        kd = KIND_ALIASES.get(norm_header(kd_raw))
        rid_raw = cell(row, m, "rule")
        cid_raw = cell(row, m, "case")
        exp = cell(row, m, "expect")

        if ASSUME_RE.search(" ".join(row)):
            assume_rows.append((idx, f, pt))
            # [假设] 行不进有效统计：既不算边界点，也不算已消费
            continue

        if not f or not pt:
            issues.append(("block", "L0", f"第 {idx} 行字段或「类/边界点」为空"))
            continue
        if kd is None:
            issues.append(("warn", "L6b", f"第 {idx} 行 `{f} · {pt}` 的类别 `{kd_raw}` 非法"
                                          f"（只认 有效类 / 无效类 / 边界）"))
            continue

        d = per_field.setdefault(f, {"type": tp, "有效类": 0, "无效类": 0, "边界": 0,
                                     "points": [], "no_case": [], "no_expect": []})
        d[kd] += 1
        d["points"].append(pt)

        # L3 未消费等价类：design 档只记待回填，full 档才阻断
        if not cid_raw or cid_raw in ("-", "—", "/", "待补", "TBD"):
            d["no_case"].append(pt)
            if args.stage == "full":
                issues.append(("block", "L3",
                               f"`{f} · {pt}`（{kd}）无用例回指——属未消费等价类"))
            else:
                issues.append(("warn", "L3d",
                               f"`{f} · {pt}`（{kd}）待回填用例 ID（Step 3.5 建矩阵阶段允许为空）"))
        if not exp or exp in ("-", "—", "/"):
            d["no_expect"].append(pt)
            issues.append(("warn", "L3b", f"`{f} · {pt}`（{kd}）缺「预期要点」，无法判断断言什么"))

        # L4 编造需求
        if rule_ids is not None and rid_raw:
            for rid in [x.strip() for x in SPLIT_RULE.split(rid_raw) if x.strip()]:
                if re.fullmatch(r"R-\d+", rid) and rid not in rule_ids:
                    issues.append(("block", "L4", f"`{f} · {pt}` 覆盖的 `{rid}` 不在需求清单内"))

        # L9 用例 ID 必须真实存在
        if case_ids is not None and cid_raw:
            miss = [c for c in SPLIT_ID.split(cid_raw)
                    if c and re.match(r"TC-", c) and c not in case_ids]
            if miss:
                issues.append(("block", "L9", f"`{f} · {pt}` 引用了不存在的用例: {miss[:5]}"))

    # L2 边界点数量
    for f, d in per_field.items():
        tp = d["type"]
        need = tp in BOUNDARY_REQUIRED
        if not need:
            if tp and tp not in TYPE_WHITELIST:
                issues.append(("warn", "L6", f"字段 `{f}` 类型 `{tp}` 不在类型白名单内，口径不统一"))
            continue
        if d["边界"] < args.min_boundary:
            issues.append(("block", "L2",
                           f"字段 `{f}`（{tp}）边界点仅 {d['边界']} 个 < {args.min_boundary}"
                           f"——越界/临界场景会漏"))
        if tp and tp not in TYPE_WHITELIST:
            issues.append(("warn", "L6", f"字段 `{f}` 类型 `{tp}` 不在类型白名单内，口径不统一"))
        if d["无效类"] == 0:
            issues.append(("warn", "L8", f"字段 `{f}`（{tp}）无「无效类」行——非法取值是否漏测？"))

    # L7 同字段重复点
    for f, d in per_field.items():
        seen, dup = set(), set()
        for p in d["points"]:
            if p in seen:
                dup.add(p)
            seen.add(p)
        if dup:
            issues.append(("warn", "L7", f"字段 `{f}` 的类/边界点重复: {sorted(dup)}"))

    # L10 反向校验（full 阶段 + 提供 --cases）：用例未被任何矩阵行引用 = 无设计依据
    if args.stage == "full" and case_ids is not None:
        referenced = set()
        for row in rows:
            for c in SPLIT_ID.split(cell(row, m, "case")):
                if c:
                    referenced.add(c)
        orphans = sorted(c for c in case_ids if c and c.startswith("TC-") and c not in referenced)
        if orphans:
            msg = (f"{len(orphans)} 条用例未被任何矩阵行引用（无设计依据，"
                   f"要么补矩阵行、要么删用例）: {orphans[:10]}"
                   + ("…" if len(orphans) > 10 else ""))
            if args.orphan_case_mode == "block":
                issues.append(("block", "L10", msg))
            else:
                issues.append(("warn", "L10", msg))

    # L5 假设行占比
    assume_ratio = (len(assume_rows) / total) if total else 0.0
    if assume_ratio > args.assume_max:
        issues.append(("block", "L5",
                       f"标 [假设] 的行占比 {assume_ratio:.0%} > 上限 {args.assume_max:.0%}"
                       f"——在为无依据的数据编边界"))
    elif assume_rows:
        issues.append(("warn", "L5",
                       f"标 [假设] 的行 {len(assume_rows)} 条（占比 {assume_ratio:.0%}），"
                       f"不计入有效覆盖，需回溯数据字典/需求确认"))

    return per_field, issues, assume_rows, assume_ratio, field_rows


def render(per_field, issues, assume_rows, assume_ratio, total, args, tables_used,
           field_rows=None):
    L = []
    blocks = [i for i in issues if i[0] == "block"]
    warns = [i for i in issues if i[0] == "warn"]
    n_boundary = sum(d["边界"] for d in per_field.values())

    L.append("# 等价类 / 边界值矩阵 Lint 报告\n")
    L.append("## 一、总览\n")
    L.append("| 指标 | 值 |\n|---|---|")
    L.append(f"| 阶段 | **{args.stage}**"
             + ("（Step 3.5 建矩阵，用例 ID 允许为空）" if args.stage == "design"
                else "（用例生成后回填复核）") + " |")
    L.append(f"| 矩阵表数量 | {tables_used} |")
    L.append(f"| 数据行 | {total} |")
    L.append(f"| 字段数 | {len(per_field)} |")
    L.append(f"| 边界点总数 | {n_boundary} |")
    label = "未消费等价类" if args.stage == "full" else "待回填用例 ID"
    L.append(f"| {label} | {sum(len(d['no_case']) for d in per_field.values())} |")
    L.append(f"| [假设] 行占比 | {assume_ratio:.0%}（上限 {args.assume_max:.0%}） |")
    L.append(f"| 阻断项 / 告警项 | {len(blocks)} / {len(warns)} |\n")

    L.append("## 二、字段级边界点覆盖\n")
    L.append(f"> 门槛：数值 / 枚举类字段边界点 ≥ {args.min_boundary} 个\n")
    L.append("| 字段 | 类型 | 有效类 | 无效类 | 边界点 | 判定 |\n|---|---|---|---|---|---|")
    for f, d in per_field.items():
        need = d["type"] in BOUNDARY_REQUIRED
        if not need:
            v = "✅ 该类型不强制边界"
        elif d["边界"] < args.min_boundary:
            v = f"❌ 缺 {args.min_boundary - d['边界']} 个"
        elif d["no_case"]:
            v = f"❌ {len(d['no_case'])} 项未消费"
        else:
            v = "✅"
        L.append(f"| {f} | {d['type'] or '—'} | {d['有效类']} | {d['无效类']} | {d['边界']} | {v} |")
    L.append("")

    if any(d["no_case"] for d in per_field.values()):
        if args.stage == "full":
            L.append("## 三、未消费等价类（无用例回指，不计入覆盖）\n")
        else:
            L.append("## 三、待回填用例 ID（建矩阵阶段允许为空，Step 5 后跑 `--stage full` 复核）\n")
        for f, d in per_field.items():
            if d["no_case"]:
                L.append(f"- **{f}**：{'、'.join(d['no_case'])}")
        L.append("")

    if assume_rows:
        L.append("## 四、[假设] 行（无来源，不计入有效覆盖）\n")
        L.append("| 行 | 字段 | 类/边界点 |\n|---|---|---|")
        for i, f, p in assume_rows[:20]:
            L.append(f"| {i} | {f} | {p} |")
        if len(assume_rows) > 20:
            L.append(f"| … | 其余 {len(assume_rows) - 20} 行 | |")
        L.append("")

    if warns:
        L.append("## 五、告警\n")
        for _, code, msg in warns:
            L.append(f"- `{code}` {msg}")
        L.append("")

    L.append("## 六、结论\n")
    if blocks:
        L.append(f"**不通过**：{len(blocks)} 项阻断需修正后重跑。")
        for _, code, msg in blocks[:20]:
            L.append(f"- `{code}` {msg}")
        if len(blocks) > 20:
            L.append(f"- … 其余 {len(blocks) - 20} 项")
    elif args.stage == "design":
        L.append("**通过（design 阶段）**：矩阵已可作用例来源清单；"
                 "用例生成后须回填「用例 ID」并跑 `--stage full --cases test_cases.json` 复核。")
    else:
        L.append("**通过（full 阶段）**：矩阵与用例库已双向对齐。")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description="等价类/边界值矩阵 lint（Step 3.5 闸门）")
    ap.add_argument("matrix", help="矩阵 Markdown 文件")
    ap.add_argument("--stage", choices=["design", "full"], default="design",
                    help="design=建矩阵阶段（用例 ID 允许空，L3 降级告警）；"
                         "full=用例生成后回填复核（L3 阻断 + 反向查未被引用的用例）")
    ap.add_argument("--orphan-case-mode", choices=["warn", "block"], default="warn",
                    help="full 阶段：用例库中未被任何矩阵行引用的用例如何处理（默认 warn）")
    ap.add_argument("--min-boundary", type=int, default=3,
                    help="数值/枚举字段的边界点下限（默认 3）")
    ap.add_argument("--assume-max", type=float, default=0.30,
                    help="[假设] 行占比上限（默认 0.30，**经验值尚未实证校准**；"
                         "用 --assume-stats 看分布，攒够样本后取 P90 回改）")
    ap.add_argument("--assume-stats", action="store_true",
                    help="打印每个字段的 [假设] 行占比，用于校准 --assume-max")
    ap.add_argument("--requirement-rules", help="需求规则清单 JSON，用于校验 R-ID 非编造")
    ap.add_argument("--cases", help="用例 JSON，用于校验矩阵引用的用例 ID 真实存在")
    ap.add_argument("-o", "--output", help="报告输出路径（默认 stdout）")
    ap.add_argument("--format", choices=["markdown", "json"], default="markdown")
    ap.add_argument("--quiet", action="store_true", help="只输出结论行")
    args = ap.parse_args()

    try:
        m, rows, used = load_matrix(args.matrix)
    except Exception as e:
        print(f"[错误] 读取矩阵失败: {e}", file=sys.stderr)
        return 2
    if not rows:
        print("[错误] 未在文件中找到矩阵表格（需含 字段 / 类-边界点 / 类别 / 用例 ID 列）",
              file=sys.stderr)
        return 2
    missing = [k for k in REQUIRED if k not in m]
    if missing:
        print(f"[错误] 表头缺必需列: {missing}", file=sys.stderr)
        return 2

    rule_ids = None
    if args.requirement_rules:
        try:
            raw = json.load(io.open(args.requirement_rules, encoding="utf-8"))
        except Exception as e:
            print(f"[错误] 读取需求清单失败: {e}", file=sys.stderr)
            return 2
        if isinstance(raw, dict) and "rules" in raw:
            raw = raw["rules"]

        def rid_of(x):
            if isinstance(x, dict):
                return str(x.get("id", "")).strip()
            mo = re.search(r"R-\d+", str(x))
            return mo.group(0) if mo else ""

        rule_ids = {rid_of(x) for x in raw if rid_of(x)}

    case_ids = None
    if args.cases:
        try:
            raw = json.load(io.open(args.cases, encoding="utf-8"))
        except Exception as e:
            print(f"[错误] 读取用例库失败: {e}", file=sys.stderr)
            return 2
        if isinstance(raw, dict) and "cases" in raw:
            raw = raw["cases"]
        case_ids = {str(c.get("id", "")).strip() for c in raw if isinstance(c, dict)}

    per_field, issues, assume_rows, ratio, field_rows = lint(rows, m, args, rule_ids, case_ids)
    blocks = [i for i in issues if i[0] == "block"]

    if args.format == "json":
        payload = {
            "matrix": args.matrix,
            "tables": used,
            "rows": len(rows),
            "fields": [{"field": f, **{k: v for k, v in d.items() if k != "points"}}
                       for f, d in per_field.items()],
            "assume_rows": len(assume_rows),
            "assume_ratio": round(ratio, 4),
            "block": [{"code": c, "msg": msg} for _, c, msg in blocks],
            "warn": [{"code": c, "msg": msg} for lv, c, msg in issues if lv == "warn"],
            "pass": not blocks,
        }
        out = json.dumps(payload, ensure_ascii=False, indent=2)
    else:
        out = render(per_field, issues, assume_rows, ratio, len(rows), args, used,
                     field_rows=field_rows)

    if args.assume_stats and not args.quiet:
        # 假设占比分布：默认 --assume-max 0.30 **至今没有实证校准**（手上只有 1 份真实矩阵，
        # 且因取自已确认需求，假设行占比为 0%，样本量根本不够）。所以这里不猜默认值，
        # 改成把观测值打出来，让项目自己攒数据：攒够 ≥5 份真实矩阵后取 P90 再回改默认值。
        by_field = {}
        for _, f, _ in assume_rows:
            by_field[f or "(空字段)"] = by_field.get(f or "(空字段)", 0) + 1
        print("\n=== [假设] 行分布（用于校准 --assume-max，当前默认 0.30 属经验值）===")
        print(f"{'字段':24s} {'假设行':>6s} {'数据行':>6s} {'占比':>7s}")
        for f in sorted(field_rows):
            n_all = field_rows[f]
            n_as = by_field.get(f, 0)
            print(f"{f:24s} {n_as:6d} {n_all:6d} {n_as / n_all:7.0%}")
        print(f"{'合计':24s} {len(assume_rows):6d} {len(rows):6d} {ratio:7.0%}")
        print("> 校准方法：收集 ≥5 份真实项目矩阵，统计各项目合计占比，取 P90 作为新的 "
              "--assume-max；在此之前保持 0.30 并在报告里标注『经验值、未校准』。")

    if args.output:
        io.open(args.output, "w", encoding="utf-8").write(out)
        if not args.quiet:
            print(f"[已写出] {args.output}")
    elif not args.quiet:
        print(out)
    if args.quiet:
        status = "PASS" if not blocks else "FAIL"
        print(f"{status} 字段 {len(per_field)} / 行 {len(rows)} / 阻断 {len(blocks)}")
    return 0 if not blocks else 1


if __name__ == "__main__":
    # 退出码：0=通过 / 1=不达标 / 2=输入·参数错误 / 3=脚本自身崩溃。
    # 3 必须与 1 分开：早期未捕获异常统一表现为 exit 1，会被误读成
    # "数据不达标"，让人对着不存在的质量问题返工。
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception:
        import traceback
        print("\n[内部错误] matrix_lint.py 自身崩溃（exit 3），不是数据不达标。", file=sys.stderr)
        print("请把下面的堆栈连同输入样例一起报给技能维护者：", file=sys.stderr)
        traceback.print_exc()
        sys.exit(3)
