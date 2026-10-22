#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sort_test_cases.py — 测试用例执行顺序排序（v2.1）

四层排序模型
------------
L0 分类 partition：公共 / 横屏专项 / 竖屏专项（同一形态集中执行，减少设备切换）
L1 阶段 stage     ：账号准备 → 设备接入 → 首次引导 → 核心训练 → 智能助手 → 设置维护
L2 模块 module    ：模块在业务链路上的先后（支持层级前缀匹配：设备端-启动 归入 设备端）
L3 测试点 group   ：模块内按依赖链分组（进入 → 主流程 → 分支 → 异常 → 边界 → 安全 → 兼容 → 性能）
   组内次序 type  ：可选，按用例类型排序（功能/UI → 接口 → 异常 → 边界 → 安全 → 兼容 → 性能）

输出保证：用例内容零改动（逐单元格、逐样式、超链接、批注），仅改变行顺序。

用法
----
    python sort_test_cases.py cases.xlsx
    python sort_test_cases.py cases.xlsx --flow-config flow.json --report report.md
    python sort_test_cases.py cases.xlsx --flow-config flow.json --all-sheets      # 处理全部 sheet
    python sort_test_cases.py cases.xlsx --flow-config flow.json --dump-unclassified out.txt
    python sort_test_cases.py cases.xlsx --flow-config flow.json --inplace         # 覆盖原文件（.bak 备份）
    python sort_test_cases.py cases.xlsx --flow-config flow.json --dry-run
"""
import argparse
import json
import re
import shutil
import sys
from copy import copy
from datetime import datetime
from pathlib import Path

MODULE_KEYWORDS = ["功能模块", "所属模块", "模块", "测试模块", "分类", "module", "category"]
TOP_KEYWORDS = ["顶级功能模块", "一级模块", "所属端", "平台", "端"]
FUNC_KEYWORDS = ["功能点", "功能", "测试点", "测试项", "子模块", "feature", "function", "submodule"]
ORDER_KEYWORDS = ["执行顺序", "序号", "排序", "order", "sequence"]
TITLE_KEYWORDS = ["用例标题", "测试用例标题", "标题", "title", "name", "casename"]
TYPE_KEYWORDS = ["测试类型", "用例类型", "类型", "type", "kind"]
PARTITION_KEYWORDS = ["设备型号", "用例分类", "分类", "专项", "partition", "category"]
PRIORITY_KEYWORDS = ["测试优先级", "优先级", "priority", "level"]

DEFAULT_TYPE_ORDER = [
    "业务测试", "功能测试", "系统测试", "集成测试", "联动测试",
    "UI测试",
    "接口测试", "数据一致性测试", "埋点测试", "日志测试",
    "异常测试", "边界测试", "网络测试",
    "并发测试", "队列测试", "稳定性测试",
    "安全测试", "风控测试",
    "兼容性测试", "国际化测试",
    "性能测试", "用户体验测试",
]

DEFAULT_FLOW = {
    "module_sequence": [
        "登录", "引导", "课程库", "训练", "训练记录",
        "首页", "AI教练", "个人中心", "自由跑", "联调", "遥控",
    ],
    "module_flow": {
        "登录": ["二维码", "token", "密码", "登出", "账号"],
        "引导": ["安全确认", "能力阶段", "C00", "校准", "返回"],
        "课程库": ["加载", "课程内容", "训练"],
        "训练": ["进入训练", "快速确认", "训练中状态", "心率", "状态", "语音", "暂停", "终止", "结束", "异常阻断", "自由跑", "恢复"],
        "训练记录": ["记录数据", "时间", "卡路里", "心率", "阶段", "详情", "类型"],
        "首页": ["日历", "训练计划", "完成状态", "离线", "副标签"],
        "AI教练": ["唤醒", "回复", "校验", "跳转", "遮挡", "状态"],
        "个人中心": ["健康信息", "键盘", "Wi-Fi", "网络", "符号"],
        "自由跑": ["安全夹", "启动"],
        "联调": ["遥控"],
        "遥控": ["首页键"],
    },
}

SEP = ("/", "-", "_", "·", " ", "—")


def detect_column(headers, keywords, exclude=None, avoid_substr=()):
    exclude = exclude or set()
    pool = []
    for h in headers:
        if h in exclude or h is None:
            continue
        hl = str(h).lower()
        if any(a.lower() in hl for a in avoid_substr):
            continue
        pool.append((h, hl))
    for kw in keywords:
        k = kw.lower()
        for h, hl in pool:
            if k in hl:
                return h
    return None


def pick_column(headers, exact_names, keywords, exclude=None, avoid_substr=()):
    """精确列名优先（避免「APP版本类型」被误判成「测试类型」），再退回关键字模糊匹配。"""
    hs = [str(h) for h in headers]
    for name in exact_names:
        if name in hs:
            return headers[hs.index(name)]
    return detect_column(headers, keywords, exclude=exclude, avoid_substr=avoid_substr)


def safe_search(pattern, text):
    try:
        return re.search(pattern, text) is not None
    except re.error:
        return pattern in text


def extract_module_from_title(title):
    parts = re.findall(r"【([^】]+)】", str(title))
    if len(parts) >= 3:
        return parts[2]
    return parts[-1] if parts else ""


def load_rows(path, sheet_name=None):
    p = Path(path)
    suffix = p.suffix.lower()
    if suffix in (".xlsx", ".xlsm"):
        try:
            import openpyxl
        except ImportError:
            sys.exit("缺少依赖 openpyxl，请先安装：pip install openpyxl")
        wb = openpyxl.load_workbook(p, data_only=False)
        ws = wb[sheet_name] if sheet_name else wb.active
        data = [list(r) for r in ws.iter_rows(values_only=True)]
        if not data:
            sys.exit(f"工作表为空：{ws.title}")
        headers = [str(h) if h is not None else f"col{i}" for i, h in enumerate(data[0])]
        rows = []
        for i, r in enumerate(data[1:], start=2):
            if all(c is None or str(c).strip() == "" for c in r):
                continue
            d = {headers[j]: (r[j] if j < len(r) else None) for j in range(len(headers))}
            d["__row__"] = i
            d["__orig__"] = len(rows)
            rows.append(d)
        return headers, rows, ws.title
    if suffix == ".json":
        with open(p, encoding="utf-8") as f:
            obj = json.load(f)
        if isinstance(obj, dict) and "testcases" in obj:
            obj = obj["testcases"]
        headers = list(obj[0].keys()) if obj else []
        for i, d in enumerate(obj):
            d["__orig__"] = i
        return headers, obj, None
    if suffix == ".csv":
        import csv
        with open(p, encoding="utf-8-sig", newline="") as f:
            rd = csv.DictReader(f)
            rows = list(rd)
        headers = rd.fieldnames or []
        for i, d in enumerate(rows):
            d["__orig__"] = i
        return headers, rows, None
    sys.exit(f"不支持的文件类型：{suffix}（仅支持 .xlsx/.json/.csv）")


class FlowSorter:
    def __init__(self, flow, module_col, top_col, title_col, type_col, func_col, order_col,
                 part_col=None):
        self.flow = flow or DEFAULT_FLOW
        self.module_col = module_col
        self.top_col = top_col
        self.title_col = title_col
        self.type_col = type_col
        self.func_col = func_col
        self.order_col = order_col

        pcfg = self.flow.get("partition") or {}
        self.part_col = part_col or pcfg.get("column")
        self.part_names = pcfg.get("order") or []
        self.part_default = pcfg.get("default") or ""
        self.part_idx = {p: i for i, p in enumerate(self.part_names)}

        self.stage_of, self.stage_names = self._build_stages()
        self.mod_seq = self._build_module_seq()
        self.rules = self.flow.get("testpoint_rules") or {}
        self.mod_flow = self.flow.get("module_flow") or {}
        self.type_order = self.flow.get("type_order") or DEFAULT_TYPE_ORDER
        self.type_rank = {t: i for i, t in enumerate(self.type_order)}
        # L1 顶级模块层：group=强制分组（同端集中）/ weak=仅作兜底与展示，不打断业务流
        self.top_seq = {m: i for i, m in enumerate(self.flow.get("top_module_sequence") or [])}
        self.top_mode = str(self.flow.get("top_module_mode") or "weak").lower()
        # 优先级层（默认关闭：原库实证「优先级不是执行顺序主轴」）
        self.prio_order = self.flow.get("priority_order") or []
        self.prio_rank = {p: i for i, p in enumerate(self.prio_order)}
        self.sort_by_priority = bool(self.flow.get("sort_by_priority"))
        self.priority_col = self.flow.get("priority_column") or ""

    def _build_stages(self):
        stages = self.flow.get("stages") or []
        stage_of, names = {}, []
        for i, s in enumerate(stages):
            name = s.get("name") or f"阶段{i + 1}"
            names.append(name)
            for m in s.get("modules", []):
                stage_of[m] = i
        return stage_of, names

    def _build_module_seq(self):
        seq = self.flow.get("module_sequence")
        if not seq:
            seq = []
            for s in self.flow.get("stages") or []:
                seq.extend(s.get("modules", []))
        return {m: i for i, m in enumerate(seq)}

    def partition_of(self, row):
        if not self.part_col:
            return 0, ""
        v = str(row.get(self.part_col) or "").strip()
        if not v:
            v = self.part_default
        return self.part_idx.get(v, len(self.part_names)), v

    def module_key(self, module):
        m = str(module or "").strip()
        if m in self.mod_seq:
            return self.mod_seq[m], ""
        best_idx, best_key = None, None
        for key, idx in self.mod_seq.items():
            if m.startswith(key) and (len(m) == len(key) or m[len(key):len(key) + 1] in SEP):
                if best_key is None or len(key) > len(best_key):
                    best_idx, best_key = idx, key
        if best_idx is not None:
            return best_idx, m
        return len(self.mod_seq), m

    def stage_index(self, module):
        m = str(module or "").strip()
        if m in self.stage_of:
            return self.stage_of[m]
        best, best_len = len(self.stage_of), 0
        for key, idx in self.stage_of.items():
            if m.startswith(key) and (len(m) == len(key) or m[len(key):len(key) + 1] in SEP):
                if len(key) > best_len:
                    best, best_len = idx, len(key)
        return best

    def resolve_module_name(self, row):
        if self.module_col:
            v = row.get(self.module_col)
            if v is not None and str(v).strip():
                return str(v).strip()
        if self.top_col and row.get(self.top_col):
            return str(row.get(self.top_col)).strip()
        t = str(row.get(self.title_col) or "") if self.title_col else ""
        return extract_module_from_title(t)

    def testpoint(self, module, title, row):
        """返回 (组下标, 组名, 组内按类型排序?, 组内按优先级排序?)。"""
        rules = self.rules.get(module)
        if not rules:
            for key, rl in self.rules.items():
                if module.startswith(key) and module[len(key):len(key) + 1] in SEP:
                    rules = rl
                    break
        if rules:
            order = sorted(range(len(rules)), key=lambda k: (rules[k].get("priority", 100), k))
            for i in order:
                rule = rules[i]
                match = rule.get("match") or []
                exclude = rule.get("exclude") or []
                if exclude and any(safe_search(p, title) for p in exclude):
                    continue
                if match and any(safe_search(p, title) for p in match):
                    return (i, rule.get("group") or f"G{i + 1:02d}",
                            bool(rule.get("sort_by_type")), bool(rule.get("sort_by_priority")))
            return len(rules), "99 未归类", False, False
        seq = self.mod_flow.get(module) or []
        for i, kw in enumerate(seq):
            if kw and kw in title:
                return i, kw, False, False
        return len(seq), ("99 未归类" if seq else "（整模块按原序）"), False, False

    def type_index(self, test_type):
        return self.type_rank.get(str(test_type or "").strip(), len(self.type_rank))

    def prio_index(self, row):
        col = self.priority_col
        if not col:
            return 0
        return self.prio_rank.get(str(row.get(col) or "").strip(), len(self.prio_rank))

    def top_index(self, row):
        if not self.top_seq or not self.top_col:
            return 0
        v = str(row.get(self.top_col) or "").strip()
        return self.top_seq.get(v, len(self.top_seq))

    def parse_secondary(self, value):
        if value is None or str(value).strip() == "":
            return (2, "", 0)
        s = str(value).strip()
        mm = re.match(r"^(.*?)[-_ ]*(\d+)$", s)
        if mm:
            return (0, mm.group(1), int(mm.group(2)))
        return (1, s, 0)

    def sort(self, rows):
        raw = []
        for row in rows:
            module = self.resolve_module_name(row)
            title = str(row.get(self.title_col) or "") if self.title_col else ""
            gidx, gname, by_type, by_prio = self.testpoint(module, title, row)
            unclassified = "未归类" in gname
            raw.append([module, title, (None if unclassified else gidx), gname,
                        by_type, by_prio, row])

        # 兜底策略：默认 nearest（未命中规则的用例「承接上一个测试点」，保持原相对位置），
        # 仅当显式声明 fallback="tail" 时才排到模块末尾。默认保序可避免打乱原库的测试点顺序。
        tail_mods = {
            m for m, cfg in (self.flow.get("module_options") or {}).items()
            if str(cfg.get("fallback", "")).lower() == "tail"
        }
        cur_mod, anchor = None, -0.5
        for item in raw:
            module, gidx = item[0], item[2]
            if module != cur_mod:
                cur_mod, anchor = module, -0.5
            if gidx is None:
                is_tail = module in tail_mods or any(
                    module.startswith(k) and module[len(k):len(k) + 1] in SEP for k in tail_mods
                )
                if is_tail:
                    item[2] = 9999.0
                else:
                    item[2] = anchor + 0.4
                    item[3] = "↳ 原序承接（保持原位置）"
            else:
                anchor = float(gidx)

        decorated = []
        for module, title, gidx, gname, by_type, by_prio, row in raw:
            tidx = self.type_index(row.get(self.type_col)) if by_type else 0
            nidx = self.prio_index(row) if (by_prio or self.sort_by_priority) else 0
            sec = self.parse_secondary(row.get(self.order_col)) if self.order_col else (3, "", 0)
            pidx, pname = self.partition_of(row)
            key = [pidx]
            if self.top_mode == "group":
                key.append(self.top_index(row))
            key.extend([self.stage_index(module), self.module_key(module)])
            # sub：同一功能模块内再按顶级模块（端）聚块，避免「设备状态与设置」在 APP/固件/联调间来回跳
            if self.top_mode == "sub":
                key.append(self.top_index(row))
            key.extend([gidx, tidx, nidx, sec, row.get("__orig__", 0)])
            decorated.append((tuple(key), row, module, gname, pname))
        decorated.sort(key=lambda x: x[0])
        return decorated


def _reorder_sheet(ws, order_rows, add_seq_col=None):
    max_col = ws.max_column
    snap = []
    for r in order_rows:
        cells = []
        for c in range(1, max_col + 1):
            cell = ws.cell(r, c)
            cells.append((cell.value, copy(cell._style), cell.hyperlink, cell.comment))
        snap.append((cells, ws.row_dimensions[r].height))

    target_col = None
    if add_seq_col:
        hdr_cells = [str(ws.cell(1, c).value) for c in range(1, max_col + 1)]
        if add_seq_col in hdr_cells:
            target_col = hdr_cells.index(add_seq_col) + 1
        else:
            target_col = max_col + 1
            ws.cell(1, target_col).value = add_seq_col
            try:
                ws.cell(1, target_col)._style = copy(ws.cell(1, target_col - 1)._style)
            except Exception:
                pass
        try:
            from openpyxl.utils import get_column_letter
            ws.column_dimensions[get_column_letter(target_col)].width = 10
        except Exception:
            pass

    for i, (cells, h) in enumerate(snap):
        tr = i + 2
        for c, (v, st, hl, cm) in enumerate(cells, start=1):
            cell = ws.cell(tr, c)
            cell.value = v
            try:
                cell._style = copy(st)
            except Exception:
                pass
            try:
                cell.hyperlink = hl
                cell.comment = cm
            except Exception:
                pass
        if target_col:
            ws.cell(tr, target_col).value = i + 1
        if h is not None:
            ws.row_dimensions[tr].height = h
    return target_col


def reorder_workbook(src, dst, plans, add_seq_col=None):
    """plans: [{"sheet": name, "order": [源行号...]}]，一次复制、多表重排。"""
    import openpyxl
    shutil.copyfile(src, dst)
    wb = openpyxl.load_workbook(dst)
    result = {}
    for plan in plans:
        name = plan["sheet"]
        ws = wb[name] if name else wb.active
        result[name] = _reorder_sheet(ws, plan["order"], add_seq_col)
    wb.save(dst)
    return result


def write_rows(path, headers, rows, sheet_title=None):
    p = Path(path)
    suffix = p.suffix.lower()
    if suffix in (".xlsx", ".xlsm"):
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        if sheet_title:
            try:
                ws.title = sheet_title[:31]
            except ValueError:
                pass
        ws.append(headers)
        for r in rows:
            ws.append([r.get(h) for h in headers])
        wb.save(p)
    elif suffix == ".json":
        with open(p, "w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False, indent=2)
    elif suffix == ".csv":
        import csv
        with open(p, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=headers, extrasaction="ignore")
            w.writeheader()
            w.writerows(rows)
    else:
        sys.exit(f"输出类型不支持：{suffix}")


def self_check(rows_in, decorated, title_col):
    problems = []

    def norm(v):
        return "" if v is None else str(v)

    def sig(r):
        return tuple((k, norm(r[k])) for k in sorted(r.keys()) if not k.startswith("__"))

    if sorted(map(sig, rows_in), key=repr) != sorted(map(sig, [d[1] for d in decorated]), key=repr):
        problems.append("❌ 内容一致性校验失败：排序前后用例内容不一致")
    if len(rows_in) != len(decorated):
        problems.append(f"❌ 条数不一致：{len(rows_in)} → {len(decorated)}")
    seq = [(d[0][0], d[2]) for d in decorated]
    seen, breaks, prev = set(), 0, None
    for item in seq:
        if item != prev:
            if item in seen:
                breaks += 1
            seen.add(item)
            prev = item
    if breaks:
        problems.append(f"⚠️ 有 {breaks} 处模块被打散（同一模块出现在多个连续段）")
    empty_titles = sum(1 for d in decorated if not str(d[1].get(title_col) or "").strip())
    return problems, empty_titles


def build_report(sorter, decorated, total, problems, empty_titles, src, out, to_col):
    lines = ["# 测试用例执行顺序排序报告\n"]
    lines.append(f"- 源文件：`{Path(src).name}`")
    lines.append(f"- 输出文件：`{Path(out).name if out else '(仅演练)'}`")
    lines.append(f"- 用例总数：**{total}**")
    lines.append(f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")

    partitions = []
    for key, row, module, gname, pname in decorated:
        if pname not in partitions:
            partitions.append(pname)

    lines.append("## 一、排序结构（分类 → 阶段 → 模块 → 测试点）\n")
    for pname in partitions:
        sub = [d for d in decorated if d[4] == pname]
        lines.append(f"\n# 【{pname or '默认'}】共 {len(sub)} 条\n")
        tree = {}
        order = []
        for key, row, module, gname, _ in sub:
            k = (key[1], module, gname)
            if k not in tree:
                tree[k] = []
                order.append(k)
            tree[k].append(row)
        cur_stage, cur_mod = None, None
        for (stage_i, module, gname) in order:
            sname = sorter.stage_names[stage_i] if stage_i < len(sorter.stage_names) else "未分配阶段"
            if sname != cur_stage:
                lines.append(f"\n### {sname}\n")
                cur_stage, cur_mod = sname, None
            if module != cur_mod:
                cnt = sum(len(v) for (si, m, g), v in tree.items() if m == module)
                lines.append(f"\n**{module}**（{cnt} 条）\n")
                lines.append("| # | 测试点 | 条数 |")
                lines.append("|---|--------|------|")
                cur_mod = module
                gi = 0
            gi += 1
            lines.append(f"| {gi} | {gname} | {len(tree[(stage_i, module, gname)])} |")
        lines.append("")

    unclassified = [(m, g, len(v)) for (si, m, g), v in
                    {}.items()]  # placeholder for type consistency
    un = {}
    for key, row, module, gname, pname in decorated:
        if "未归类" in gname:
            un[module] = un.get(module, 0) + 1

    lines.append("\n## 二、质量自检\n")
    lines.append(f"- 内容零改动校验：{'✅ 通过' if not any('内容一致性' in p for p in problems) else '❌ 失败'}")
    lines.append(f"- 条数校验：{'✅ 通过' if not any('条数' in p for p in problems) else '❌ 失败'}")
    lines.append(f"- 模块成块连续性：{'✅ 通过' if not any('打散' in p for p in problems) else '⚠️ 存在打散'}")
    lines.append(f"- 未归类测试点：{'✅ 0 条' if not un else '⚠️ ' + str(sum(un.values())) + ' 条'}")
    for m, c in un.items():
        lines.append(f"  - {m}：{c} 条")
    if empty_titles:
        lines.append(f"- 空标题行：{empty_titles} 条（置模块末尾）")
    lines.append(f"- 执行序号列：{'已追加（第 %d 列）' % to_col if to_col else '未追加（保持原表结构）'}")
    if problems:
        lines.append("\n### 自检告警\n")
        for p in problems:
            lines.append(f"- {p}")
    lines.append("")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="按业务流程对测试用例执行顺序排序（v2.1 四层模型）")
    ap.add_argument("input", help="测试用例文件 (.xlsx/.xlsm/.json/.csv)")
    ap.add_argument("--output", "-o", help="输出路径（默认 原名_sorted）")
    ap.add_argument("--flow-config", help="流程定义 JSON")
    ap.add_argument("--module-col")
    ap.add_argument("--top-col")
    ap.add_argument("--func-col")
    ap.add_argument("--title-col")
    ap.add_argument("--type-col")
    ap.add_argument("--order-col")
    ap.add_argument("--partition-col", help="分类列名（公共/横屏专项/竖屏专项）")
    ap.add_argument("--priority-col", help="优先级列名（P0-P4，启用优先级层时用）")
    ap.add_argument("--sheet", help="单张工作表名")
    ap.add_argument("--all-sheets", action="store_true", help="处理工作簿内全部 sheet")
    ap.add_argument("--add-seq", metavar="COLNAME", help="追加执行序号列")
    ap.add_argument("--report", help="Markdown 报告路径")
    ap.add_argument("--dump-unclassified", metavar="PATH", help="导出未归类清单")
    ap.add_argument("--inplace", action="store_true", help="覆盖原文件（自动 .bak 备份）")
    ap.add_argument("--dry-run", action="store_true", help="只统计，不写文件")
    args = ap.parse_args()

    flow = DEFAULT_FLOW
    if args.flow_config:
        with open(args.flow_config, encoding="utf-8") as f:
            flow = json.load(f)

    suffix = Path(args.input).suffix.lower()
    sheets = [args.sheet] if args.sheet else [None]
    if args.all_sheets and suffix in (".xlsx", ".xlsm"):
        import openpyxl
        sheets = openpyxl.load_workbook(args.input, read_only=True).sheetnames

    all_plans, reports, dump_lines = [], [], []
    total_all = 0
    sorter_ref = None
    problems_all, empty_all = [], 0

    for sh in sheets:
        headers, rows, sheet_title = load_rows(args.input, sheet_name=sh)
        if not rows:
            continue
        title_col = args.title_col or pick_column(
            headers, ["测试用例标题", "用例标题", "标题"], TITLE_KEYWORDS)
        top_col = args.top_col or pick_column(
            headers, ["顶级功能模块", "一级模块", "所属端"], TOP_KEYWORDS)
        module_col = args.module_col or pick_column(
            headers, ["功能模块", "所属模块", "测试模块"], MODULE_KEYWORDS)
        type_col = args.type_col or pick_column(
            headers, ["测试类型", "用例类型"], TYPE_KEYWORDS)
        prio_col = args.priority_col or pick_column(
            headers, ["测试优先级", "优先级"], PRIORITY_KEYWORDS)
        order_col = args.order_col or detect_column(headers, ORDER_KEYWORDS, exclude={module_col})
        part_col = args.partition_col or detect_column(
            headers, PARTITION_KEYWORDS, exclude={module_col, top_col}
        )
        if not title_col:
            sys.exit(f"未找到用例标题列，现有列：{headers}")

        sorter = FlowSorter(flow, module_col, top_col, title_col, type_col, None, order_col, part_col)
        sorter.priority_col = prio_col
        sorter_ref = sorter
        decorated = sorter.sort(rows)

        print(f"[{sheet_title or '-'}] 用例 {len(rows)} 条 | 标题={title_col} 顶级={top_col or '-'} "
              f"模块={module_col} 分类={part_col or '-'} 类型={type_col} 优先级={prio_col or '-'}")
        problems, empty = self_check(rows, decorated, title_col)
        for p in problems:
            print("  " + p)
        # keep_order=true 的模块允许「只分组、组内保序」，不视为缺规则
        keep = {m for m, cfg in (flow.get("module_options") or {}).items()
                if cfg.get("keep_order")}
        no_rule = sorted({
            d[2] for d in decorated
            if d[2] not in (flow.get("testpoint_rules") or {}) and d[2] not in keep
        })
        if no_rule:
            msg = "⚠️ 以下模块缺少 testpoint_rules（既未声明 keep_order），已退化为默认组：" + "、".join(no_rule)
            print("  " + msg)
            problems.append(msg)
        problems_all += problems
        empty_all += empty
        total_all += len(rows)

        un = {}
        for key, row, module, gname, pname in decorated:
            if "未归类" in gname:
                un[module] = un.get(module, 0) + 1
                dump_lines.append(f"{module}\t{row.get(title_col)}")
        if un:
            print("  未归类:", ", ".join(f"{k}={v}" for k, v in un.items()))

        all_plans.append({"sheet": sheet_title, "order": [d[1]["__row__"] for d in decorated]})
        reports.append((sheet_title, decorated, len(rows), problems, empty))
        if suffix not in (".xlsx", ".xlsm"):
            reports[-1] = (sheet_title, decorated, len(rows), problems, empty)

    if args.dump_unclassified:
        Path(args.dump_unclassified).parent.mkdir(parents=True, exist_ok=True)
        Path(args.dump_unclassified).write_text("\n".join(dump_lines), encoding="utf-8")
        print(f"未归类清单：{args.dump_unclassified}（{len(dump_lines)} 条）")

    out = None
    to_col = None
    if not args.dry_run:
        if args.inplace:
            bak = str(Path(args.input).with_suffix("")) + ".bak" + Path(args.input).suffix
            shutil.copyfile(args.input, bak)
            print(f"已备份：{bak}")
            out = args.input
        else:
            out = args.output or (str(Path(args.input).with_suffix("")) + "_sorted" + Path(args.input).suffix)
        if suffix in (".xlsx", ".xlsm"):
            cols = reorder_workbook(args.input, out, all_plans, args.add_seq)
            to_col = list(cols.values())[0] if cols else None
        else:
            for sheet_title, decorated, _, _, _ in reports:
                if args.add_seq:
                    for i, d in enumerate(decorated, start=1):
                        d[1][args.add_seq] = i
                write_rows(out, headers, [d[1] for d in decorated], sheet_title)
        print(f"已输出：{out}（{len(sheets)} 个工作表，共 {total_all} 条）")
    else:
        print("（dry-run，未写入文件）")

    if args.report and reports:
        chunks = []
        for sheet_title, decorated, n, problems, empty in reports:
            body = build_report(sorter_ref, decorated, n, problems, empty,
                                args.input, out, to_col)
            if len(reports) > 1:
                body = body.replace("# 测试用例执行顺序排序报告\n",
                                    f"# 测试用例执行顺序排序报告 — {sheet_title}\n", 1)
            chunks.append(body)
        rep = "\n\n---\n\n".join(chunks)
        Path(args.report).parent.mkdir(parents=True, exist_ok=True)
        Path(args.report).write_text(rep, encoding="utf-8")
        print(f"已生成报告：{args.report}")


if __name__ == "__main__":
    main()
