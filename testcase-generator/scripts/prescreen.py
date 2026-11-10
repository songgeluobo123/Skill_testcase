#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
prescreen.py — 测试用例质量预审器（正式生成前的 14 项闸门）

检查项（详见 references/quality_prescreen.md）：
  1. 需求覆盖率 >= coverage_min（需 --requirement-rules 提供需求规则清单）
  2. P0 占比（最高优先级）在 [p0_min, p0_max]（默认 0.10~0.25，安全攸关软件上调）
  3. P2 占比在 [p2_min, p2_max]（默认 0.25~0.40）
  4. 每条用例关联至少 1 种测试设计方法（design_method 非空且合法，6 方法之一或多）
  5. 无凭空编造（coverage_rule 必须落在需求规则清单内）
  6. 无语义重复（同 module+steps+expected 去重）
  7. 预期结果可判定（无"合理/美观/流畅"类不可判定词；缺断言标志仅告警）
  8. 标题规范与残缺检查（≤ --title-max 字，默认 30 / 无编号前缀 / 无【】 / 无句末标点 / 无占位残留；
     缺标题或缺步骤即阻断；重名标题仅告警；用例编号重复即阻断）
  9. 场景构成配额（每功能点 1 正向 : ≥3 异常·边界·权限；模块内无异常/边界即阻断，
     负向偏少或缺权限校验仅告警）
  10. 孤儿用例（无 coverage_rule 且未标 exploratory=true）：默认**直接阻断**；
      可用 --orphan-max 放宽为阈值告警（如 0.1 允许 10%）

  —— 以下 4 项为"密度与深度"闸门（默认 warn，灰度后切 block）——

  11. 需求密度（M1）：每条需求用例数 >= --min-cases-per-rule（默认 0=关闭，建议 6）。
      按 coverage_rule **显式回指**计数，不做文本猜测；--density-exempt 可豁免简单需求
  12. 方法一致性（M2）：design_method 声称的方法必须有落地证据，否则判**方法虚标**。
      边界值分析→须含比较/极值词或 0·100 边界字面量 且含数字；
      等价类划分→test_data 须≥2 取值或含类归属词（仅 1 取值记"欠展开"，不算虚标）；
      判定表法/正交分析法→步骤须含≥2 个条件维度
  13. 需求级场景配额（M6）：每条**需求**至少 1 条异常/边界用例（模块级第 9 项的向下钻取，
      防"大模块掩盖小需求"）
  14. 范围性用例（M4 兜底）：步骤含 逐一/依次/分别/遍历… 且并列 ≥--range-min-objs 个对象、
      但预期只有 1 条断言 → 判"一条用例吃掉 N 个场景"。第 9/11/13 项都只数条数，
      数不出"4 条覆盖 16 个场景"，本项补上这个缺口。备注列已展开的降级为弱提示。

退出码：
  0  —— 全部通过（或仅警告）
  1  —— 存在不达标项（需修正后重跑）
  2  —— 输入/参数错误
  3  —— 内部错误（脚本自身崩溃；**与 1 严格区分**，见下）

> 为什么必须有 3：早期所有非 0 都返回 1，脚本崩溃（如 steps 传数组抛 TypeError）会被
> 误读成"用例质量不达标"，让人对着不存在的质量问题返工。崩溃必须可区分。

用法：
  python prescreen.py cases.json --requirement-rules requirements.json
  python prescreen.py cases.json --p0-min 0.40 --p0-max 0.60
  python prescreen.py cases.json            # 仅结构闸门（第 1 项覆盖率需清单，自动跳过）
  # 密度与深度闸门（Step 5 模板：全部显式 block）
  python prescreen.py cases.json --requirement-rules requirements.json \
         --min-cases-per-rule 6 --density-mode block --method-check block \
         --scene-rule-mode block --range-mode block

优先级采用 P0-P3（P0 最高，一票否决）；全技能统一，无 P4。
可判定性、标题检查、场景配额的依据见 references/excellent_case_patterns.md
与 references/testpoint_checklist.md 第二节。
密度与方法一致性的口径见 references/quality_prescreen.md 第 11/12/13 项。
"""

import argparse
import json
import re
import sys

DESIGN_METHODS = {"等价类划分", "边界值分析", "场景法", "状态迁移法", "判定表法", "正交分析法", "错误推测"}
PRIORITIES = {"P0", "P1", "P2", "P3"}

# 检查 7：不可判定词（见到即改，见 excellent_case_patterns.md 三、反面清单）
UNJUDGEABLE_WORDS = [
    "合理", "美观", "友好", "流畅", "良好", "正常显示", "显示正常", "工整", "整齐",
    "尽量", "适当", "无异常", "不卡顿", "体验好", "清晰明了", "符合预期", "正确无误",
]
# 检查 7：可判定标志（应/必须/需/数值/阈值/逐字文案/清单编号）
ASSERT_MARKERS = re.compile(r"应|必须|需|为[:：]|=\s*\d|>\s*\d|<\s*\d|\d|1[.、]|提示|显示为|保持")
# 检查 8：标题占位残留
TITLE_PLACEHOLDER = re.compile(r"待.{0,6}更新|TBD|TODO|XXX+|xxxx|【】|\[\]", re.IGNORECASE)

# 检查 9：场景构成配额（正向 : 异常·边界·权限），口径见 testpoint_checklist.md 第二节
PERM_KEYS = ["权限", "越权", "角色", "未登录", "未授权", "鉴权", "登录态", "白名单", "游客"]
NEG_KEYS = ["异常", "边界", "失败", "错误", "超限", "超时", "为空", "空值", "非法",
            "不支持", "重复", "断网", "弱网", "逆向", "负向", "拒绝", "上限", "下限",
            "最大", "最小", "超出", "超过"]

# 检查 12：方法一致性（M2）——"声称用过某方法"必须有落地证据
# 边界值分析：比较/极值词
BOUNDARY_WORDS = ["大于", "小于", "等于", "≥", "≤", ">", "<", "超过", "低于", "超出",
                  "不低于", "不高于", "上限", "下限", "最大", "最小", "边界", "临界", "阈值"]
# 边界值分析：0/100 这类"值本身就是边界"的字面量（无比较词也成立，如"展示 0%"）
BOUNDARY_LITERAL = re.compile(r"0\s*(?:%|％|km/h|公里|格|档|元|分钟|小时|秒|次)"
                              r"|100\s*(?:%|％)|满电|满格|满量程|满信号")
# 等价类划分：类归属词（含"X值"型表述——用例里更常写"传空值/传非法值"而不是"无效类"）
EQ_CLASS_WORDS = ["有效类", "无效类", "合法", "非法", "边界外", "异常类", "等价类",
                  "取值", "枚举", "类别", "集合",
                  "有效值", "无效值", "合法值", "非法值", "越界值", "空值",
                  "超限值", "正常值", "异常值", "边界值"]
# 判定表法 / 正交分析法：条件维度线索
COND_CUES = ["当", "若", "如果", "条件", "且", "同时", "分别", "组合", "取值", "场景"]
# 判定表法 / 正交分析法：一行内显式并列 ≥3 个取值（如"已添加已连接/已添加未连接/未添加已连接"）
ALT_GROUP_RE = re.compile(r"[^/\n]{1,24}(?:/[^/\n]{1,24}){2,}")
NUMBER_RE = re.compile(r"\d")

# 检查 14：范围性用例（M4 兜底）——一条用例覆盖多个并列场景
# 词表口径与 defect_audit.py 的 ENUM_WORDS 对齐（那边已用于把范围性用例排除出 DDF 排名），
# 另补"全部/所有/每个/各个"这类更强的全域量词。
RANGE_WORDS = ("逐一", "逐个", "依次", "分别", "遍历", "逐项", "逐条",
               "全部", "所有", "每个", "各个")
# 并列对象分隔符：顿号与斜杠是中文用例里最主流的并列写法；
# 不切「和/及/与」——这三个字在中文里高频出现在词内部（"和值""及时""与其"），切了必然误伤。
OBJ_SPLIT_RE = re.compile(r"[、/／]")



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


# 词表可在运行时被 --method-lexicon 增补（**合并，不是替换**——替换会让加词时
# 一不小心丢掉全部内置词，然后闸门静默失效）。
LEXICON = {
    "boundary": list(BOUNDARY_WORDS),
    "boundary_literal": BOUNDARY_LITERAL.pattern,
    "eq_class": list(EQ_CLASS_WORDS),
    "cond": list(COND_CUES),
}


def load_lexicon(path):
    """读取外部词表并合并进 LEXICON；返回增补的词数，供启动时打印。

    格式（每一项都可选，只写要增补的）：
      {"boundary": ["临界值","满量程"], "eq_class": ["档位值"], "cond": ["在…时"],
       "boundary_literal": "正则字符串（替换内置正则）"}
    """
    with open(path, encoding="utf-8") as f:
        ext = json.load(f)
    if not isinstance(ext, dict):
        raise ValueError("--method-lexicon 需为对象：{boundary/eq_class/cond/boundary_literal}")
    added = 0
    for key in ("boundary", "eq_class", "cond"):
        vals = ext.get(key) or []
        if not isinstance(vals, list):
            raise ValueError(f"--method-lexicon 的 {key} 必须是字符串数组")
        for w in vals:
            w = str(w).strip()
            if w and w not in LEXICON[key]:
                LEXICON[key].append(w)
                added += 1
    lit = ext.get("boundary_literal")
    if lit:
        re.compile(lit)                      # 语法错了要在这里就炸，不要等到判用例时
        LEXICON["boundary_literal"] = lit
        added += 1
    return added


def norm(s):
    """归一化用于去重比较。

    契约上 steps/expected 是「1. 2. 3.」换行分隔的字符串（见 output_format.md），
    但模型实际输出数组的比例很高。这里必须同时吃 str 与 list/tuple/set：
    早期版本只处理 str，遇到数组会在第 6 项抛 TypeError ——
    后续第 7~13 项全部不执行，而退出码仍是 1，会被误读成"预审不通过"。
    """
    if isinstance(s, (list, tuple, set)):
        s = "\n".join(str(x) for x in s)
    elif s is None:
        s = ""
    elif not isinstance(s, str):
        s = str(s)
    return re.sub(r"\s+", "", s)


def as_list(v):
    if isinstance(v, str):
        return [v]
    if isinstance(v, (list, tuple, set)):
        return list(v)
    return []


def case_title(c):
    """取用例标题。

    字段契约分裂的历史坑：output_format.md 与 to_excel.py 用 `name`，
    而本脚本早期只读 `title`。结果是**完全按规范写出的用例**会在第 8 项被判
    "标题为空" 而全量阻断。这里统一为「name 优先，title 兜底」，两种都收。
    """
    if not isinstance(c, dict):
        return ""
    for k in ("name", "title"):
        v = c.get(k)
        if isinstance(v, (list, tuple)):
            v = " ".join(str(x) for x in v)
        if v is not None and str(v).strip():
            return str(v).strip()
    return ""


def case_text(c):
    """标题 + 步骤 + 预期 的合并文本（用于负向/权限关键词判定）。"""
    return " ".join([case_title(c), str(c.get("steps", "")),
                     str(c.get("expected", ""))])


def body_text(c):
    """步骤 + 预期（用于方法落地证据）。

    **标题不参与方法证据判定**：标题是标签不是断言，否则"下载完成不等于安装"
    会因标题含"等于"被误判为边界值用例。
    """
    return " ".join([str(c.get("steps", "")), str(c.get("expected", ""))])


def test_data_values(c):
    """test_data 中的所有非空取值（去重；"无"是合法取值，不当噪声过滤）。"""
    td = c.get("test_data")
    vals = []
    if isinstance(td, dict):
        vals = [str(v).strip() for v in td.values()]
    elif isinstance(td, list):
        vals = [str(v).strip() for v in td]
    elif isinstance(td, str):
        vals = [td.strip()]
    return [v for v in vals if v and v not in ("-", "N/A", "NA")]


_BOUNDARY_LIT_RE = None


def boundary_literal_re():
    """按 LEXICON 里的正则在首次使用时编译；词表被 --method-lexicon 改过会重编。"""
    global _BOUNDARY_LIT_RE
    pat = LEXICON["boundary_literal"]
    if _BOUNDARY_LIT_RE is None or _BOUNDARY_LIT_RE.pattern != pat:
        _BOUNDARY_LIT_RE = re.compile(pat)
    return _BOUNDARY_LIT_RE


def boundary_evidence(c):
    """边界值分析的落地证据：返回 (是否含比较/极值词, 是否含 0/100 边界字面量, 是否含数字)。"""
    t = body_text(c)
    return (any(w in t for w in LEXICON["boundary"]),
            bool(boundary_literal_re().search(t)),
            bool(NUMBER_RE.search(t)))


def condition_dims(c):
    """判定表/正交的条件维度数：条件线索句 + 显式并列取值组（≥3 个用 / 并列）。"""
    steps = str(c.get("steps", "") or "")
    segs = [s for s in re.split(r"[\n;；]", steps) if s.strip()]
    dims = sum(1 for s in segs if any(w in s for w in LEXICON["cond"]))
    if ALT_GROUP_RE.search(steps):
        dims += 1
    return dims


def classify_case(c):
    """把单条用例判为 pos/neg，并判定是否属权限校验。口径与第 9 项、第 13 项共用。"""
    tt = str(c.get("test_type", ""))
    text = " ".join([tt, case_title(c), str(c.get("steps", ""))])
    is_perm = any(k in text for k in PERM_KEYS)
    if "异常" in tt or "边界" in tt or "权限" in tt:
        kind = "neg"
    elif "功能" in tt or "正向" in tt or "正常" in tt:
        kind = "pos"
    elif any(k in text for k in NEG_KEYS):
        kind = "neg"
    else:
        kind = "pos"
    return kind, is_perm


def _lines(v):
    """把 steps / expected 统一成非空行列表（兼容字符串与数组两种写法）。"""
    if isinstance(v, (list, tuple)):
        return [str(x) for x in v if str(x).strip()]
    return [x for x in str(v or "").split("\n") if x.strip()]


def range_evidence(c):
    """第 14 项：判定"范围性用例"——一条用例覆盖多个并列场景。

    返回 (是否命中, 并列对象数, 预期断言条数, 命中的范围词列表)。

    **只看 steps**：预期里出现"逐一显示 3 项"是合法表述，不能当证据。
    这与第 12 项「标题不作证据」是同一条原则——证据必须落在实际执行动作上。

    并列对象数只按顿号/斜杠切分。切「和/及/与」会误伤（"和值""及时""与其"），
    宁可少报也不要把正常用例判成范围性用例。
    """
    objs, hit_words = 0, []
    for ln in _lines(c.get("steps")):
        ws = [w for w in RANGE_WORDS if w in ln]
        if not ws:
            continue
        hit_words.extend(ws)
        segs = [p for p in OBJ_SPLIT_RE.split(ln) if len(p.strip()) >= 2]
        objs = max(objs, len(segs))
    if not hit_words or objs < 2:
        return False, objs, 0, []
    return True, objs, len(_lines(c.get("expected"))), sorted(set(hit_words))


def main():
    ap = argparse.ArgumentParser(description="测试用例质量预审器（14 项闸门）")
    ap.add_argument("input", help="用例 JSON 文件路径")
    ap.add_argument("--requirement-rules", help="需求规则清单 JSON（字符串数组）")
    ap.add_argument("--coverage-min", type=float, default=0.95)
    ap.add_argument("--p0-min", type=float, default=0.10)
    ap.add_argument("--p0-max", type=float, default=0.25,
                    help="P0 占比上限（默认 0.25）。依据：真库 1669 条已执行用例实测 21.2%%，"
                         "原默认 0.15 会把整库判失败——理论值不该压过团队实际分级习惯")
    ap.add_argument("--p2-min", type=float, default=0.25,
                    help="P2 占比下限（默认 0.25）。依据：真库实测 30.9%%，原默认 0.35 会误判")
    ap.add_argument("--p2-max", type=float, default=0.40)
    ap.add_argument("--ratio-tolerance", type=float, default=0.5,
                    help="整数粒度补偿容差（单位：条，默认 0.5）。仅当占比区间在"
                         "该总条数下不存在任何整数解时才生效；设 0 关闭补偿"
                         "（5/6/11/12/13 条库的 P0 10%%~15%% 将永远无法通过）")
    ap.add_argument("--scene-min-cases", type=int, default=4,
                    help="模块场景构成检查的最小用例数门槛（默认 4，少于该数不判负向缺失）")
    ap.add_argument("--orphan-max", type=float, default=0.0,
                    help="孤儿用例占比上限（默认 0.0：任何孤儿用例即阻断；0.1 表示允许 10%%）")
    ap.add_argument("--title-max", type=int, default=30,
                    help="第 8 项：用例标题长度上限（默认 30 字。收紧口径的项目可传 20）")
    # --- 密度与深度闸门（第 11/12/13 项）---
    ap.add_argument("--min-cases-per-rule", type=int, default=0,
                    help="第11项：每条需求的用例数下限（默认 0=关闭；普通项目 4，复杂项目 6）")
    ap.add_argument("--density-mode", choices=["off", "warn", "block"], default="warn",
                    help="第11项执行强度（默认 warn；--min-cases-per-rule 为 0 时本项不生效）")
    ap.add_argument("--density-exempt", default="",
                    help="第11项豁免的需求 ID，逗号分隔，如 R-002,R-039（单字段型/待澄清需求）")
    ap.add_argument("--method-check", choices=["off", "warn", "block"], default="warn",
                    help="第12项设计方法一致性校验强度（默认 warn）")
    ap.add_argument("--scene-rule-mode", choices=["off", "warn", "block"], default="warn",
                    help="第13项需求级场景配额强度（默认 warn）")
    ap.add_argument("--min-neg-per-rule", type=int, default=3,
                    help="第13项：每条需求至少有 1 条负向即不阻断；少于该数（默认 3）仅告警")
    ap.add_argument("--method-lexicon",
                    help="第12项方法一致性词表 JSON（与内置词表**合并**，只写要增补的词）。"
                         "格式：{\"boundary\":[...],\"eq_class\":[...],\"cond\":[...],"
                         "\"boundary_literal\":\"正则\"}。中文表达千变万化，固定词表必然漏判，"
                         "项目侧可按领域术语补充")
    ap.add_argument("--range-mode", choices=["off", "warn", "block"], default="warn",
                    help="第14项范围性用例校验强度（默认 warn）。"
                         "Step 5 命令模板里硬写 block——这是目前唯一没有兜底的敞口")
    ap.add_argument("--range-min-objs", type=int, default=3,
                    help="第14项：并列对象数达到该值且预期仅 1 条断言，判范围性用例（默认 3）")
    ap.add_argument("--range-weak-mode", choices=["off", "warn"], default="warn",
                    help="第14项弱证据（有范围词但对象数不足）是否告警（默认 warn）")
    args = ap.parse_args()

    exempt_rules = {x.strip() for x in args.density_exempt.split(",") if x.strip()}

    if args.method_lexicon:
        try:
            added = load_lexicon(args.method_lexicon)
        except Exception as e:
            print(f"[错误] 读取/解析方法词表失败: {e}", file=sys.stderr)
            return 2
        print(f"[i] 方法词表已合并：+{added} 条（boundary {len(LEXICON['boundary'])} / "
              f"eq_class {len(LEXICON['eq_class'])} / cond {len(LEXICON['cond'])}）")

    try:
        cases = load_cases(args.input)
    except Exception as e:
        print(f"[错误] 读取/解析输入失败: {e}", file=sys.stderr)
        return 2
    if not cases:
        print("[错误] 未找到任何用例", file=sys.stderr)
        return 2

    fails = []
    warns = []
    skipped = []   # 因"本库没有这个字段"而整项跳过的闸门，必须在汇总里显式列出
    total = len(cases)

    # 1. 需求覆盖率（按规则 ID 匹配，支持 requirements.json 字符串列表）
    rule_ids = set()
    rule_meta = {}
    if args.requirement_rules:
        try:
            with open(args.requirement_rules, encoding="utf-8") as f:
                raw_rules = json.load(f)
        except Exception as e:
            print(f"[错误] 读取需求规则清单失败: {e}", file=sys.stderr)
            return 2
        if isinstance(raw_rules, dict) and "rules" in raw_rules:
            raw_rules = raw_rules["rules"]

        def rid_of(x):
            if isinstance(x, dict):
                return str(x.get("id", "")).strip()
            m = re.search(r"R-\d+", str(x))
            return m.group(0) if m else ""

        rule_ids = {rid_of(x) for x in raw_rules if rid_of(x)}
        for x in raw_rules:
            rid = rid_of(x)
            if rid:
                rule_meta[rid] = (str(x.get("name", "") or x.get("text", "") or "").strip()
                                  if isinstance(x, dict) else str(x))
        covered_ids = set()
        for c in cases:
            for tok in str(c.get("coverage_rule", "")).split(";"):
                tok = tok.strip()
                if re.fullmatch(r"R-\d+", tok) and tok in rule_ids:
                    covered_ids.add(tok)
        ratio = len(covered_ids) / len(rule_ids) if rule_ids else 0
        if ratio < args.coverage_min:
            fails.append(f"需求覆盖率 {ratio:.0%} < 阈值 {args.coverage_min:.0%}（已覆盖 {len(covered_ids)}/{len(rule_ids)}）")
        else:
            print(f"[✓] 需求覆盖率 {ratio:.0%}（{len(covered_ids)}/{len(rule_ids)}）")
    else:
        linked = sum(1 for c in cases if (c.get("coverage_rule") or "").strip())
        print(f"[!] 未提供需求规则清单，跳过真实覆盖率计算；用例规则关联率 {linked/total:.0%}（仅供参考）")
        warns.append("未提供 --requirement-rules，覆盖率检查跳过")

    # 2/3. 优先级占比
    cnt = {p: sum(1 for c in cases if norm_priority(c.get("priority")) == p)
           for p in PRIORITIES}
    p0r = cnt["P0"] / total
    p2r = cnt["P2"] / total
    for label, key, ratio, lo, hi in (
            ("P0", "P0", p0r, args.p0_min, args.p0_max),
            ("P2", "P2", p2r, args.p2_min, args.p2_max)):
        if lo <= ratio <= hi:
            print(f"[✓] {label} 占比 {ratio:.0%}（{cnt[key]} 条）")
            continue
        # 整数粒度补偿：条数是整数，占比区间未必有整数解。
        # 例：12 条库 P0 要 10%~15% → k/12 只有 8.3%(k=1) 与 16.7%(k=2)，两端口都出界，
        # 无论怎么排优先级都过不了 —— 这是闸门的错，不是用例的错。
        has_int_solution = any(lo <= i / total <= hi for i in range(0, total + 1))
        if not has_int_solution:
            tol = args.ratio_tolerance / total      # 容差按「条」折算成占比
            if (lo - tol) <= ratio <= (hi + tol):
                print(f"[✓] {label} 占比 {ratio:.0%}（{cnt[key]} 条）"
                      f"｜整数粒度补偿：{total} 条库无法落在 {lo:.0%}~{hi:.0%}")
                warns.append(f"{label} 占比按整数粒度补偿放行（{total} 条库该区间无整数解）")
                continue
        fails.append(f"{label} 占比 {ratio:.0%} 不在 [{lo:.0%},{hi:.0%}]（当前 {cnt[key]} 条）")

    # 4. 设计方法关联
    # 字段整体缺失 ≠ 字段填错。真实项目库常根本没有「设计方法」列（15 列里没这一项），
    # 此时逐条判"未关联合法方法"会得到 100% 失败——不是用例有问题，是这份库的字段形态不同。
    # 判据：全部用例该字段都为空 → 整项跳过；只要有任意一条填了，就按"填错的那些"判。
    def _dm_of(c):
        dm = c.get("design_method")
        if isinstance(dm, str):
            dm = [dm]
        return [x for x in (dm or []) if str(x).strip()]

    if not any(_dm_of(c) for c in cases):
        print("[–] 第 4 项跳过：本库无 design_method 字段（不判违规；详见汇总「已跳过」）")
        skipped.append("第 4 项 设计方法关联：全库无 design_method 字段，本项未生效")
        bad_dm = []
    else:
        bad_dm = []
        for c in cases:
            dm = _dm_of(c)
            if not (set(dm) & DESIGN_METHODS):
                bad_dm.append(c.get("id", "?"))
    if bad_dm:
        fails.append(f"{len(bad_dm)} 条用例未关联合法测试设计方法"
                     f"（6 方法之一或多）: {bad_dm[:10]}")
    elif not skipped:
        print(f"[✓] 全部 {total} 条用例均关联测试设计方法")

    # 5. 编造场景（coverage_rule 中的 R-xxx 必须落在需求清单内）
    if args.requirement_rules:
        fab = []
        for c in cases:
            for tok in str(c.get("coverage_rule", "")).split(";"):
                tok = tok.strip()
                if re.fullmatch(r"R-\d+", tok) and tok not in rule_ids:
                    fab.append((c.get("id", "?"), tok))
        if fab:
            fails.append(f"{len(fab)} 条用例覆盖规则不在需求清单内（疑似编造）: {fab[:10]}")
        else:
            print(f"[✓] 无编造场景")

    # 6. 语义重复
    seen = {}
    for c in cases:
        key = (c.get("module", ""), norm(c.get("steps", "")), norm(c.get("expected", "")))
        seen.setdefault(key, []).append(c.get("id", "?"))
    dups = [v for v in seen.values() if len(v) > 1]
    if dups:
        fails.append(f"存在 {len(dups)} 组语义重复用例: {dups[:5]}")
    else:
        print(f"[✓] 无语义重复用例")

    # 7. 预期结果可判定（不可判定词一票否决；缺断言标志仅告警）
    vague, no_marker = [], []
    for c in cases:
        exp = str(c.get("expected", "") or "")
        if not exp.strip():
            vague.append((c.get("id", "?"), "预期为空"))
            continue
        hit = [w for w in UNJUDGEABLE_WORDS if w in exp]
        if hit:
            vague.append((c.get("id", "?"), "/".join(hit[:3])))
        elif not ASSERT_MARKERS.search(exp):
            no_marker.append(c.get("id", "?"))
    if vague:
        fails.append(f"{len(vague)} 条用例预期结果不可判定（命中不可判定词或为空）: {vague[:10]}")
    else:
        print(f"[✓] 全部 {total} 条用例预期结果可判定")
    if no_marker:
        warns.append(f"{len(no_marker)} 条用例预期缺少断言标志（应/数值/逐字文案/清单编号），建议改写: {no_marker[:10]}")

    # 8. 标题规范与残缺检查
    bad_title, no_steps, placeholder = [], [], []
    title_map = {}
    for c in cases:
        cid = c.get("id", "?")
        t = case_title(c)
        if not t:
            bad_title.append((cid, "标题为空"))
        else:
            reason = None
            if len(t) > args.title_max:
                reason = f"超长 {len(t)} 字（上限 {args.title_max}）"
            elif re.match(r"^\s*\d+\s*[、.．]", t):
                reason = "含序号前缀"
            elif "【" in t or "】" in t:
                reason = "含【】标记"
            elif re.search(r"[，。；！？,;!?]\s*$", t):
                reason = "含句末标点"
            if reason:
                bad_title.append((cid, reason))
            if TITLE_PLACEHOLDER.search(t):
                placeholder.append((cid, t))
            title_map.setdefault((c.get("module", ""), norm(t)), []).append(cid)
        if not str(c.get("steps", "") or "").strip():
            no_steps.append(cid)

    if bad_title:
        fails.append(f"{len(bad_title)} 条用例标题不合规（≤{args.title_max} 字 / 无序号前缀 / 无【】 / 无句末标点）: {bad_title[:10]}")
    else:
        print(f"[✓] 全部 {total} 条用例标题合规")
    if no_steps:
        fails.append(f"{len(no_steps)} 条用例缺失测试步骤（残缺条目不得入库）: {no_steps[:10]}")
    if placeholder:
        fails.append(f"{len(placeholder)} 条用例标题含占位残留（待XX更新/TBD/XXX）: {placeholder[:5]}")
    dup_titles = [(k[1], v) for k, v in title_map.items() if len(v) > 1]
    if dup_titles:
        warns.append(f"{len(dup_titles)} 组同模块标题重名，须靠唯一用例编号区分: {dup_titles[:5]}")

    # 8b. 用例编号唯一性（编号是追溯锚点，重复即阻断）
    id_map = {}
    for c in cases:
        cid = str(c.get("id", "") or "").strip()
        if cid:
            id_map.setdefault(cid, 0)
            id_map[cid] += 1
    dup_ids = [cid for cid, n in id_map.items() if n > 1]
    if dup_ids:
        fails.append(f"{len(dup_ids)} 个用例编号重复（追溯锚点不得重复）: {dup_ids[:10]}")
    else:
        print(f"[✓] 用例编号唯一（{len(id_map)} 个显式编号）")

    # 9. 场景构成配额（每功能点 1 正向 : ≥3 异常/边界，含权限校验）
    mod_scene = {}
    for c in cases:
        m = str(c.get("module", "") or "(未分模块)")
        d = mod_scene.setdefault(m, {"pos": 0, "neg": 0, "perm": 0, "n": 0})
        d["n"] += 1
        kind, is_perm = classify_case(c)
        if is_perm:
            d["perm"] += 1
        d[kind] += 1

    zero_neg, thin_neg, no_perm = [], [], []
    for m, d in sorted(mod_scene.items()):
        if d["n"] >= args.scene_min_cases and d["neg"] == 0:
            zero_neg.append(f"{m}({d['n']} 条)")
        elif d["pos"] and d["neg"] / d["pos"] < 1 / 3:
            thin_neg.append(f"{m}(正{d['pos']}:负{d['neg']})")
        if d["n"] >= args.scene_min_cases and d["perm"] == 0:
            no_perm.append(f"{m}({d['n']} 条)")

    if zero_neg:
        fails.append(f"{len(zero_neg)} 个模块无任何异常/边界用例（违反 1 正向:≥3 负向配额）: {zero_neg[:5]}")
    else:
        print(f"[✓] 各模块均含异常/边界类用例")
    if thin_neg:
        warns.append(f"{len(thin_neg)} 个模块负向用例偏少（建议 1 正向 : ≥3 异常/边界）: {thin_neg[:5]}")
    if no_perm:
        warns.append(f"{len(no_perm)} 个模块无权限校验类用例: {no_perm[:5]}")

    # 10. 孤儿用例（无 coverage_rule，且未标 exploratory；默认直接阻断）
    # 「全库都没有 coverage_rule 且没给需求清单」= 这份库根本不做需求追溯，
    # 此时每条都算孤儿（100%），判它没有信息量。跳过并显式登记，不静默放行。
    has_rule_field = any(str(c.get("coverage_rule", "") or "").strip() for c in cases)
    orphans = []
    for c in cases:
        if str(c.get("coverage_rule", "") or "").strip():
            continue
        v = c.get("exploratory")
        if v is True or str(v).strip().lower() in ("1", "true", "yes", "y"):
            continue
        orphans.append(str(c.get("id", "?")))
    orphan_ratio = len(orphans) / total
    if not has_rule_field and not args.requirement_rules:
        print("[–] 第 10 项跳过：全库无 coverage_rule 且未提供需求清单（本库不做需求追溯）")
        skipped.append("第 10 项 孤儿用例：全库无 coverage_rule 且无需求清单，"
                       "需求追溯与覆盖率检查本项未生效")
    elif orphans and orphan_ratio > args.orphan_max:
        fails.append(f"{len(orphans)} 条孤儿用例（无 coverage_rule 且未标 exploratory）"
                     f"占比 {orphan_ratio:.0%} > 上限 {args.orphan_max:.0%}: {orphans[:10]}")
    elif orphans:
        warns.append(f"{len(orphans)} 条孤儿用例（占比 {orphan_ratio:.0%}，未超上限 "
                     f"{args.orphan_max:.0%}）: {orphans[:10]}")
    else:
        print(f"[✓] 无孤儿用例（每条用例均有需求映射）")

    # 需求 → 用例 的显式回指索引（第 11/13 项共用；只认 coverage_rule 里写明的 R-ID）
    linked = {}
    for c in cases:
        for tok in str(c.get("coverage_rule", "") or "").split(";"):
            tok = tok.strip()
            if re.fullmatch(r"R-\d+", tok):
                linked.setdefault(tok, []).append(c)

    # 11. 需求密度（M1）：逐需求计数，打破"模块合计达标即放行"的平台化分布
    if args.density_mode != "off" and args.min_cases_per_rule > 0:
        scope = sorted(rule_ids) if rule_ids else sorted(linked)
        gaps = []
        for rid in scope:
            if rid in exempt_rules:
                continue
            n = len(linked.get(rid, []))
            if n < args.min_cases_per_rule:
                gaps.append((rid, n, args.min_cases_per_rule - n))
        gaps.sort(key=lambda x: (-x[2], x[0]))
        total_gap = sum(g[2] for g in gaps)
        if gaps:
            msg = (f"{len(gaps)} 个需求用例密度不足（<{args.min_cases_per_rule} 条/需求），"
                   f"合计缺口 {total_gap} 条: "
                   + "、".join(f"{r}({n}条,缺{g})" for r, n, g in gaps[:10])
                   + ("…" if len(gaps) > 10 else ""))
            if exempt_rules:
                msg += f"（已豁免 {len(exempt_rules)} 个: {','.join(sorted(exempt_rules))}）"
            if args.density_mode == "block":
                fails.append(msg)
            else:
                warns.append(msg)
            print(f"[!] 需求密度：{len(gaps)}/{len(scope)} 个需求 < {args.min_cases_per_rule} 条，"
                  f"合计缺口 {total_gap} 条")
            for r, n, g in gaps[:15]:
                print(f"      {r:8s} {n:2d} 条  缺 {g} 条  {rule_meta.get(r, '')}")
            if len(gaps) > 15:
                print(f"      … 其余 {len(gaps) - 15} 个需求见汇总消息")
        else:
            print(f"[✓] 需求密度达标（{len(scope)} 个需求均 ≥{args.min_cases_per_rule} 条）")

    # 12. 方法一致性（M2）：声称的方法必须有落地证据，否则判"方法虚标"
    if args.method_check != "off":
        fake, thin = [], []
        for c in cases:
            cid = c.get("id", "?")
            t = body_text(c)
            for m in as_list(c.get("design_method")):
                if m == "边界值分析":
                    bw, lit, num = boundary_evidence(c)
                    if not (bw or lit):
                        fake.append((cid, m, "步骤/预期无比较·极值词也无 0·100 边界值"))
                    elif not num:
                        fake.append((cid, m, "无具体数值"))
                elif m == "等价类划分":
                    n = len(set(test_data_values(c)))
                    if n >= 2 or any(w in t for w in LEXICON["eq_class"]):
                        continue
                    if n == 1:
                        thin.append((cid, "仅 1 个取值，未枚举等价类集合"))
                    else:
                        fake.append((cid, m, "test_data 无任何取值"))
                elif m in ("判定表法", "正交分析法"):
                    dims = condition_dims(c)
                    if dims < 2:
                        fake.append((cid, m, f"仅 {dims} 个条件维度（需≥2）"))
        if fake:
            by_method = {}
            for cid, m, why in fake:
                by_method.setdefault(m, 0)
                by_method[m] += 1
            dist = "、".join(f"{k} {v} 条" for k, v in sorted(by_method.items()))
            msg = (f"{len(fake)} 条用例存在方法虚标（{dist}）: "
                   + "、".join(f"{cid}·{m}·{why}" for cid, m, why in fake[:8])
                   + ("…" if len(fake) > 8 else ""))
            if args.method_check == "block":
                fails.append(msg)
            else:
                warns.append(msg)
            print(f"[!] 方法一致性：{len(fake)} 条方法虚标（{dist}）")
            for cid, m, why in fake[:15]:
                print(f"      {cid:16s} {m}  {why}")
            if len(fake) > 15:
                print(f"      … 其余 {len(fake) - 15} 条见汇总消息")
        else:
            print(f"[✓] 设计方法一致：全部声称的方法均有落地证据")
        if thin:
            warns.append(f"{len(thin)} 条标「等价类划分」的用例只枚举了 1 个取值"
                         f"（属欠展开，非虚标；建议按等价类矩阵补齐取值集合）: "
                         + "、".join(cid for cid, _ in thin[:10])
                         + ("…" if len(thin) > 10 else ""))

    # 13. 需求级场景配额（M6）：第 9 项的下钻，防"大模块掩盖小需求"
    if args.scene_rule_mode != "off":
        no_neg, thin_neg_rule = [], []
        for rid, lst in sorted(linked.items()):
            if rid in exempt_rules:
                continue
            neg = sum(1 for c in lst if classify_case(c)[0] == "neg")
            if neg == 0:
                no_neg.append(f"{rid}({len(lst)} 条)")
            elif neg < args.min_neg_per_rule:
                thin_neg_rule.append(f"{rid}(负{neg}条)")
        if thin_neg_rule:
            warns.append(f"{len(thin_neg_rule)} 个需求的负向用例偏少（<{args.min_neg_per_rule} 条，"
                         f"建议 1 正向 : ≥3 异常/边界）: "
                         + "、".join(thin_neg_rule[:10]) + ("…" if len(thin_neg_rule) > 10 else ""))
        if no_neg:
            msg = (f"{len(no_neg)} 个需求无任何异常/边界用例（需求级至少 1 条负向）: "
                   + "、".join(no_neg[:10]) + ("…" if len(no_neg) > 10 else ""))
            if args.scene_rule_mode == "block":
                fails.append(msg)
            else:
                warns.append(msg)
        else:
            print(f"[✓] 各需求均含异常/边界类用例（需求级）")

    # 14. 范围性用例（M4 兜底）：一条用例覆盖多个并列场景
    #     第 9/11/13 项都只数"条数"，数不出"4 条覆盖 16 个场景"这种情况——
    #     这是 13 项闸门里唯一没有兜底判据的地方，本项补上。
    if args.range_mode != "off":
        strong, weak = [], []
        for c in cases:
            cid = c.get("id", "?")
            hit, objs, n_exp, words = range_evidence(c)
            if not hit:
                continue
            # 备注列已做场景展开的，降级为弱证据——case_design.md 第七节允许
            # "预期同构的批量校验"用备注展开，这条豁免必须留出口，否则会误伤。
            has_remark = bool(str(c.get("remark") or "").strip())
            if objs >= args.range_min_objs and n_exp <= 1:
                # 备注列已逐项展开的，降级为弱提示——case_design.md 第七节允许
                # "预期同构的批量校验"用备注展开，这条豁免必须留出口，否则会误伤。
                (weak if has_remark else strong).append((cid, objs, n_exp, words))
            elif n_exp <= 1 and not has_remark:
                weak.append((cid, objs, n_exp, words))
        if strong:
            msg = (f"{len(strong)} 条范围性用例：步骤含「{'/'.join(RANGE_WORDS[:7])}」且并列 "
                   f"{args.range_min_objs}+ 个对象，但预期只有 1 条断言"
                   f"（一条用例吃掉 N 个场景）: "
                   + "、".join(f"{cid}({objs}对象)" for cid, objs, _, _ in strong[:10])
                   + ("…" if len(strong) > 10 else ""))
            if args.range_mode == "block":
                fails.append(msg)
            else:
                warns.append(msg)
            print(f"[!] 范围性用例：{len(strong)} 条（建议拆条，或在备注列逐项展开场景）")
            for cid, objs, n_exp, words in strong[:15]:
                print(f"      {cid:16s} 对象 {objs} 个 · 预期 {n_exp} 条 · 命中「{words[0]}」")
            if len(strong) > 15:
                print(f"      … 其余 {len(strong) - 15} 条见汇总消息")
        else:
            print(f"[✓] 无范围性用例（单条用例未覆盖多个并列场景）")
        if weak and args.range_weak_mode != "off":
            warns.append(f"{len(weak)} 条用例疑似范围性（含范围词但并列对象不足 "
                         f"{args.range_min_objs} 个，或已在备注列展开），仅提示: "
                         + "、".join(cid for cid, _, _, _ in weak[:10])
                         + ("…" if len(weak) > 10 else ""))

    print()
    if skipped:
        # 跳过必须可见。静默跳过 = 把闸门关掉还不报警，比闸门误报更危险。
        print("=== 已跳过的闸门（本库字段形态不支持，不代表通过）===")
        for s in skipped:
            print(f"  – {s}")
        print()
    if fails:
        print("=== 预审不通过，需修正后重跑 ===")
        for f in fails:
            print(f"  ✗ {f}")
        for w in warns:
            print(f"  ! {w}")
        return 1
    print("=== 预审全部通过 ===")
    for w in warns:
        print(f"  ! {w}")
    return 0


if __name__ == "__main__":
    # 退出码 3 = 脚本自身崩溃。必须与 1（用例不达标）区分开：
    # 早期未捕获异常统一表现为 exit 1，会被误读成"预审不通过"，导致对着
    # 不存在的质量问题返工（steps 传数组崩溃那次就是这样藏了很久）。
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception:
        import traceback
        print("\n[内部错误] prescreen.py 自身崩溃（exit 3），不是数据不达标。",
              file=sys.stderr)
        print("请把下面的堆栈连同输入样例一起报给技能维护者：", file=sys.stderr)
        traceback.print_exc()
        sys.exit(3)
