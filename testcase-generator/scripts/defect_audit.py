#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
defect_audit.py — 缺陷反哺审计器（v1.8.0 · 阶段 1 只读灰度）

要解决的问题
------------
现有三道闸门（预审 / 覆盖率 / 变异强度）量的都是"我们假想的错"：
  · prescreen 第 7 项是词表黑名单，几乎必过；
  · coverage_audit 的显式 coverage_rule 直接采信，模块名相同只算疑似；
  · mutation_audit 枚举的是脚本自己造的变异体。
三者可以集体及格、又集体错过同一个真实故障——**没有任何机制引入外部事实**。
本脚本把"真实发生过的缺陷"作为地面真值，反算"用例库到底拦住了多少"。

三层（--layer，默认 1）
  层 1  只吃缺陷单：字段可用性体检 + 缺陷拦截率 DER（缺字段时如实标不可算）+ 代理指标
  层 2  加入用例库：缺陷 ↔ 用例归属（L1/L2/L3）+ 三态判定 + 用例缺陷发现力 DDF + 死用例候选
  层 3  输出回填建议：每个 escaped 缺陷缺哪类断言（7 类），生成回归用例草案

关键设计（防"假拦截"，与 mutation_review 的 killer_pattern 教训同构）
  `prevented` 只认「强判别要素」命中，且**只在 expected 上匹配**：
    强：NUM 具体数值 / TXT 引号内逐字文案 / ACT 结果态动作 / UNIQ 唯一性
    弱：NEG 否定词 / BND 边界词 —— 单独命中**不算** prevented（"不允许"到处都是，
        只凭一个否定词就判"拦住了"，就是又一次假杀死）
  抽不出任何要素的缺陷不脑补，直接落 escaped，并在报告里标「缺判别要素」。

四态口径（比方案文档更保守，是 2026-11-09 实测后修正的，见文末"实测教训"）
  escaped      缺陷确实发生且用例库没有可拦截的断言 → **可靠**（「漏」是事实）
  undecidable  无效缺陷（被驳回 / 有意设计）或信息不足 → 不进分母
  suspected    缺陷标题里的判别要素在**某条用例的同一分句**里出现过 → 只能算"疑似已拦"，
               必须人工确认。默认**不计入** prevent，避免假拦截
  prevented    仅当 `--prevented-mode auto` 显式开启，把 suspected 直接采纳（**慎用**）

实测教训（225 条真实缺陷 × 2431 条真实用例，2026-11-09）
  把 suspected 直接当 prevented 时，人工抽检 8 条只对 2 条（一致率 25%）；
  改成四态后重抽 10 条：**escaped 5/5 成立，suspected 0/5 成立**。
  根因不是阈值没调好，而是方法问题：mutation_audit 能做「杀死判定」，是因为变异体
  与用例出自同一句需求、语义天然对齐；而缺陷与用例是两份独立文本，只有「需求 ID」
  这一层锚点能对齐。所以：**「漏」可以自动判，「拦」不行**。
  因此 suspected 清单默认**不写进报告**（`--with-suspected` 才输出）——
  一份 0 命中率的待确认清单，只会把人工确认成本转嫁给使用者。
  要做可靠的「拦」，必须先有 需求规则 ID ↔ 用例 coverage_rule 的显式映射（阶段 2）。

退出码：0（--gate off 默认，恒放行）；0+警告（--gate warn）；2 输入/参数错误。
本脚本**不阻断**，不改变任何既有闸门的退出码语义。
"""

import argparse
import csv
import json
import os
import re
import sys
from datetime import datetime

# ---------------------------------------------------------------- 常量

DEFAULT_L2_MIN_KW = 2          # L2 关键词命中最少个数
DEFAULT_L3_THRESHOLD = 0.35    # L3 文本相似度（比 coverage 的 0.08 严，缺陷标题短）
DEFAULT_ESCAPED_WARN = 0.80    # --gate warn 的告警线
MIN_TITLE_LEN = 4              # 去掉标签后短于此视为信息不足 → undecidable

VERSION_TAG_RE = re.compile(r"^(?:v|V)?\d+(?:\.\d+)*$|^mvp$|^MVP$|^demo$|^Demo$")
# 机型标签：T5102 / T5107/T5102 / U014 / T5102-T5107 —— 不是模块，别当模块用
MODEL_TAG_RE = re.compile(r"^[A-Za-z]{1,3}\d{3,}(?:[/\-,、][A-Za-z0-9]+)*$")
DEVICE_TAGS = {"移动端", "APP", "App", "app", "联调", "设备端", "遥控", "遥控器",
               "小程序", "H5", "服务端", "后台", "固件", "硬件", "iOS", "Android",
               "彩屏", "电子表", "横屏端", "竖屏端", "横/竖屏端", "横屏", "竖屏",
               "双屏", "大屏"}
# 这些「模块」其实是端/形态级桶，不是功能模块。TAPD 的 module 字段常填成它们，
# 直接当模块会得到「横屏端 100% 逃逸」这种正确但没用的结论。
GENERIC_MODULES = DEVICE_TAGS | {"通用", "其他", "未分类", "全部"}
TAG_RE = re.compile(r"【([^】]{1,24})】")

# 缺陷发现阶段字段（DER 依赖它）—— TAPD 里分别是：
#   source/sourcephase/originphase/testphase；有些项目用「发现阶段」自定义字段
PHASE_FIELDS = ("sourcephase", "source", "originphase", "testphase", "found_phase")
ONLINE_WORDS = ("线上", "生产", "客户", "用户反馈", "外场", "灰度", "发布后", "online", "prod")
TEST_WORDS = ("测试", "提测", "内测", "验收", "联调", "冒烟", "回归", "test", "qa")

# 强判别要素：能区分对错
ACT_WORDS = ("停止", "归零", "跳转", "弹出", "消失", "置灰", "禁用", "不可用", "清空",
             "重置", "锁定", "登出", "退出", "返回首页", "无反应", "无响应", "不显示",
             "无法进入", "无法继续", "中断", "重启", "恢复", "同步", "生效", "保存",
             "记录", "生成", "刷新", "选中", "聚焦", "遮挡", "重合", "溢出")
NEG_WORDS = ("不", "无", "未", "没有", "禁止", "不允许", "不应", "不能", "无法")
BND_WORDS = ("超过", "超出", "未达", "不足", "不低于", "不超过", "至少", "最多",
             "上限", "下限", "以内", "以上", "以下")
UNIQ_WORDS = ("仅一个", "仅有一条", "仅一条", "仅有", "只允许", "只能", "唯一", "同一", "单个",
              "一条", "一次", "单次")
QUOTE_RE = re.compile(r"[“\"'‘「]([^”\"'’」]{2,60})[”\"'’」]")
NUM_RE = re.compile(r"\d+(?:\.\d+)?\s*(?:%|次|秒|分钟|小时|天|个|条|人|台|步|元|字符|个字|km/h|ms)?")
ENUM_WORDS = ("逐一", "逐个", "依次", "分别", "遍历", "逐项", "逐条")
# 数值的「区分力」门槛：单位/百分号、小数、或 ≥2 位整数才算强要素。
# 单个数字（尤其是标题里 【V1】 这类版本号）几乎必然在任意 expected 里命中，
# 放进来就会造成成片的假拦截——2026-11-09 实测：111 条「已拦」里有大量是 "1" 撞上的。
UNIT_AFTER_RE = re.compile(r"\s*(%|次|秒|分钟|小时|天|个|条|人|台|步|元|字符|个字|km/h|ms|km)")

# 缺陷判别要素 → 用例侧需要补的断言类型（与 mutation 算子对齐）
GAP_DESC = {
    "NUM": "具体数值（逐数/逐字），不能只写“显示正确”",
    "TXT": "逐字文案（引号内原文），不能只写“提示正确”",
    "ACT": "结果态证据（状态变更后的可观测现象），不能只写“提示已XX”",
    "UNIQ": "唯一性/计数断言（“仅一条”“同一”），不能只写“正常”",
    "NEG": "显式否定结果（“不出现/不再弹出/无新增”）",
    "BND": "边界两侧各一条（未达 / 已达）",
    "PHEN": "现象级断言（先能描述“错成什么样”，才谈得上判红）",
}

CASE_HEADER_ALIASES = {
    "id": ["用例编号", "编号", "id", "用例id", "caseid"],
    "module": ["功能模块", "测试模块", "模块", "所属模块"],
    "module_fallback": ["顶级功能模块"],
    "title": ["用例名称", "用例标题", "标题", "名称", "title", "name"],
    "steps": ["测试步骤", "步骤", "操作步骤", "steps"],
    "expected": ["预期结果", "预期", "expected"],
    "result": ["测试结果", "执行结果", "实际结果", "result"],
    "defect": ["关联缺陷", "缺陷", "缺陷单号", "bug", "bugid", "缺陷id"],
}


# ---------------------------------------------------------------- 结果码语义

# 不同项目用不同字母，语义必须钉死——否则"还没测"会被算成"跑过但失败"。
# 实测：某正式库 1669 条已执行用例里有 45 条 NP，早年实现把"有结果就算执行过"，
# 于是 NP 抬高执行率、掩盖真实进度；更糟的是部分统计把 NP 当"非通过"，
# 让"本阶段还没排上"混进缺陷漏测口径。
RESULT_PASS = ("PASS", "通过", "OK", "P")
RESULT_FAIL = ("FAIL", "失败", "不通过", "NG", "F")
RESULT_PENDING = ("NP",)                       # 当前阶段需要测试，但尚未执行
RESULT_NOT_RUN = ("NT", "未测试", "未执行", "NOTEST")
RESULT_BLOCKED = ("BLOCK", "BLOCKED", "阻塞")


def classify_result(raw):
    """把结果码归一成 pass / fail / pending / not_run / blocked / unknown / empty。

    NP（本阶段应测未测）归 **pending**，属于「未执行」而非「失败」。
    这条区分直接影响两件事：执行进度是否被虚高、以及"未测"会不会被算成"漏测"。
    """
    s = norm(raw).upper()
    if not s:
        return "empty"
    if s in RESULT_PASS:
        return "pass"
    if s in RESULT_FAIL:
        return "fail"
    if s in RESULT_PENDING:
        return "pending"
    if s in RESULT_NOT_RUN:
        return "not_run"
    if s in RESULT_BLOCKED:
        return "blocked"
    # 兜底：包含式匹配（"PASS(见备注)"、"失败-环境问题" 这类）
    if any(k in s for k in ("PASS", "通过")):
        return "pass"
    if any(k in s for k in ("FAIL", "失败")):
        return "fail"
    if "NP" in s:
        return "pending"
    if "NT" in s:
        return "not_run"
    if "BLOCK" in s or "阻塞" in s:
        return "blocked"
    return "unknown"


# ---------------------------------------------------------------- 文本工具

def norm(s):
    return re.sub(r"\s+", " ", str(s or "")).strip()


def bigrams(s):
    s = re.sub(r"[^\w\u4e00-\u9fa5]", "", norm(s))
    return {s[i:i + 2] for i in range(len(s) - 1)} if len(s) > 1 else ({s} if s else set())


def jaccard(a, b):
    A, B = bigrams(a), bigrams(b)
    if not A or not B:
        return 0.0
    return len(A & B) / len(A | B)


def keywords(s):
    """中文/英文关键词粗切：中文取 2-4 字片段里的名词性片段，英文取词。"""
    s = norm(s)
    out = set()
    for w in re.findall(r"[A-Za-z][A-Za-z0-9_]{1,}", s):
        if len(w) >= 3:
            out.add(w.lower())
    for seg in re.findall(r"[\u4e00-\u9fa5]{2,}", s):
        for n in (4, 3, 2):
            for i in range(0, len(seg) - n + 1):
                out.add(seg[i:i + n])
    return out


def is_enum_case(c):
    text = " ".join([norm(c.get("steps")), norm(c.get("expected"))])
    return any(w in text for w in ENUM_WORDS)


# ---------------------------------------------------------------- 输入解析

def _pick(row, aliases):
    for a in aliases:
        for k in row:
            if norm(k).lower() == a.lower():
                return row[k]
    for a in aliases:
        for k in row:
            if a.lower() in norm(k).lower():
                return row[k]
    return None


def load_bugs(path):
    """支持：TAPD API dump（{data:[{Bug:{}}]}）/ 扁平数组 / .xlsx / .csv"""
    low = path.lower()
    if low.endswith((".xlsx", ".xlsm")):
        return _load_bugs_xlsx(path)
    if low.endswith(".csv"):
        with open(path, encoding="utf-8-sig", newline="") as f:
            return [dict(r) for r in csv.DictReader(f)]
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict):
        if "data" in data:
            data = data["data"]
        elif "bugs" in data:
            data = data["bugs"]
        else:
            raise ValueError("缺陷 JSON 需含 data / bugs 键，或直接是数组")
    if not isinstance(data, list):
        raise ValueError("缺陷文件格式不支持")
    out = []
    for it in data:
        if isinstance(it, dict) and "Bug" in it:
            out.append(it["Bug"])
        elif isinstance(it, dict):
            out.append(it)
    return out


def dedupe_bugs(bugs):
    """同一缺陷会因分页导出 / 多表合并重复出现。按 id 去重（无 id 的原样保留），
    否则 DER 分母、回归率、逃逸率全部被重复计数抬高。"""
    seen, out = set(), []
    for b in bugs:
        bid = norm(b.get("id"))
        if bid:
            if bid in seen:
                continue
            seen.add(bid)
        out.append(b)
    return out


def _load_bugs_xlsx(path):
    try:
        from xlsx_util import open_workbook
    except ImportError:
        from .xlsx_util import open_workbook
    # 不用 read_only：云端工具存过的文件 dimension 常是 A1:A1，会静默读 0 行
    wb = open_workbook(path)
    ws = wb[wb.sheetnames[0]]
    rows = list(ws.iter_rows(values_only=True))
    wb.close()
    if not rows:
        return []
    hdr = [norm(x) for x in rows[0]]
    return [dict(zip(hdr, r)) for r in rows[1:] if any(x not in (None, "") for x in r)]


def load_cases(path):
    low = path.lower()
    if low.endswith((".xlsx", ".xlsm")):
        return _load_cases_xlsx(path)
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict) and "cases" in data:
        data = data["cases"]
    if not isinstance(data, list):
        raise ValueError("用例文件需为数组，或含 cases 键的对象")
    out = []
    for i, c in enumerate(data, 1):
        row = {
            "id": norm(c.get("id") or c.get("name") or f"ROW{i}"),
            "module": norm(c.get("module")),
            "title": norm(c.get("title") or c.get("name")),
            "steps": norm(c.get("steps")),
            "expected": norm(c.get("expected")),
            "result": norm(c.get("result")),
            "defect": norm(c.get("defect")),
        }
        row["range_case"] = is_enum_case(row)
        out.append(row)
    return out


def _load_cases_xlsx(path):
    try:
        from xlsx_util import open_workbook
    except ImportError:
        from .xlsx_util import open_workbook
    # 不用 read_only：云端工具存过的文件 dimension 常是 A1:A1，会静默读 0 行
    wb = open_workbook(path)
    ws = wb[wb.sheetnames[0]]
    rows = list(ws.iter_rows(values_only=True))
    wb.close()
    if not rows:
        return []
    hdr = [norm(x) for x in rows[0]]
    # 表头可能存在「顶级功能模块」与「功能模块」并存 —— 精确匹配优先，
    # 否则会把整个「设备端」当模块，模块级指标全糊在一起（coverage_audit 踩过）。
    idx = {}
    for key, aliases in CASE_HEADER_ALIASES.items():
        pos = None
        for a in aliases:
            for i, h in enumerate(hdr):
                if h.lower() == a.lower():
                    pos = i
                    break
            if pos is not None:
                break
        if pos is None:
            for a in aliases:
                for i, h in enumerate(hdr):
                    if a.lower() in h.lower():
                        pos = i
                        break
                if pos is not None:
                    break
        idx[key] = pos
    out = []
    for n, r in enumerate(rows[1:], 2):
        def g(key):
            p = idx.get(key)
            if p is None or p >= len(r) or r[p] is None:
                return ""
            return norm(r[p])
        if not g("title"):
            continue
        cid = g("id") or f"ROW{n}"
        row = {
            "id": cid, "module": g("module") or g("module_fallback"),
            "title": g("title"), "steps": g("steps"),
            "expected": g("expected"), "result": g("result"), "defect": g("defect"),
        }
        # 范围性用例（"逐一/逐个/依次/分别…"一条覆盖 N 个子场景）：不参与 DDF 排名，
        # 也不进死用例候选。T5102 库里有 164 条（6.7%），误判会直接污染指标。
        row["range_case"] = is_enum_case(row)
        out.append(row)
    return out


# ---------------------------------------------------------------- 缺陷归一

def bug_tags(title):
    return TAG_RE.findall(norm(title))


def bug_scope(bug):
    """端归属：移动端 / 设备 / 空。标题第二段标签决定（APP、联调、T5102 都算设备）。"""
    for t in bug_tags(bug.get("title")):
        if t == "移动端":
            return "移动端"
        if t in DEVICE_TAGS or MODEL_TAG_RE.match(t):
            return "设备"
    return ""


def bug_module_raw(bug):
    """未归一的模块名：module 字段（非端/形态级桶时）> 标题里第一个"既非版本、亦非端、亦非机型"的标签"""
    m = norm(bug.get("module"))
    if m and m not in GENERIC_MODULES:
        return m
    cand = [t for t in bug_tags(bug.get("title"))
            if not VERSION_TAG_RE.match(t) and t not in DEVICE_TAGS
            and not MODEL_TAG_RE.match(t)]
    return cand[0] if cand else m


def map_module(raw, scope, module_map):
    """模块归一：`端/模块` 精确 > `*/模块` 通配 > `模块` 原名。
    映射为 "" 表示「用例库里没有对应模块」——这是真实的零覆盖，不要硬塞。"""
    if not module_map or not raw:
        return raw
    for key in (f"{scope}/{raw}" if scope else None, f"*/{raw}", raw):
        if key and key in module_map:
            v = module_map[key]
            # 映射为 "" = 用例库里根本没有这个模块（真实零覆盖）。不能直接置空，
            # 否则这些缺陷会塌进「未分模块」，把"哪一块完全没测"这个最有用的结论抹掉。
            return v if v else f"{raw}（库内无对应模块）"
    return raw


def bug_module(bug, module_map=None):
    return map_module(bug_module_raw(bug), bug_scope(bug), module_map)


def normalize_bug(b, module_map=None):
    raw = bug_module_raw(b)
    scope = bug_scope(b)
    return {
        "id": norm(b.get("id")),
        "title": norm(b.get("title")),
        "desc": strip_html(b.get("description") or b.get("desc"))[:600],
        "module": map_module(raw, scope, module_map),
        "raw_module": raw,
        "scope": scope,
        "severity": norm(b.get("severity")),
        "priority": norm(b.get("priority_label") or b.get("priority")),
        "status": norm(b.get("status")),
        "resolution": norm(b.get("resolution")),
        "created": norm(b.get("created")),
        "version_report": norm(b.get("version_report")),
        "regression": norm(b.get("regression_number")),
        "reopen": bool(norm(b.get("reopen_time"))),
        "reject": bool(norm(b.get("reject_time"))),
        "phase": next((norm(b.get(f)) for f in PHASE_FIELDS if norm(b.get(f))), ""),
        "tags": bug_tags(b.get("title")),
    }


# ---------------------------------------------------------------- 判别要素抽取

def strip_tags(title):
    """去掉【版本】【端】【机型】【模块】标签，只留现象描述。
    否则 【V1】 里的 "1" 会被当成判别数值——实测这是最大的一类假拦截。"""
    return norm(TAG_RE.sub(" ", norm(title)))


HTML_TAG_RE = re.compile(r"<[^>]{0,600}>")
CSS_DECL_RE = re.compile(r"[A-Za-z-]{2,20}\s*:\s*[^;\"']{0,60};")
URL_RE = re.compile(r"https?://\S+|www\.\S+")


def strip_html(s):
    """TAPD 的 description 是富文本 HTML。不去掉就会从 `font-size: 18px` 里
    抽出 "18"/"50" 这类假判别数值——实测第二大假拦截来源。"""
    t = str(s or "")
    if "<" not in t and "&" not in t:
        return norm(t)
    t = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", t, flags=re.S | re.I)
    t = URL_RE.sub(" ", t)
    t = HTML_TAG_RE.sub(" ", t)
    t = CSS_DECL_RE.sub(" ", t)
    t = (t.replace("&nbsp;", " ").replace("&lt;", " ").replace("&gt;", " ")
          .replace("&amp;", " ").replace("&quot;", " ").replace("&#39;", " "))
    return norm(t)


def _num_strong(s, tail):
    """数值的区分力：带单位/百分号、是小数、或 ≥2 位整数才算强要素。"""
    if UNIT_AFTER_RE.match(tail or ""):
        return True
    if "." in s:
        return True
    return len(s) >= 2


def extract_discriminators(text, drop_tags=True):
    """从缺陷标题/描述抽「能区分对错」的要素。返回 [{type, pattern, basis, strong}]"""
    t = strip_tags(text) if drop_tags else norm(text)
    out = []

    for q in QUOTE_RE.findall(t):
        q = q.strip()
        if len(q) >= 2:
            out.append({"type": "TXT", "pattern": re.escape(q[:12]), "basis": q,
                        "strong": True})

    for m in re.finditer(r"\d+(?:\.\d+)?", t):
        s = m.group(0)
        tail = t[m.end():m.end() + 4]
        out.append({"type": "NUM",
                    "pattern": r"(?<!\d)" + re.escape(s) + r"(?!\d)",
                    "basis": s + (tail.strip()[:2] if UNIT_AFTER_RE.match(tail) else ""),
                    "strong": _num_strong(s, tail)})

    for w in ACT_WORDS:
        if w in t:
            out.append({"type": "ACT", "pattern": re.escape(w), "basis": w, "strong": True})
            break

    for w in UNIQ_WORDS:
        if w in t:
            out.append({"type": "UNIQ", "pattern": re.escape(w), "basis": w, "strong": True})
            break

    neg = [w for w in NEG_WORDS if w in t]
    if neg:
        out.append({"type": "NEG", "pattern": re.escape(neg[0]), "basis": neg[0],
                    "strong": False})

    bnd = [w for w in BND_WORDS if w in t]
    if bnd:
        out.append({"type": "BND", "pattern": re.escape(bnd[0]), "basis": bnd[0],
                    "strong": False})

    # 去重（同 type 同 basis）
    seen, uniq = set(), []
    for d in out:
        k = (d["type"], d["basis"])
        if k not in seen:
            seen.add(k)
            uniq.append(d)
    return uniq


STRONG_TYPES = {"NUM", "TXT", "ACT", "UNIQ"}

# 泛词：出现在几乎任何 expected 里，不能作为「同一件事」的证据
STOP_KW = {"正常", "错误", "异常", "显示", "功能", "状态", "提示", "页面", "界面", "点击",
           "进行", "可以", "一致", "用户", "内容", "问题", "设计", "测试", "操作", "支持"}


def _clauses(text):
    """按句/分句切开，顺带削掉 "1. " "2、" 这类列表序号。
    不切分的话，expected 里任意位置的 "跳转" 都会跟标题里的 "跳转" 撞上。"""
    parts = re.split(r"[。；;\n]+|\d+\s*[.、)）]\s*", norm(text))
    return [p.strip() for p in parts if p.strip()]


def _clause_hit(expected, disc, kws):
    """判别要素与"对象词"必须落在**同一分句**里，才算真的在验同一件事。
    对象词按「长度降序」取前 8 个（长词更具体），保证结果可复现——
    以前直接取 set 的前 4 个，顺序受 hash 影响，同一输入两次跑可能不同判决。"""
    obj = sorted([k for k in kws if len(k) >= 2], key=lambda x: (-len(x), x))[:8]
    for cl in _clauses(expected):
        if not re.search(disc["pattern"], cl):
            continue
        if not obj or any(k in cl for k in obj):
            return cl
    return None


# ---------------------------------------------------------------- 层 1

def _phase_of(b):
    """发现阶段取值：优先归一后的 `phase`，回退到 TAPD 原始字段名。
    normalize_bug 会把原始字段合并成 `phase`，只读原始字段会导致永远判「全空」。"""
    v = norm(b.get("phase"))
    if v:
        return v
    return next((norm(b.get(f)) for f in PHASE_FIELDS if norm(b.get(f))), "")


def probe_fields(bugs):
    """字段可用性体检：DER 能不能算，缺哪个字段，一句话说清。"""
    n = len(bugs) or 1
    filled = {f: sum(1 for b in bugs if norm(b.get(f))) for f in PHASE_FIELDS}
    n_phase = sum(1 for b in bugs if norm(b.get("phase")))
    if n_phase:
        filled["phase"] = n_phase
    best = max(filled, key=lambda k: filled[k])
    n_best = filled[best]

    phases = [_phase_of(b) for b in bugs]
    n_test = sum(1 for p in phases if any(w.lower() in p.lower() for w in TEST_WORDS))
    n_online = sum(1 for p in phases if any(w.lower() in p.lower() for w in ONLINE_WORDS))
    return {
        "phase_field_filled": filled,
        "phase_field_best": best if n_best else None,
        "phase_filled_rate": round(n_best / n, 4),
        "phase_test": n_test,
        "phase_online": n_online,
        "der_available": bool(n_best and n_online and n_test),
        "der_reason": ("可用：发现阶段字段已填且同时存在测试发现与线上发现"
                       if (n_best and n_online and n_test) else
                       ("不可算：发现阶段字段（" + "/".join(PHASE_FIELDS) + "）全空"
                        if not n_best else
                        ("不可算：有阶段字段但缺线上样本（线上 %d 条）—— 此时算出的 100%% 是自嗨"
                         % n_online if not n_online else
                         "不可算：缺测试阶段样本（测试 %d 条）" % n_test))),
    }


def is_invalid(bug):
    """无效缺陷：被驳回 / 有意设计"""
    if bug["reject"]:
        return "rejected"
    r = bug["resolution"].lower()
    if "intentional" in r or "设计如此" in r or "非缺陷" in r:
        return "intentional_design"
    return ""


def compute_layer1(bugs):
    valid = [b for b in bugs if not is_invalid(b)]
    invalid = [b for b in bugs if is_invalid(b)]
    # 分母只算有效缺陷：被驳回的缺陷不该进 DER 分母（与层 2 的 evaluable 口径一致）
    probe = probe_fields(valid)

    n = len(valid) or 1
    reg = [b for b in valid if b["regression"] not in ("", "0")]
    reopen = [b for b in valid if b["reopen"]]

    by_mod = {}
    for b in valid:
        m = b["module"] or "未分模块"
        d = by_mod.setdefault(m, {"bugs": 0, "regression": 0, "fatal": 0})
        d["bugs"] += 1
        if b["regression"] not in ("", "0"):
            d["regression"] += 1
        if b["severity"] in ("fatal", "serious"):
            d["fatal"] += 1

    der = None
    if probe["der_available"]:
        der = round(probe["phase_test"] / (probe["phase_test"] + probe["phase_online"]), 4)

    return {
        "layer": 1,
        "total": len(bugs), "valid": len(valid), "invalid": len(invalid),
        "invalid_detail": [{"id": b["id"], "reason": is_invalid(b), "title": b["title"]}
                           for b in invalid],
        "probe": probe,
        "der": der, "dlr": None if der is None else round(1 - der, 4),
        "regression_rate": round(len(reg) / n, 4),
        "reopen_rate": round(len(reopen) / n, 4),
        "regression_ids": [b["id"] for b in reg],
        "reopen_ids": [b["id"] for b in reopen],
        "by_module": {k: dict(v, regression_rate=round(v["regression"] / (v["bugs"] or 1), 4))
                      for k, v in sorted(by_mod.items(), key=lambda x: -x[1]["bugs"])},
    }


# ---------------------------------------------------------------- 层 2

def case_features(c):
    return {
        "text": " ".join([c["title"], c["steps"], c["expected"]]),
        "module": c["module"],
    }


def match_l1(bug, cases):
    """显式关联：用例「关联缺陷」列含该缺陷 id（或缺陷 id 出现在用例文本里）"""
    bid = bug["id"]
    if not bid:
        return []
    hit = []
    for c in cases:
        blob = c["defect"] + " " + c["title"] + " " + c["expected"]
        if bid and bid in blob:
            hit.append(c)
    return hit


def match_l2(bug, cases, min_kw=DEFAULT_L2_MIN_KW, top=3):
    """结构匹配：模块归一相等 + 关键词命中 ≥ min_kw。只在同模块内找，**只取最相关 top3**。

    取全量会让"模块内任意一条用例命中一个泛动词"就判拦住——实测这是最大假拦截来源
    （训练完成无反馈弹窗 被 "设备未连接窗口提示" 判为已拦）。"""
    if not bug["module"]:
        return []
    text = strip_tags(bug["title"]) + " " + bug["desc"]
    kw_bug = keywords(text)
    hit = []
    for c in cases:
        if norm(c["module"]) != bug["module"]:
            continue
        kw_c = keywords(c["title"] + " " + c["expected"] + " " + c["steps"])
        common = {w for w in (kw_bug & kw_c) if w not in STOP_KW}
        if len(common) >= min_kw:
            hit.append((c, common))
    hit.sort(key=lambda x: -len(x[1]))
    return hit[:top]


def match_l3(bug, cases, threshold=DEFAULT_L3_THRESHOLD):
    if not threshold:
        return []
    text = bug["title"]
    scored = [(c, jaccard(text, c["title"] + " " + c["expected"])) for c in cases]
    scored = [(c, s) for c, s in scored if s >= threshold]
    scored.sort(key=lambda x: -x[1])
    return scored[:3]


def judge_bug(bug, cases, min_kw=DEFAULT_L2_MIN_KW, l3_threshold=DEFAULT_L3_THRESHOLD,
              prevented_mode="off"):
    """四态判定。
    默认 `prevented_mode="off"`：强要素命中只判 `suspected`（疑似已拦，需人工确认），
    不宣称"拦住了"——实测自动判定一致率仅 25%，硬报会掩盖真实漏测。"""
    bad = is_invalid(bug)
    if bad:
        return {"verdict": "undecidable", "confidence": "-", "reason": bad,
                "matched_cases": [], "gap_type": "", "discriminators": []}

    # 信息不足：标题里只有【版本】【端】【模块】标签、没有现象描述。
    # 以前这里写成 `and not bug["tags"]`，但绝大多数缺陷都有标签 → 分支形同废弃，
    # "只有标签"的缺陷会被硬判 escaped，污染漏测率。
    if len(strip_tags(bug["title"]) + bug["desc"]) < MIN_TITLE_LEN:
        return {"verdict": "undecidable", "confidence": "-",
                "reason": "信息不足（只有标签，无现象描述）",
                "matched_cases": [], "gap_type": "", "discriminators": []}

    disc = extract_discriminators(bug["title"] + " " + bug["desc"])

    l1 = match_l1(bug, cases)
    if l1:
        pool, level = [(c, {"L1"}) for c in l1], "L1"
    else:
        l2 = match_l2(bug, cases, min_kw)
        if l2:
            pool, level = l2, "L2"
        else:
            pool, level = [], "-"

    # 在候选池里找「命中强判别要素」的用例（只看 expected，不看 steps/标题）
    strong = [d for d in disc if d.get("strong")]
    weak_only = [d for d in disc if not d.get("strong")]

    killers = []
    for c, kws in pool:
        for d in strong:
            cl = _clause_hit(c["expected"], d, set() if level == "L1" else kws)
            if cl:
                killers.append((c["id"], d["type"], d["basis"], cl[:40]))
                break

    if killers:
        v = "prevented" if prevented_mode == "auto" else "suspected"
        return {"verdict": v, "confidence": level,
                "reason": ("expected 同一分句内命中强判别要素"
                           if v == "prevented" else "疑似命中（需人工确认，未计入已拦）"),
                "matched_cases": [c["id"] for c, _ in pool][:5],
                "killed_by": killers,
                "gap_type": "", "discriminators": [d["type"] for d in disc]}

    # 未拦住：说清缺什么
    if strong:
        gap = strong[0]["type"]
    elif weak_only:
        gap = weak_only[0]["type"]
    else:
        gap = "PHEN"

    if pool:
        reason = "有用例关联，但 expected 无强判别要素（挂着拦不住）"
    elif level == "-":
        reason = "无任何用例关联（该场景无用例）"
    else:
        reason = "无任何用例关联"

    l3 = [] if pool else [(c["id"], round(s, 3)) for c, s in match_l3(bug, cases, l3_threshold)]
    if l3 and not pool:
        reason += "；L3 疑似：%s（不计入，仅提示）" % ", ".join(f"{i}({s})" for i, s in l3)

    return {"verdict": "escaped", "confidence": level, "reason": reason,
            "matched_cases": [c["id"] for c, _ in pool][:5],
            "killed_by": [], "gap_type": gap,
            "l3_hints": l3,
            "discriminators": [d["type"] for d in disc]}


def compute_layer2(bugs, cases, min_kw=DEFAULT_L2_MIN_KW, l3_threshold=DEFAULT_L3_THRESHOLD,
                   protected=None, prevented_mode="off"):
    protected = set(protected or [])
    rows = []
    for b in bugs:
        j = judge_bug(b, cases, min_kw, l3_threshold, prevented_mode)
        rows.append(dict(b, **j))

    # 分母只排除 undecidable（无效缺陷/信息不足）。suspected 仍留在分母里：
    # 它"可能有拦"，但没确认，按保守口径算作未确认逃逸。
    evaluable = [r for r in rows if r["verdict"] != "undecidable"]
    ne = len(evaluable) or 1
    prevented = [r for r in rows if r["verdict"] == "prevented"]
    suspected = [r for r in rows if r["verdict"] == "suspected"]
    escaped = [r for r in rows if r["verdict"] == "escaped"]
    undec = [r for r in rows if r["verdict"] == "undecidable"]

    # 模块级 DDF / 逃逸率
    by_mod = {}
    for c in cases:
        m = c["module"] or "未分模块"
        by_mod.setdefault(m, {"cases": 0, "linked": 0})
        by_mod[m]["cases"] += 1
    linked_ids = set()
    for r in rows:
        if r["verdict"] in ("prevented", "suspected", "escaped") and r["matched_cases"]:
            for cid in r["matched_cases"]:
                linked_ids.add(cid)
    for c in cases:
        m = c["module"] or "未分模块"
        if c["id"] in linked_ids:
            by_mod[m]["linked"] += 1
    for m, d in by_mod.items():
        d["ddf"] = round(d["linked"] / (d["cases"] or 1), 4)

    bug_mod = {}
    for r in evaluable:
        m = r["module"] or "未分模块"
        d = bug_mod.setdefault(m, {"bugs": 0, "escaped": 0, "prevented": 0, "suspected": 0})
        d["bugs"] += 1
        d[r["verdict"]] = d.get(r["verdict"], 0) + 1
    for m, d in bug_mod.items():
        d["escape_rate"] = round(d["escaped"] / (d["bugs"] or 1), 4)
        d["escape_hi"] = round((d["escaped"] + d["suspected"]) / (d["bugs"] or 1), 4)

    # 死用例候选：① 未关联任何缺陷 ② 有执行记录且全通过 ③ 非范围性 ④ 不在变异保护名单
    # 关键前提：必须有执行数据。2431 条库里「测试结果」全空时，
    # "从未失败过"和"从未跑过"无法区分，此时强行出候选池等于把 80% 的库判死。
    linked_case_ids = {cid for r in rows for cid in r["matched_cases"]}
    # 结果码语义：只有 pass/fail 才算「执行过」。
    # NP（本阶段应测未测）是「未执行」，把它算进执行率会虚高进度，
    # 也会让"还没排上"被误解成"跑了没好"。
    kinds = {c["id"]: classify_result(c.get("result")) for c in cases}
    executed = [c for c in cases if kinds.get(c["id"]) in ("pass", "fail")]
    pending = [c for c in cases if kinds.get(c["id"]) == "pending"]
    blocked = [c for c in cases if kinds.get(c["id"]) == "blocked"]
    executed_rate = round(len(executed) / (len(cases) or 1), 4)
    # 无缺陷数据时同样不出候选池：没有外部事实，"没关联缺陷"等于"没数据"，不是"没价值"
    dead_available = executed_rate >= 0.10 and bool(rows)
    dead = []
    if dead_available:
        for c in cases:
            if c["id"] in linked_case_ids or c["id"] in protected:
                continue
            if is_enum_case(c):
                continue
            res = c["result"]
            if not res:
                continue                      # 没跑过不进池（不是"死"，是"没验"）
            # 必须真跑过且真通过。NP/NT/BLOCK 一律不进池：
            # 把"还没测"当"测了没事"是死用例分析里最典型的假阳性来源。
            if kinds.get(c["id"]) != "pass":
                continue
            dead.append({"id": c["id"], "module": c["module"], "title": c["title"],
                         "why": "无缺陷关联，执行全通过"})

    gap_dist = {}
    for r in escaped:
        gap_dist[r["gap_type"]] = gap_dist.get(r["gap_type"], 0) + 1

    return {
        "layer": 2,
        "total": len(rows), "evaluable": len(evaluable),
        "undecidable": len(undec),
        "undecidable_rate": round(len(undec) / (len(rows) or 1), 4),
        "prevented": len(prevented), "suspected": len(suspected), "escaped": len(escaped),
        "escape_rate": round(len(escaped) / ne, 4),
        "escape_hi": round((len(escaped) + len(suspected)) / ne, 4),
        "suspected_rate": round(len(suspected) / ne, 4),
        "prevent_rate": round(len(prevented) / ne, 4),
        "prevented_mode": prevented_mode,
        "ddf_global": round(len(linked_case_ids) / (len(cases) or 1), 4),
        "by_module": by_mod, "bug_by_module": bug_mod,
        "rows": rows,
        "gap_dist": gap_dist,
        "dead_case_candidates": dead,
        "dead_available": dead_available,
        "executed_rate": executed_rate,
        "executed": len(executed),
        "pending_np": len(pending),
        "blocked": len(blocked),
        "pending_case_ids": [c["id"] for c in pending],
        "total_cases": len(cases),
        "linked_cases": len(linked_case_ids),
    }


# ---------------------------------------------------------------- 报告

def _pct(x):
    return "—" if x is None else f"{x*100:.1f}%"


def render_markdown(res, bugs_path, cases_path, layer, with_suspected=False):
    L = []
    a = L.append
    a("# 缺陷反哺审计报告")
    a("")
    a(f"- 生成时间：{res['generated_at']}")
    a(f"- 缺陷来源：`{bugs_path}`")
    if cases_path:
        a(f"- 用例库：`{cases_path}`")
    a(f"- 审计层级：层 {layer}")
    a("")
    a("> 本报告**不阻断**任何流程（`--gate off`）。口径："
      "`prevented` 只认 expected 命中强判别要素，不看标题、不看 steps。")
    a("")
    if res.get("no_data"):
        a("> **本次无缺陷数据**：缺陷文件解析为 0 条。下面的表都是空壳，"
          "Step 6.5 应整步跳过（新项目未上线时属正常情况），不影响任何既有闸门。")
        a("")

    l1 = res["layer1"]
    a("## 一、数据体检（先看这段，否则后面的数都是假的）")
    a("")
    p = l1["probe"]
    a("| 项 | 值 |")
    a("|---|---|")
    a(f"| 缺陷总数 | {l1['total']} |")
    a(f"| 有效缺陷（剔除驳回/有意设计） | {l1['valid']} |")
    a(f"| 无效缺陷 | {l1['invalid']} |")
    a(f"| 发现阶段字段填充率 | {_pct(p['phase_filled_rate'])}（最佳字段 `{p['phase_field_best'] or '无'}`）|")
    a(f"| 测试阶段发现 / 线上发现 | {p['phase_test']} / {p['phase_online']} |")
    a(f"| **DER 可算性** | **{'可算' if p['der_available'] else '不可算'}** |")
    a("")
    a(f"> {p['der_reason']}")
    a("")
    if l1["invalid"]:
        a("**无效缺陷（不进分母）**")
        a("")
        for x in l1["invalid_detail"][:20]:
            a(f"- `{x['id']}` [{x['reason']}] {x['title']}")
        if l1["invalid"] > 20:
            a(f"- …… 另 {l1['invalid']-20} 条")
        a("")

    a("## 二、全局指标")
    a("")
    a("| 指标 | 值 | 读法 |")
    a("|---|---|---|")
    if l1["der"] is not None:
        a(f"| 缺陷拦截率 DER | {_pct(l1['der'])} | 越高越好（测试拦住的占比） |")
        a(f"| 缺陷泄漏率 DLR | {_pct(l1['dlr'])} | 越低越好（= 1 − DER） |")
    else:
        a("| 缺陷拦截率 DER | **不可算** | 缺发现阶段字段或线上样本，见第一节 |")
    a(f"| 回归缺陷率 | {_pct(l1['regression_rate'])} | 改好又坏的比例——「验证不足」的硬信号 |")
    a(f"| 缺陷重开率 | {_pct(l1['reopen_rate'])} | 关单后又被重开 |")
    if layer >= 2:
        a(f"| 用例缺陷发现力 DDF | {_pct(res['layer2']['ddf_global'])} "
          f"（{res['layer2']['linked_cases']}/{res['layer2']['total_cases']}）| 越高越好 |")
        a(f"| 缺陷逃逸率（可靠口径）| {_pct(res['layer2']['escape_rate'])} "
          f"（{res['layer2']['escaped']}/{res['layer2']['evaluable']}）| 越低越好 |")
        a(f"| 真实逃逸率区间 | {_pct(res['layer2']['escape_rate'])} ~ "
          f"{_pct(res['layer2']['escape_hi'])} | 下界=已确认拦住的不算漏；上界=疑似也当漏 |")
        a(f"| 疑似已拦（待人工确认）| {res['layer2']['suspected']} 条 "
          f"（{_pct(res['layer2']['suspected_rate'])}）| **不计入已拦**，见 4.2 |")
        a(f"| 不可判定率 | {_pct(res['layer2']['undecidable_rate'])} | 缺陷单质量的反向指标 |")
    a("")
    if l1["regression_ids"]:
        a(f"**回归缺陷 ID**（{len(l1['regression_ids'])} 条）："
          + "、".join(f"`{i}`" for i in l1["regression_ids"][:30]))
        a("")
    if l1["reopen_ids"]:
        a(f"**重开缺陷 ID**（{len(l1['reopen_ids'])} 条）："
          + "、".join(f"`{i}`" for i in l1["reopen_ids"][:30]))
        a("")

    a("## 三、模块分布")
    a("")
    a("| 模块 | 缺陷数 | 致命/严重 | 回归缺陷 | 回归缺陷率 |")
    a("|---|---|---|---|---|")
    for m, d in l1["by_module"].items():
        a(f"| {m} | {d['bugs']} | {d['fatal']} | {d['regression']} | {_pct(d['regression_rate'])} |")
    a("")
    if layer >= 2 and res["layer2"]["bug_by_module"]:
        a("| 模块 | 可判缺陷 | 已拦 | 疑似 | 逃逸 | 逃逸率 | 区间上界 | 关联用例 | DDF |")
        a("|---|---|---|---|---|---|---|---|---|")
        l2 = res["layer2"]
        for m, d in sorted(l2["bug_by_module"].items(), key=lambda x: -x[1]["bugs"]):
            cm = l2["by_module"].get(m, {"cases": 0, "linked": 0, "ddf": 0})
            a(f"| {m} | {d['bugs']} | {d['prevented']} | {d['suspected']} | {d['escaped']} | "
              f"{_pct(d['escape_rate'])} | {_pct(d.get('escape_hi'))} | "
              f"{cm['linked']}/{cm['cases']} | {_pct(cm['ddf'])} |")
        a("")

    if layer >= 2:
        l2 = res["layer2"]
        a("## 四、四态明细（层 2）")
        a("")
        a(f"- 已拦 `prevented`：**{l2['prevented']}** 条"
          + ("（**仅 `--prevented-mode auto` 下才可能 > 0**）" if l2["prevented"] == 0 else ""))
        a(f"- 疑似已拦 `suspected`：**{l2['suspected']}** 条"
          + ("（实测人工确认率 0/5，**默认不出清单**，需要时加 `--with-suspected`）"
             if not with_suspected else "（需人工确认，见 4.2）"))
        a(f"- 逃逸 `escaped`：**{l2['escaped']}** 条（可靠：缺陷发生了且没有可拦截的断言）")
        a(f"- 不可判定 `undecidable`：**{l2['undecidable']}** 条（无效缺陷 / 信息不足）")
        a("")
        esc = [r for r in l2["rows"] if r["verdict"] == "escaped"]
        if esc:
            a("### 4.1 逃逸缺陷（按缺口类型分组，就是回填清单）")
            a("")
            for gt, n in sorted(l2["gap_dist"].items(), key=lambda x: -x[1]):
                a(f"#### {gt}（{n} 条）—— {GAP_DESC.get(gt, '')}")
                a("")
                for r in [x for x in esc if x["gap_type"] == gt][:15]:
                    a(f"- `{r['id']}` [{r['module'] or '未分模块'}] {r['title']}")
                    a(f"  - 原因：{r['reason']}")
                    if r["matched_cases"]:
                        a(f"  - 关联用例：{', '.join(r['matched_cases'])}")
                more = len([x for x in esc if x["gap_type"] == gt]) - 15
                if more > 0:
                    a(f"- …… 另 {more} 条")
                a("")
        prev = [r for r in l2["rows"] if r["verdict"] == "prevented"]
        susp = [r for r in l2["rows"] if r["verdict"] == "suspected"]
        if with_suspected and (prev or susp):
            a("### 4.2 疑似已拦（**人工逐条确认清单，未确认前不得计入拦截率**）")
            a("")
            a("> 判定方式：缺陷标题里的判别要素，在某条关联用例 `expected` 的**同一分句**里出现过。")
            a("> 实测：抽检 5 条 suspected（及更早 8 条）成立 0 条 —— 命中「同一动作词」"
              "不等于验的是同一件事（例：「训练完成后弹出错误弹窗」被「跳转至完成界面」判命中）。"
              "**逐条看「命中分句」那一列**，不成立就划到 4.1 回填。")
            a("")
            a("| # | 缺陷 | 命中用例 | 要素 | 命中分句（判定依据） |")
            a("|---|---|---|---|---|")
            for i, r in enumerate(prev + susp, 1):
                k = r["killed_by"][0] if r["killed_by"] else ("", "", "", "")
                a(f"| {i} | {r['title'][:34]} | {k[0]} | {k[1]}:{k[2]} | "
                  f"{k[3] if len(k) > 3 else ''} |")
            a("")
        dead = l2["dead_case_candidates"]

        # 阶段内待执行（NP）：本阶段应测未测 —— 是进度缺口，既不是失败也不是漏测
        n_pending = l2.get("pending_np", 0)
        if n_pending:
            a(f"### 4.3 阶段内待执行（NP）：**{n_pending} 条**")
            a("")
            a("> `NP` = 当前阶段需要测试、但尚未执行。它**不是失败，也不是漏测**，"
              "而是**进度缺口**——这批复测完成前，相关需求的结论不能算已验证。"
              "统计口径上它不计入「已执行率」，也不进缺陷逃逸清单。")
            a("")
            if l2.get("blocked"):
                a(f"> 另有 `BLOCK` 阻塞 {l2['blocked']} 条，原因多为环境/依赖，需单独跟进。")
                a("")
            ids = l2.get("pending_case_ids", [])
            a("用例清单：" + "、".join(ids[:30]) + ("…" if len(ids) > 30 else ""))
            a("")

        if not l2.get("dead_available", True):
            a("### 4.4 死用例候选：**本次不生成**（缺执行数据）")
            a("")
            a(f"> 用例库「测试结果」列填充率仅 {_pct(l2.get('executed_rate'))}，"
              "无法区分「从未失败」和「从未跑过」。这种情况下列候选池会把整库判死，"
              "所以本脚本直接不出（宁缺勿滥）。")
            a(">")
            a("> 解锁条件：任一迭代真实执行过一批用例后重跑；"
              "或用 `--protected` 传入变异审计的 killer 名单做交叉保护后再人工判断。")
            a("")
        else:
            a(f"### 4.4 死用例候选（{len(dead)} 条，只列不删）")
            a("")
            a(f"> 判据：未关联任何缺陷 + 有执行记录且全通过 + 非范围性 + 不在变异保护名单。"
              f"（执行数据填充率 {_pct(l2.get('executed_rate'))}）")
            a("> **必须**拿 `mutation_audit.py` 的 killer 名单过一遍再决定退役，否则会误杀。")
            a("")
            bym = {}
            for d in dead:
                bym.setdefault(d["module"] or "未分模块", []).append(d)
            for m, ds in sorted(bym.items(), key=lambda x: -len(x[1])):
                a(f"- **{m}**：{len(ds)} 条（{', '.join(d['id'] for d in ds[:12])}"
                  + ("……" if len(ds) > 12 else "") + "）")
            a("")

    if layer >= 3 and res.get("layer2"):
        esc3 = [r for r in res["layer2"]["rows"] if r["verdict"] == "escaped"]
        a(f"## 四之二、回填草案（层 3：{len(esc3)} 条逃逸缺陷 → 回归候选）")
        a("")
        a("> 只回答「往哪条用例的 expected 里补什么断言」，**不自动改用例库**。"
          "完整草案（含建议标题）见 `--emit-backfill` 输出的 JSON，交 Step 5 逐条生成。")
        a("")
        a("| # | 缺陷 | 模块 | 缺口 | 补什么 | 挂到哪条用例 |")
        a("|---|---|---|---|---|---|")
        for i, r in enumerate(esc3[:40], 1):
            a(f"| {i} | {r['title'][:30]} | {r['module'] or '未分模块'} | {r['gap_type']} | "
              f"{GAP_DESC.get(r['gap_type'], '')} | "
              f"{', '.join(r['matched_cases'][:2]) or '—（库内无用例，需新建）'} |")
        if len(esc3) > 40:
            a(f"| … | 另 {len(esc3) - 40} 条见 JSON | | | | |")
        a("")

    a("## 五、结论与下一步")
    a("")
    if l1["der"] is None:
        a(f"1. **DER 本次不可算**：{l1['probe']['der_reason']}。"
          "不要用「本项目零线上缺陷」倒推出 100% 拦截率——那是自嗨。")
        a("2. 先补数据：TAPD 缺陷单补「发现阶段/来源」字段，或按 `version_report` + 发布时间分区统计。")
    else:
        a(f"1. 缺陷拦截率 DER = {_pct(l1['der'])}（全局）。模块级见第三节，低于 "
          f"{_pct(0.6)} 的模块优先复盘。")
    a(f"{'(3' if l1['der'] is None else '(2'}. 回归缺陷率 {_pct(l1['regression_rate'])}"
      "：这些「改好又坏」的缺陷，说明上一次的验证没有覆盖全，可直接作为回归用例的选题。"
      if l1["regression_ids"] else
      "2. 无回归缺陷，说明修复验证质量尚可（或缺陷单未记 regression_number）。")
    if layer >= 2:
        a("3. 逃逸缺陷按第四节 4.1 的缺口类型回填：**补断言优先于补用例**，"
          "先看能不能在已有用例的 expected 里加数值/结果态/逐字文案。")
        a("4. 死用例候选只列不删，退役前必须与变异审计的保护名单交叉。")
    a("")
    return "\n".join(L)


def render_json(res):
    def slim(r):
        return {k: v for k, v in r.items() if k not in ("desc",)}
    out = {
        "generated_at": res["generated_at"],
        "layer": res["layer"],
        "layer1": {k: v for k, v in res["layer1"].items() if k != "invalid_detail"},
        "invalid": res["layer1"]["invalid_detail"],
    }
    if res["layer"] >= 2:
        l2 = res["layer2"]
        out["metrics"] = {
            "der": res["layer1"]["der"],
            "dlr": res["layer1"]["dlr"],
            "ddf_global": l2["ddf_global"],
            "escape_rate": l2["escape_rate"],
            "escape_hi": l2["escape_hi"],
            "suspected": l2["suspected"],
            "prevented": l2["prevented"],
            "prevented_mode": l2["prevented_mode"],
            "undecidable_rate": l2["undecidable_rate"],
            "regression_rate": res["layer1"]["regression_rate"],
        }
        out["by_module"] = l2["by_module"]
        out["bug_by_module"] = l2["bug_by_module"]
        out["bugs"] = [slim(r) for r in l2["rows"]]
        out["dead_case_candidates"] = [d["id"] for d in l2["dead_case_candidates"]]
        out["gap_dist"] = l2["gap_dist"]
    return json.dumps(out, ensure_ascii=False, indent=2)


def render_backfill(res):
    l2 = res["layer2"]
    items = []
    for r in l2["rows"]:
        if r["verdict"] != "escaped":
            continue
        items.append({
            "bug_id": r["id"], "title": r["title"], "module": r["module"],
            "gap_type": r["gap_type"],
            "advice": GAP_DESC.get(r["gap_type"], ""),
            "existing_cases": r["matched_cases"],
            "suggest_case": {
                "module": r["module"], "priority": "P1",
                "precondition": f"已复现缺陷 {r['id']} 的前置状态",
                "steps": "按缺陷复现路径执行一遍",
                "expected": "应" + ("给出具体数值/清单" if r["gap_type"] == "NUM"
                                    else "输出逐字文案" if r["gap_type"] == "TXT"
                                    else "给出结果态证据" if r["gap_type"] == "ACT"
                                    else "满足唯一性/计数要求" if r["gap_type"] == "UNIQ"
                                    else "明确不出现/不再发生" if r["gap_type"] == "NEG"
                                    else "边界两侧结果不同" if r["gap_type"] == "BND"
                                    else "描述清楚错误现象"),
                "coverage_rule": "",
            },
        })
    return json.dumps({"generated_at": res["generated_at"], "count": len(items),
                       "items": items}, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------- CLI

def main():
    ap = argparse.ArgumentParser(
        description="缺陷反哺审计：缺陷单（× 用例库）→ 拦截率 / 三态判定 / 缺口回填（不阻断）")
    ap.add_argument("bugs", help="缺陷文件（.json TAPD dump / .xlsx / .csv）")
    ap.add_argument("cases", nargs="?", help="用例库（.xlsx / .json），层 2 起必填")
    ap.add_argument("-o", "--out", help="报告输出路径（默认打印到 stdout）")
    ap.add_argument("--format", choices=["markdown", "json"], default="markdown")
    ap.add_argument("--layer", type=int, choices=[1, 2, 3], default=1,
                    help="审计层级：1 只算指标 / 2 加归属与三态 / 3 加回填草案（默认 1）")
    ap.add_argument("--gate", choices=["off", "warn"], default="off",
                    help="闸门：off 恒放行（默认）/ warn 逃逸率超线只告警")
    ap.add_argument("--escaped-warn", type=float, default=DEFAULT_ESCAPED_WARN,
                    help=f"--gate warn 的逃逸率告警线（默认 {DEFAULT_ESCAPED_WARN}）")
    ap.add_argument("--module-map", metavar="PATH",
                    help='模块归一副本 JSON：{"缺陷模块": "用例模块"}')
    ap.add_argument("--l2-min-keywords", type=int, default=DEFAULT_L2_MIN_KW,
                    help=f"L2 关键词命中最少个数（默认 {DEFAULT_L2_MIN_KW}）")
    ap.add_argument("--l3-threshold", type=float, default=DEFAULT_L3_THRESHOLD,
                    help=f"L3 相似度阈值，0 关闭（默认 {DEFAULT_L3_THRESHOLD}）")
    ap.add_argument("--protected", metavar="PATH",
                    help="变异审计保护名单 JSON（killer 用例 id 数组），死用例候选会跳过它们")
    ap.add_argument("--prevented-mode", choices=["off", "auto"], default="off",
                    help="off=强要素命中只判「疑似」，需人工确认（默认，实测一致率仅 25%%）；"
                         "auto=直接判「已拦」（会虚高，慎用）")
    ap.add_argument("--with-suspected", action="store_true",
                    help="在报告里输出「疑似已拦截」清单（默认不输出：实测确认率 0/5，噪声为主）")
    ap.add_argument("--emit-map", metavar="PATH", help="输出 defect_map.json")
    ap.add_argument("--emit-backfill", metavar="PATH", help="输出 regression_backfill.json")
    args = ap.parse_args()

    if args.layer >= 2 and not args.cases:
        print("[错误] --layer 2/3 需要用例库路径", file=sys.stderr)
        return 2

    try:
        bugs_raw = dedupe_bugs(load_bugs(args.bugs))
    except Exception as e:
        print(f"[错误] 读取缺陷失败: {e}", file=sys.stderr)
        return 2
    if not bugs_raw:
        print("[提示] 缺陷文件里没有可用记录 —— 输出「无数据」报告并放行（不阻断）",
              file=sys.stderr)

    module_map = None
    if args.module_map:
        try:
            with open(args.module_map, encoding="utf-8") as f:
                module_map = json.load(f)
        except Exception as e:
            print(f"[错误] 读取模块归一副本失败: {e}", file=sys.stderr)
            return 2

    bugs = [normalize_bug(b, module_map) for b in bugs_raw]
    res = {"generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
           "layer": args.layer, "no_data": not bugs,
           "layer1": compute_layer1(bugs)}

    if args.layer >= 2:
        try:
            cases = load_cases(args.cases)
        except Exception as e:
            print(f"[错误] 读取用例库失败: {e}", file=sys.stderr)
            return 2
        if not cases:
            print("[错误] 未解析到任何用例", file=sys.stderr)
            return 2
        protected = []
        if args.protected:
            try:
                with open(args.protected, encoding="utf-8") as f:
                    pj = json.load(f)
                protected = pj if isinstance(pj, list) else pj.get("killer_case_ids", [])
            except Exception as e:
                print(f"[错误] 读取保护名单失败: {e}", file=sys.stderr)
                return 2
        res["layer2"] = compute_layer2(bugs, cases, args.l2_min_keywords,
                                       args.l3_threshold, protected, args.prevented_mode)

    text = render_json(res) if args.format == "json" else \
        render_markdown(res, args.bugs, args.cases, args.layer, args.with_suspected)

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text + "\n")
        print(f"[✓] 报告已写入 {args.out}")
    else:
        print(text)

    if args.layer >= 2 and args.emit_map:
        with open(args.emit_map, "w", encoding="utf-8") as f:
            f.write(render_json(res) + "\n")
        print(f"[✓] 映射已写入 {args.emit_map}")
    if args.layer >= 2 and args.emit_backfill:
        with open(args.emit_backfill, "w", encoding="utf-8") as f:
            f.write(render_backfill(res) + "\n")
        print(f"[✓] 回填草案已写入 {args.emit_backfill}")

    l1 = res["layer1"]
    p = l1["probe"]
    print(f"    缺陷 {l1['total']} 条（有效 {l1['valid']}），DER "
          f"{'不可算（' + p['der_reason'] + '）' if l1['der'] is None else _pct(l1['der'])}，"
          f"回归缺陷率 {_pct(l1['regression_rate'])}", file=sys.stderr)
    if args.layer >= 2:
        l2 = res["layer2"]
        print(f"    已拦 {l2['prevented']} / 逃逸 {l2['escaped']} / 不可判 {l2['undecidable']}，"
              f"DDF {_pct(l2['ddf_global'])}，死用例候选 {len(l2['dead_case_candidates'])} 条",
              file=sys.stderr)

    if args.gate == "warn" and args.layer >= 2:
        if res["layer2"]["escape_rate"] > args.escaped_warn:
            print(f"[警告] 缺陷逃逸率 {_pct(res['layer2']['escape_rate'])} 高于 "
                  f"{_pct(args.escaped_warn)}（warn 模式不阻断）", file=sys.stderr)
    return 0


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
        print("\n[内部错误] defect_audit.py 自身崩溃（exit 3），不是数据不达标。", file=sys.stderr)
        print("请把下面的堆栈连同输入样例一起报给技能维护者：", file=sys.stderr)
        traceback.print_exc()
        sys.exit(3)
