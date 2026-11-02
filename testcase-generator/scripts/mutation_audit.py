#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mutation_audit.py — 需求层变异强度审计器（v1.7.0 · 默认 P0 阻断）

要解决的问题
------------
现有两道闸门量的都是"字面"，不是"行为"：
  · prescreen 第 7 项「预期可判定」= 不可判定词黑名单 + 断言标志（"应"/"提示"/任意数字即过）；
  · coverage_audit = 显式 coverage_rule 直接采信，或文本 bigram Jaccard ≥ 0.08 即算强匹配。
结果：一份"预审 10 项全过 + 覆盖率 100% + 0 孤儿"的用例集，仍可能有六成以上的
"合理但错误"的实现完全测不出来（实测样本变异得分 26.3%，见
references/mutation_review.md 与项目根 test_mutation_audit.py）。

本脚本把"覆盖"从"文字命中"升级为"能测出错"：
  对每条需求规则枚举「合理但错误」的实现（变异体 mutant），
  若用例集中存在某条用例的预期结果能区分该错误实现 → 该变异体被杀死；
  杀不死 = 名义覆盖。得分 = 杀死数 / 有效变异体数。

算子（详见 references/mutation_review.md 第二节）
  确定性、脚本自动抽取（无需模型）：NUM 数值 / BND 边界方向 / NEG 否定翻转 /
                                    DEL 动作删除 / ENUM 枚举替换·删项
  语义、需显式开启（--semantic，默认关）：ORD 顺序 / STM 状态迁移 / IDEM 幂等

关键设计（防"假杀死"）
  killer_pattern 只允许锚定「能区分对错的那一个要素」（数值/方向/枚举项/动作结果/否定词），
  不得只锚定功能名；且**只在 expected 上匹配**，不看 steps——steps 里写"连续输错 5 次"
  不是边界断言，不能让弱用例蒙混过关。用 --explain 可逐条打印 pattern 与命中原文。

输入：
  用例 —— .json（数组或 {"cases": [...]}）
  需求 —— requirements.json（extract_requirements.py 产出：[{id, module, text, priority, ...}]）

用法：
  python mutation_audit.py test_cases.json requirements.json -o 强度报告.md
      # 默认 --mut-gate p0：P0 规则 <0.90 或零强度即阻断，其余只告警
  python mutation_audit.py test_cases.json requirements.json --mut-gate warn   # 只出报告
  python mutation_audit.py test_cases.json requirements.json --mut-gate block  # 全量阻断
  python mutation_audit.py test_cases.json requirements.json --explain --rule R-101
  python mutation_audit.py test_cases.json requirements.json --semantic mutants.json \
      --ignore mutants.ignore.json --format json -o audit.json

退出码：0 放行（warn/off；p0 模式下无 P0 不达标）；1 阻断；2 输入/参数错误。
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime

DEFAULT_MUT_MIN = 0.70          # 全局变异得分达标线
DEFAULT_P0_MUT_MIN = 0.90       # P0 规则达标线
DEFAULT_MAX_PER_RULE = 6        # 每条规则最多自动生成多少个变异体
DEFAULT_MIN_MUTANTS_FOR_ZERO = 2  # 变异体少于该数的规则判「证据不足」，不判零强度

# 每算子配额（先保证"错误类型"的多样性，再谈数量）：
# 若只按总量截断，一条含两个数字的规则会被 4 个 NUM 变异体占满，
# 关键的"否定翻转/动作漏做"变异体根本不会生成——那等于自己把检出能力砍掉一半。
OPERATOR_CAP = {"TEXT": 2, "PRI": 2, "BND": 2, "NUM": 2, "NEG": 1, "DEL": 1, "ENUM": 1,
                "ORD": 1, "STM": 1, "IDEM": 1}

# ---------------------------------------------------------------- 算子素材

# 数值 + 单位（NUM）。英文单位后面加 (?!配字母) 负向前瞻，
# 否则 "10 steps" 会被切成 "10 s" 造出一个无意义的变异体。
UNIT_PAT = (r"(次|分钟|小时|毫秒|秒|天|个月|元|字符|个字|%|个|条|人|台|步|"
            r"km/h|mph|ms|min|sec|kg|kb|mb|gb|s)")
NUM_RE = re.compile(r"(\d+(?:\.\d+)?)\s*" + UNIT_PAT + r"(?![A-Za-z])")

# 逐字文案（TEXT）：规则里被引号包住的固定文案 —— 改一个字就是最真实的"文案缺陷"
TEXT_RE = re.compile(r"[“\"「『]([^”\"」』]{2,40})[”\"」』]")

# 边界方向（BND）：左 = 规则里可能出现的写法，右 = 翻转后的错误写法说明
BND_WORDS = [
    ("不超过", "改为「小于」或「少于」"),
    ("不少于", "改为「多于」或「超过」"),
    ("不低于", "改为「低于」"),
    ("不高于", "改为「高于」"),
    ("不超过", "改为「小于」"),
    ("超过", "边界包含性翻转为「及以上」"),
    ("大于", "边界包含性翻转为「大于等于」"),
    ("小于", "边界包含性翻转为「小于等于」"),
    ("低于", "边界包含性翻转为「小于等于」"),
    ("高于", "边界包含性翻转为「大于等于」"),
    ("至少", "改为「超过」"),
    ("最多", "改为「少于」"),
    ("以上", "边界包含性翻转为「超过」"),
    ("以下", "边界包含性翻转为「低于」"),
    ("以内", "边界包含性翻转为「小于」"),
]
BND_TAIL = r"(及以下|及以上|以下|以上|免|不需要|不触发|不弹|直接|不校验)"

# 否定翻转（NEG）：命中即去掉否定词，语义反转
NEG_WORDS = ["不可", "不能", "不允许", "禁止", "不得", "无法", "无需", "不支持", "免"]
NEG_SYNONYM = {
    "不可": ("不可", "不能", "无法", "禁止", "不得", "不允许"),
    "不能": ("不可", "不能", "无法", "禁止", "不得"),
    "不允许": ("不可", "不能", "无法", "禁止", "不允许"),
    "禁止": ("禁止", "不可", "不允许", "不得"),
    "不得": ("不得", "不可", "禁止", "不允许"),
    "无法": ("无法", "不能", "不可"),
    "无需": ("无需", "不需要", "免于"),
    "不支持": ("不支持", "不可", "不能"),
    "免": ("免", "不需要", "无需"),
}

# 动作删除（DEL）：动作词 → 该动作"做成了"的可观测证据（killer 模板）
# 设计铁律：killer 必须是**结果态**，不能是动作名本身；且若规则里有明确主体
# （麦克风/输入框/库存…），killer 会被加上主体约束——否则「置灰」会命中任何
# "按钮置灰"的无关用例，得分虚高（真实库实测：47 条无关用例被判成杀手）。
SUBJECT_HINTS = ["麦克风", "摄像头", "输入框", "顶部图标", "图标", "播报",
                 "队列", "订单", "库存", "录音", "进度", "弹窗"]
# 只对这些"通用结果词"注入主体约束；其余动作（释放/回跳/关闭/打断/录音…）的 killer
# 模板本身已带语境，再注入会串味（实测：给「关闭」注入「麦克风」会得到"麦克风…订单已关闭"）。
GENERIC_ACTIONS = {"置灰", "隐藏", "清零", "重置", "禁用"}
ACTION_KILLERS = {
    "关闭": r"(?:弹窗|页面|列表|订单|记录|入口).{0,6}(关闭|消失|收起|退出)|已关闭|关闭成功|已取消",
    "释放": r"库存.{0,6}(释放|恢复|回滚|归还|增加)|(释放|恢复|回滚|归还).{0,6}库存",
    "回跳": r"回跳|返回原|回到.{0,8}(页|详情)|原访问地址",
    "截断": r"截断|保留前\s*\d|仅保留|只保留",
    "清零": r"清零|归零|重置为\s*0|恢复为\s*0",
    "置灰": r"置灰|不可点击|禁用|disabled",
    "隐藏": r"隐藏|不展示|不可见|不显示",
    "锁定": r"(?:仍|继续|依旧|再次).{0,10}(锁定|无法登录|不可登录)|锁定(?:中|状态|生效)|账号.{0,4}(冻结|封禁)",
    "打断": r"(?:P0|安全).{0,10}(打断|抢占|中断)|(?:打断|抢占).{0,8}(正在播放|低优先级|P2|P3)",
    "录音": r"录音(?:中|状态|态)|开始录音|进入录音|采集中|正在听|倾听中|语音输入.{0,6}(可用|激活)",
    "采集": r"预览区.{0,10}(实时|画面|更新)|采集画面|实时画面|画面.{0,6}(实时更新|刷新)",
    "重置": r"重置|清零|恢复默认",
    "拒绝": r"拒绝|拦截|驳回|不允许",
    "删除": r"删除|清除|移除",
    "回滚": r"回滚|恢复上一版|还原",
}

# 枚举替换 / 删项（ENUM）
ENUM_RETURN_RE = re.compile(
    r"(?:返回|展示|显示|给出|进入)(?:默认|热门|推荐|全部|最近)(?:的)?([\u4e00-\u9fa5]{2,8})")
ENUM_SPLIT_RE = re.compile(r"([\u4e00-\u9fa5A-Za-z0-9]{1,10})、([\u4e00-\u9fa5A-Za-z0-9]{1,10})")

# 优先级序关系（PRI）："P0 > P1" 这类矩阵规则既没有数值单位、也没有否定词，
# 只能靠序关系派生变异体——否则"优先级仲裁"这种最关键的规则会被判"不可测量"。
PRI_RE = re.compile(r"(P[0-4])\s*[>＞]\s*(P[0-4])")

OPERATOR_ORDER = {"TEXT": 0, "PRI": 1, "BND": 2, "NUM": 3, "NEG": 4, "DEL": 5, "ENUM": 6,
                  "ORD": 7, "STM": 8, "IDEM": 9}
OPERATOR_NAME = {
    "NUM": "数值", "BND": "边界方向", "NEG": "否定翻转", "DEL": "动作删除",
    "ENUM": "枚举", "TEXT": "逐字文案", "PRI": "优先级序",
    "ORD": "顺序", "STM": "状态迁移", "IDEM": "幂等",
}

# 非功能类用例不参与"零贡献"判定（杀不死功能变异体属正常）
NONFUNC_TYPES = {"兼容", "兼容性", "性能", "安全", "易用", "易用性", "可靠性", "可靠"}


# ---------------------------------------------------------------- 读入

def _sibling(name):
    """按文件名加载同目录脚本（避免维护第二套 Excel 表头别名）。"""
    import importlib.util
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), name)
    if not os.path.exists(path):
        return None
    spec = importlib.util.spec_from_file_location("_tc_" + name.replace(".py", ""), path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_cases(path):
    if path.lower().endswith((".xlsx", ".xlsm", ".xls")):
        mod = _sibling("coverage_audit.py")
        if mod is None:
            raise RuntimeError("读取 Excel 需要同目录的 coverage_audit.py")
        return mod.load_cases(path)
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict) and "cases" in data:
        return data["cases"]
    if isinstance(data, list):
        return data
    raise ValueError("用例文件需为数组，或含 'cases' 键的对象")


def load_rules(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict):
        for k in ("rules", "requirements", "requirement_rules"):
            if k in data:
                data = data[k]
                break
    if not isinstance(data, list):
        raise ValueError("需求文件需为数组，或含 'rules'/'requirements' 键的对象")
    out = []
    for r in data:
        if not isinstance(r, dict):
            continue
        if r.get("included") is False or r.get("type") == "excluded":
            continue
        rid = r.get("id")
        text = r.get("text") or r.get("rule") or r.get("requirement") or ""
        if not rid or not text:
            continue
        rr = dict(r)
        rr["text"] = text
        out.append(rr)
    return out


def load_json_optional(path, what):
    if not path:
        return []
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"[警告] 读取{what}失败（已忽略）: {e}", file=sys.stderr)
        return []
    if isinstance(data, dict) and "mutants" in data:
        data = data["mutants"]
    return data if isinstance(data, list) else []


# ---------------------------------------------------------------- 变异体生成

def _mid(rid, op, seq):
    safe = re.sub(r"[^A-Za-z0-9]", "", rid)
    return f"M-{safe}-{op}-{seq}"


def _unit_pat(unit):
    """单位匹配：中文单位允许同时匹配常见英文写法（秒/s、毫秒/ms、分钟/min）。"""
    alias = {"秒": "s", "分钟": "min", "毫秒": "ms", "小时": "h"}.get(unit)
    if alias:
        return rf"(?:\s*{re.escape(unit)}|\s*{alias})?"
    return rf"\s*{re.escape(unit)}?"


def gen_mutants_for_rule(rule, max_per_rule=DEFAULT_MAX_PER_RULE, operators=None):
    """从规则文本自动抽取确定性变异体（NUM/BND/NEG/DEL/ENUM）。"""
    rid = rule["id"]
    text = rule.get("text", "")
    cands = []

    # TEXT —— 逐字文案（优先级最高：文案类规则只有"改一个字/换一句"这一种真实错法，
    # 而这类规则在真实库里占比很高，没有它就会被误判成"不可测量"）
    seen_text = set()
    for m in TEXT_RE.finditer(text):
        core = m.group(1).strip().strip("。；;，,")
        if len(core) < 2 or core in seen_text:
            continue
        seen_text.add(core)
        cands.append({
            "rule_id": rid, "operator": "TEXT",
            "source_span": m.group(0),
            "wrong_claim": f"固定文案「{core}」被改动（错字 / 改写 / 漏句）",
            "killer_pattern": re.escape(core),
        })

    # PRI —— 优先级序关系（P0 > P1 写反）
    for m in PRI_RE.finditer(text):
        hi, lo = m.group(1), m.group(2)
        cands.append({
            "rule_id": rid, "operator": "PRI",
            "source_span": m.group(0),
            "wrong_claim": f"优先级序关系「{hi} > {lo}」被写反",
            "killer_pattern": (rf"(?:{hi}|安全).{{0,12}}(?:优先|高于|打断|抢占|覆盖)"
                               rf"|{lo}.{{0,8}}被.{{0,8}}(?:{hi}|打断|抢占)"),
        })

    # BND —— 边界方向（优先级最高：差一错误的主要来源，Guru99 要求测每个极限两侧）
    for word, note in BND_WORDS:
        idx = text.find(word)
        if idx < 0:
            continue
        span = text[idx: idx + len(word) + 12]
        num_m = NUM_RE.search(span)
        if not num_m:
            # 边界词附近抽不到数值 → killer 只剩宽泛尾词（"免/以下"），会误判成"已杀死"。
            # 宁可不生成，也不要造一个假变异体去污染得分。
            continue
        value, unit = num_m.group(1), num_m.group(2)
        killer = rf"{re.escape(value)}\s*{re.escape(unit)}.{{0,10}}{BND_TAIL}"
        cands.append({
            "rule_id": rid, "operator": "BND",
            "source_span": span,
            "wrong_claim": f"「{word}」的边界包含性被写反（{note}）",
            "killer_pattern": killer,
        })

    # NUM —— 数值（±1）。先把所有数字的「-1」侧排前面：
    # 差一（少算一次 / 少锁一分钟）是最常见的实现错误，也是 Guru99 强调的"边界两侧"里更易漏的一侧。
    nums, seen_num = [], set()
    for m in NUM_RE.finditer(text):
        value, unit = m.group(1), m.group(2)
        if (value, unit) in seen_num:
            continue
        seen_num.add((value, unit))
        try:
            base = float(value)
        except ValueError:
            continue
        nums.append((value, unit, base))
    for delta in (-1, 1):
        for value, unit, base in nums:
            # 步长按单位量级来定：毫秒级用 ±1ms 等于没测（没人会把 800ms 写成 799ms），
            # 计数/时长类才用 ±1。
            step = 100 if unit == "毫秒" else 1
            d = delta * step
            if base + d <= 0:
                continue
            nv = round(base + d, 4)          # 防 8.3 - 1 = 7.300000000000001 这类浮点噪声
            nv_s = str(int(nv)) if nv == int(nv) else ("%g" % nv)
            # 允许小数邻域：变异值 89 时，用例写「89.8%」正是能区分 89 与 90 的断言
            # （真实库习惯用 90.9% / 89.8% / 95.2% 表达"刚好越过/刚好不到"）。
            # 不加 (?:\.\d+)? 会把这类边界用例全部漏判成"杀不死"。
            nv_pat = rf"{re.escape(nv_s)}(?:\.\d+)?"
            v_pat = rf"{re.escape(value)}(?:\.\d+)?"
            alt = []
            up = _unit_pat(unit)
            if d < 0:
                # 阈值被调小（更早触发）→ 「未达 V 就不该发生」这类反证式边界断言能杀死它。
                # 例：实现把 3s 改成 2s，「计时未达 3s 时无任何播报」会失败。
                alt.append(rf"(?:未达|不足|未满|小于|低于|少于)\s*{v_pat}{up}"
                           rf"[^。；]{{0,16}}(?:不|无|未有|静默|不播)")
            else:
                # 阈值被调大（更晚触发）→ 上界断言「不超过 V」或边界点正证「达到 V 应播」能杀死它。
                alt.append(rf"(?:不超过|未超过|最多|不大于)\s*{v_pat}{up}")
                alt.append(rf"(?:达到|恰好|刚好|正好)\s*{v_pat}{up}"
                           rf"[^。；]{{0,16}}(?:应|播|触发|执行|生效|提示|报警)")
            cands.append({
                "rule_id": rid, "operator": "NUM",
                "source_span": f"{value}{unit}",
                "wrong_claim": f"阈值/数量「{value}{unit}」被写成「{nv_s}{unit}」",
                "killer_pattern": rf"{nv_pat}\s*{re.escape(unit)}",
                "alt_patterns": alt,
            })

    # NEG —— 否定翻转
    for word in NEG_WORDS:
        for m in re.finditer(re.escape(word), text):
            tail = text[m.end(): m.end() + 6]
            core = re.match(r"[\u4e00-\u9fa5A-Za-z0-9]{1,6}", tail)
            if not core:
                continue
            core_s = core.group(0)
            syn = list(NEG_SYNONYM.get(word, (word,)))
            # 真实用例写「不出现 / 未触发 / 无重复」的情况远多于「不允许出现」，
            # 只认否定词表会把这些强用例判成"杀不死"。强禁止类额外接受 不/未/无/没有。
            if word in ("不可", "不允许", "禁止", "不得") and len(core_s) >= 2:
                syn += ["不", "未", "无", "没有"]
            killer = "(?:" + "|".join(re.escape(s) for s in syn) + ")" + re.escape(core_s)
            cands.append({
                "rule_id": rid, "operator": "NEG",
                "source_span": f"{word}{core_s}",
                "wrong_claim": f"「{word}{core_s}」被写成允许（否定被去掉）",
                "killer_pattern": killer,
            })
            break   # 同一否定词只取第一处，控制数量

    # DEL —— 动作删除
    subj = next((s for s in SUBJECT_HINTS if s in text), "")
    for act, killer in ACTION_KILLERS.items():
        if act not in text:
            continue
        k = killer
        # 主体约束：把"置灰/禁用"这类通用结果词绑定到规则里的主体，避免命中无关用例。
        # 动作词本身与主体同名时（如规则写"录音"）不注入，否则 pattern 会变成同义反复。
        if act in GENERIC_ACTIONS and subj and subj != act and subj not in killer:
            k = rf"(?:{subj}.{{0,12}}(?:{killer})|(?:{killer}).{{0,12}}{subj})"
        cands.append({
            "rule_id": rid, "operator": "DEL",
            "source_span": act,
            "wrong_claim": f"「{act}」这个动作被漏做（只改了状态/只给了提示）",
            "killer_pattern": k,
        })

    # ENUM —— 返回值替换 / 并列项删项
    m = ENUM_RETURN_RE.search(text)
    if m:
        noun = m.group(1)
        cands.append({
            "rule_id": rid, "operator": "ENUM",
            "source_span": m.group(0),
            "wrong_claim": f"「{m.group(0)}」被写成返回空/无结果",
            "killer_pattern": re.escape(noun),
        })
    m = ENUM_SPLIT_RE.search(text)
    if m:
        left, right = m.group(1), m.group(2)
        # 只认"短并列项"。若切出来的是一整句/带连接词（如「本地、云端和课程口播之间的」），
        # 那不是并列枚举，杀掉它也没有业务含义——宁可不生成。
        bad = ("和", "与", "及", "或", "的", "，", "。")
        if len(right) <= 8 and len(left) <= 8 and not any(b in right for b in bad):
            cands.append({
                "rule_id": rid, "operator": "ENUM",
                "source_span": m.group(0),
                "wrong_claim": f"并列项中的「{right}」被漏掉",
                "killer_pattern": re.escape(right),
            })

    # 去重 → 按算子优先级排序 → 每算子配额 → 总量截断
    seen, uniq = set(), []
    for c in sorted(cands, key=lambda x: OPERATOR_ORDER.get(x["operator"], 9)):
        if operators and c["operator"] not in operators:
            continue
        key = (c["operator"], c["killer_pattern"])
        if key in seen:
            continue
        seen.add(key)
        uniq.append(c)
    per_op, capped = {}, []
    for c in uniq:
        op = c["operator"]
        if per_op.get(op, 0) >= OPERATOR_CAP.get(op, 1):
            continue
        per_op[op] = per_op.get(op, 0) + 1
        capped.append(c)
    capped = capped[:max_per_rule]
    for i, c in enumerate(capped, 1):
        c["mid"] = _mid(rid, c["operator"], i)
        c["auto"] = True
    return capped


def merge_semantic(auto_mutants, semantic_mutants, rule_ids):
    """合并 --semantic 提供的语义变异体（ORD/STM/IDEM 等）。"""
    out = list(auto_mutants)
    for i, m in enumerate(semantic_mutants, 1):
        rid = m.get("rule_id")
        if rid not in rule_ids or not m.get("killer_pattern"):
            continue
        out.append({
            "mid": m.get("mid") or _mid(rid, m.get("operator", "SEM"), 100 + i),
            "rule_id": rid,
            "operator": m.get("operator", "SEM"),
            "source_span": m.get("source_span", ""),
            "wrong_claim": m.get("wrong_claim", "（语义变异体，未填描述）"),
            "killer_pattern": m["killer_pattern"],
            "auto": False,
        })
    return out


# ---------------------------------------------------------------- 评审

def case_expected(c, scope="expected"):
    parts = [c.get("expected") or c.get("预期结果") or ""]
    if scope == "expected+steps":
        parts.append(c.get("steps") or c.get("测试步骤") or "")
    return "\n".join(p for p in parts if p)


def norm_mod(s):
    """模块名归一：去掉节号/前导标点与空白，便于与用例模块做包含匹配。"""
    s = re.sub(r"^[\s.．、·\-—0-9]+", "", str(s or ""))
    return re.sub(r"\s+", "", s)


def case_rule_ids(c):
    return {t.strip() for t in str(c.get("coverage_rule", "")).split(";") if t.strip()}


def in_scope(c, rule_ids, rule_mods):
    """该用例是否在本次评审范围内（挂了被评审的规则，或模块与某条规则同域）。

    为什么要划范围：拿 35 条需求的规则去审 2000+ 条覆盖 20 个功能的用例库时，
    没挂规则、模块也不相干的用例天然杀不死任何变异体——把它们算成"零贡献"
    只会造出一个吓人但无意义的数字。零贡献只在"本应覆盖这些规则"的用例里才有意义。
    """
    if case_rule_ids(c) & rule_ids:
        return True
    cm = norm_mod(c.get("module") or c.get("测试模块") or "")
    if not cm or not rule_mods:
        return False
    return any(cm in rm or rm in cm for rm in rule_mods)


def build_entries(cases):
    """为每条用例生成稳定且唯一的键。

    真实用例库常常没有「用例编号」列（如 AI Coach 2405 条的表只有标题）。
    若全部回落到同一个 "(无编号)"，杀死统计会互相覆盖——一条用例杀死了变异体，
    等于所有用例都杀死了，得分虚高且零贡献清单失效。没有编号时用 Excel 行号兜底。
    """
    out, seen = [], {}
    for i, c in enumerate(cases, 2):          # Excel 数据从第 2 行开始
        cid = str(c.get("id") or c.get("用例编号") or "").strip()
        disp = cid or f"第{i}行"
        n = seen.get(disp, 0)
        seen[disp] = n + 1
        out.append((disp if n == 0 else f"{disp}#{n+1}", disp, c))
    return out


def audit(cases, rules, max_per_rule=DEFAULT_MAX_PER_RULE, semantic=None,
          ignore_ids=None, scope="expected", p0_mut_min=DEFAULT_P0_MUT_MIN,
          mut_min=DEFAULT_MUT_MIN, rule_floor_block=0.0, rule_filter=None,
          operators=None, min_mutants_for_zero=DEFAULT_MIN_MUTANTS_FOR_ZERO):
    ignore_ids = set(ignore_ids or [])
    rule_by_id = {r["id"]: r for r in rules}
    rules_used = [r for r in rules if not rule_filter or r["id"] in rule_filter]

    # 1) 生成变异体
    mutants = []
    for r in rules_used:
        mutants.extend(gen_mutants_for_rule(r, max_per_rule, operators))
    if semantic:
        mutants = merge_semantic(mutants, semantic, set(rule_by_id))

    # 2) 等价白名单（不计入分母）
    for m in mutants:
        m["ignored"] = m["mid"] in ignore_ids
    valid = [m for m in mutants if not m["ignored"]]

    # 3) 杀死判定：只看 expected；且**只在评估范围内判定**
    # 范围外用例（别的功能模块）即便文本碰巧命中也只是"跨功能相似"，不是这条需求被覆盖的证据。
    entries = build_entries(cases)
    rule_ids = {r["id"] for r in rules_used}
    rule_mods = {norm_mod(r.get("module")) for r in rules_used} - {""}
    scoped_entries = [(k, d, c) for k, d, c in entries if in_scope(c, rule_ids, rule_mods)]
    kill_map = {m["mid"]: [] for m in valid}
    case_kills = {key: [] for key, _, _ in entries}
    for m in valid:
        rxs = []
        for p in [m.get("killer_pattern")] + list(m.get("alt_patterns") or []):
            if not p:
                continue
            try:
                rxs.append(re.compile(p))
            except re.error:
                continue
        if not rxs:
            m["bad_pattern"] = True
            continue
        for key, disp, c in scoped_entries:
            text = case_expected(c, scope)
            if any(rx.search(text) for rx in rxs):
                kill_map[m["mid"]].append(disp)
                case_kills[key].append(m["mid"])

    # 4) 逐规则汇总
    rule_rows = []
    for r in rules_used:
        rid = r["id"]
        rms = [m for m in valid if m["rule_id"] == rid]
        killed = [m for m in rms if kill_map.get(m["mid"])]
        score = (len(killed) / len(rms)) if rms else None
        prio = (r.get("priority") or "").strip().upper()
        if prio not in ("P0", "P1", "P2", "P3"):
            prio = ""

        # 杀死者是否已挂到该规则（未挂 = 用例有强度但 RTM 缺映射）
        mapped = set()
        for key, disp, c in entries:
            if rid in case_rule_ids(c):
                mapped.add(disp)
        unmapped_killers = sorted({c for m in killed for c in kill_map[m["mid"]]} - mapped)

        status = "OK"
        if score is None:
            status = "不可测量"
        elif len(rms) < min_mutants_for_zero and not killed:
            # 证据不足：只有 1 个变异体且一个都没杀死——说明不了整条规则弱，
            # 只说明这一个错法没被测到（典型是表格/矩阵型规则，整表行为可能已有覆盖）。
            # 但若这 1 个已经被杀死，就不能算"证据不足"了，至少证明有强度。
            status = "证据不足"
        elif score <= rule_floor_block:
            status = "零强度"
        elif prio == "P0" and score < p0_mut_min:
            status = "P0 不达标"
        elif score < mut_min:
            status = "偏弱"

        rule_rows.append({
            "id": rid, "module": r.get("module", ""), "priority": prio,
            "text": r.get("text", ""), "mutants": len(rms), "killed": len(killed),
            "score": score, "status": status,
            "accepted": bool(r.get("unmeasurable_accepted") or r.get("accepted")),
            "survivors": [{"mid": m["mid"], "operator": m["operator"],
                           "wrong_claim": m["wrong_claim"],
                           "killer_pattern": m["killer_pattern"]}
                          for m in rms if not kill_map.get(m["mid"])],
            "unmapped_killers": unmapped_killers,
        })

    # 5) 汇总
    scored = [x for x in rule_rows if x["score"] is not None]
    total_valid = sum(x["mutants"] for x in scored)
    total_killed = sum(x["killed"] for x in scored)
    overall = (total_killed / total_valid) if total_valid else 0.0
    unmeasurable = [x for x in rule_rows if x["score"] is None]
    zero = [x for x in rule_rows if x["status"] == "零强度"]
    weak_evidence = [x for x in rule_rows if x["status"] == "证据不足"]
    p0_rules = [x for x in rule_rows if x["priority"] == "P0"]

    # 6) 零贡献用例（仅限评估范围内的功能类用例；非功能类豁免）
    scoped = scoped_entries
    zero_cases = []
    for key, disp, c in scoped:
        ttype = str(c.get("test_type") or c.get("测试类型") or "")
        if any(k in ttype for k in NONFUNC_TYPES):
            continue
        if not case_kills.get(key):
            zero_cases.append({"id": disp,
                               "name": c.get("name") or c.get("title") or c.get("用例名称", ""),
                               "module": c.get("module") or c.get("测试模块", ""),
                               "expected": case_expected(c, "expected")[:80]})

    # 7) 达标判定：区分「P0 不达标」与「其它不达标」，供 --mut-gate p0 只卡 P0
    fails, p0_fails = [], []
    if overall < mut_min:
        fails.append(f"全局变异得分 {overall*100:.1f}% < {mut_min*100:.0f}%")
    for x in rule_rows:
        # P0 不可测量 = 未验证。P0 是发布门禁，不允许"测不了"就默认过关。
        if x["priority"] == "P0" and x["score"] is None and not x["accepted"]:
            msg = f"{x['id']} 为 P0 但不可测量（规则抽不出判别要素＝未验证）"
            fails.append(msg)
            p0_fails.append(msg)
    for x in scored:
        if x["status"] == "P0 不达标":
            msg = f"{x['id']} 得分 {x['score']*100:.0f}%（P0 规则低于 {p0_mut_min*100:.0f}%）"
            fails.append(msg)
            p0_fails.append(msg)
        elif x["status"] == "零强度":
            msg = f"{x['id']} 得分 0%（零强度）"
            fails.append(msg)
            if x["priority"] == "P0":
                p0_fails.append(msg)
        elif x["status"] == "证据不足":
            fails.append(f"{x['id']} 证据不足（仅 {x['mutants']} 个变异体，0 杀不足以判定）")

    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "overall": overall, "mut_min": mut_min, "p0_mut_min": p0_mut_min,
        "min_mutants_for_zero": min_mutants_for_zero,
        "total_rules": len(rule_rows), "scored_rules": len(scored),
        "total_mutants": len(mutants), "valid_mutants": len(valid),
        "ignored_mutants": len(mutants) - len(valid),
        "killed": total_killed,
        "total_cases": len(cases), "scoped_cases": len(scoped),
        "rules": rule_rows, "unmeasurable": unmeasurable, "zero_strength": zero,
        "weak_evidence": weak_evidence,
        "zero_cases": zero_cases, "case_kills": case_kills,
        "mutants": valid, "kill_map": kill_map, "fails": fails,
        "p0_fails": p0_fails, "p0_rules": len(p0_rules),
        "pass": not fails,
    }


# ---------------------------------------------------------------- 渲染

def _pct(x):
    return "—" if x is None else f"{x*100:.0f}%"


def render_markdown(res, cases_path, reqs_path, scope="expected"):
    L = []
    a = L.append
    a("# 用例强度评审报告（需求层变异）")
    a("")
    a(f"- 生成时间：{res['generated_at']}")
    a(f"- 用例输入：`{cases_path}`　需求输入：`{reqs_path}`")
    a(f"- 匹配范围：`{scope}`（默认只看 expected；steps 不作为断言证据）")
    a(f"- 变异体：有效 {res['valid_mutants']} 个（等价白名单 {res['ignored_mutants']} 个不计入）")
    a(f"- 阈值：全局 ≥{res['mut_min']*100:.0f}% · P0 ≥{res['p0_mut_min']*100:.0f}% · 单规则 0 分即零强度")
    a(f"- **全局变异得分：{res['overall']*100:.1f}%**（{res['killed']}/{res['valid_mutants']}）")
    a("")
    a("> 口径：覆盖 = 有人测；强度 = 测得出错。两者都过才算真覆盖。")
    a("")

    a("## 一、总览")
    a("")
    a("| 模块 | 规则数 | 变异体 | 杀死 | 得分 | 零强度规则 | 判定 |")
    a("|---|---|---|---|---|---|---|")
    mods = {}
    for x in res["rules"]:
        d = mods.setdefault(norm_mod(x["module"]) or "(未分模块)", {"r": 0, "m": 0, "k": 0, "z": 0})
        d["r"] += 1
        d["m"] += x["mutants"]
        d["k"] += x["killed"]
        if x["status"] == "零强度":
            d["z"] += 1
    for m, d in mods.items():
        score = (d["k"] / d["m"]) if d["m"] else None
        verdict = "✅" if score is not None and score >= res["mut_min"] and not d["z"] else ("❌ 零强度" if d["z"] else "⚠️ 偏弱")
        a(f"| {m} | {d['r']} | {d['m']} | {d['k']} | {_pct(score)} | {d['z']} | {verdict} |")
    a("")

    a("## 二、零强度规则（最高优先级补充对象）")
    a("")
    if not res["zero_strength"]:
        a("- 无。所有规则均至少杀死 1 个变异体。")
    else:
        a("> 有覆盖但**一条错也测不出**。G1 的镜像：G1 是「没用例」，这里是「有用例但白测」。")
        a("")
        for x in sorted(res["zero_strength"], key=lambda y: (y["priority"] or "P9", y["id"])):
            a(f"### {x['id']}　{x['priority'] or '未定级'}　{x['module']}")
            a(f"**{x['text']}**　得分 0/{x['mutants']}")
            a("")
            a("| 存活变异体 | 算子 | 错误实现 | 要杀死它，预期必须具备 |")
            a("|---|---|---|---|")
            for s in x["survivors"]:
                a(f"| {s['mid']} | {OPERATOR_NAME.get(s['operator'], s['operator'])} | "
                  f"{s['wrong_claim']} | `{s['killer_pattern']}` |")
            a("")

    a("## 三、弱覆盖规则（得分 < 阈值）")
    a("")
    weak = [x for x in res["rules"] if x["status"] in ("偏弱", "P0 不达标")]
    if not weak:
        a("- 无。")
    else:
        a("| 规则 | 优先级 | 得分 | 存活变异体（错误实现） |")
        a("|---|---|---|---|")
        for x in sorted(weak, key=lambda y: (y["score"] if y["score"] is not None else 9)):
            surv = "；".join(s["wrong_claim"] for s in x["survivors"][:3]) or "—"
            a(f"| {x['id']} | {x['priority'] or '—'} | {_pct(x['score'])} | {surv} |")
        a("")

    a("## 三·五、证据不足（变异体过少，不作为结论）")
    a("")
    if not res.get("weak_evidence"):
        a("- 无。")
    else:
        a(f"> 这些规则只抽到 <{res.get('min_mutants_for_zero', 2)} 个变异体，0 杀**不能**说明整条规则弱，")
        a("> 只说明这一个错法没被测到。典型是「表格/矩阵型」规则——整表行为可能已有覆盖。")
        a("> 处理：补 `--semantic` 语义变异体后再判，或人工确认（不要据此删用例）。")
        a("")
        a("| 规则 | 优先级 | 变异体 | 存活的那一个错法 |")
        a("|---|---|---|---|")
        for x in res["weak_evidence"]:
            surv = "；".join(s["wrong_claim"] for s in x["survivors"][:1]) or "—"
            a(f"| {x['id']} | {x['priority'] or '—'} | {x['mutants']} | {surv} |")
        a("")

    a("## 四、零贡献用例（可合并 / 可补断言）")
    a("")
    if not res.get("scoped_cases"):
        a(f"> **无法界定评估范围**：全库 {res.get('total_cases', 0)} 条用例中，没有一条挂到本次评审的规则上，")
        a("> 也没有模块名能对上（常见于模块名是章节号、或需求集不完整）。此时「零贡献」没有意义，本节跳过。")
        a("> 处理方式：先补 `coverage_rule` 或修正需求侧的 `module`，再重跑。")
        a("")
    elif not res["zero_cases"]:
        a(f"- 无。评估范围内 {res['scoped_cases']} 条功能类用例都至少杀死 1 个变异体"
          f"（全库 {res.get('total_cases', 0)} 条）。")
    else:
        a(f"> 评估范围内 {res['scoped_cases']} 条用例（全库 {res.get('total_cases', 0)} 条）中，"
          f"有 {len(res['zero_cases'])} 条**杀不死任何变异体**——它们有覆盖记录但对发现错误零贡献。")
        a("> 两条出路：①补一条能区分对错的断言（优先）；②与同模块强用例合并。**不要**直接删，先确认是断言弱还是确实多余。")
        a("> 注意：范围外用例不参与判定（不同模块的用例本就不该杀死这些变异体）。")
        a("")
        a("| 用例编号 | 模块 | 名称 | 当前预期（节选） |")
        a("|---|---|---|---|")
        for z in res["zero_cases"]:
            a(f"| {z['id']} | {z['module']} | {z['name']} | {z['expected']} |")
        a("")

    # 有强度但 RTM 缺映射
    unmapped = [x for x in res["rules"] if x.get("unmapped_killers")]
    if unmapped:
        a("## 四·五、映射缺口（有用例能测，但没挂到规则上）")
        a("")
        a("| 规则 | 能测出错的用例 | 处理 |")
        a("|---|---|---|")
        for x in unmapped:
            ks = x["unmapped_killers"]
            shown = "、".join(ks[:5])
            more = f" 等 {len(ks)} 条" if len(ks) > 5 else ""
            a(f"| {x['id']} | {shown}{more} | 补 `coverage_rule` 或复核是否误挂 |")
        a("")

    a("## 五、不可测量规则（无法生成变异体）")
    a("")
    if not res["unmeasurable"]:
        a("- 无。")
    else:
        a("> 规则里既没有数值、也没有边界方向 / 否定 / 可观测动作 —— 这类规则通常**本身不可测**，")
        a("> 回推 Step 1 的 H1（禁止假设）：先把需求写具体，再谈用例。")
        a("")
        for x in res["unmeasurable"]:
            mark = "　`已豁免`（unmeasurable_accepted）" if x.get("accepted") else ""
            a(f"- `{x['id']}` [{x['module'] or '未分模块'}] {x['text']}{mark}")
        a("")
        a("> P0 规则若不可测量，**按未验证处理并阻断**；确实无法测的，在需求里加 `\"unmeasurable_accepted\": true` 登记豁免（须在检查点②说明理由）。")
        a("")
        a("")

    a("## 六、结论")
    a("")
    if res["pass"]:
        a(f"1. 全局变异得分 {res['overall']*100:.1f}%，达到 {res['mut_min']*100:.0f}% 阈值。")
        a("2. 无零强度规则、无 P0 规则低于阈值。")
        a("3. 可进入 Step 6 导出。零贡献用例建议按第四节处理（补断言优先于合并）。")
    else:
        a(f"1. 全局变异得分 {res['overall']*100:.1f}%（阈值 {res['mut_min']*100:.0f}%）。")
        for i, f in enumerate(res["fails"], 2):
            a(f"{i}. 不达标：{f}")
        n = len(res["fails"]) + 2
        a(f"{n}. **回填优先级**：零强度规则 → P0 弱覆盖 → 其余弱覆盖 → 零贡献用例。")
        a(f"{n+1}. 补的是「断言要素」（数值 / 边界两侧 / 否定结果 / 动作结果），不是「再写一条用例」。")
    a("")
    return "\n".join(L)


def render_json(res):
    def clean(x):
        return {k: (round(v, 4) if isinstance(v, float) else v) for k, v in x.items()}
    return json.dumps({
        "generated_at": res["generated_at"],
        "overall": round(res["overall"], 4),
        "mut_min": res["mut_min"], "p0_mut_min": res["p0_mut_min"],
        "total_mutants": res["total_mutants"], "valid_mutants": res["valid_mutants"],
        "ignored_mutants": res["ignored_mutants"], "killed": res["killed"],
        "total_cases": res.get("total_cases", 0), "scoped_cases": res.get("scoped_cases", 0),
        "p0_fails": res.get("p0_fails", []),
        "pass": res["pass"], "fails": res["fails"],
        "rules": [clean(x) for x in res["rules"]],
        "zero_strength_rules": [x["id"] for x in res["zero_strength"]],
        "weak_evidence_rules": [x["id"] for x in res["weak_evidence"]],
        "unmeasurable_rules": [x["id"] for x in res["unmeasurable"]],
        "zero_case_ids": [z["id"] for z in res["zero_cases"]],
    }, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------- CLI

def main():
    ap = argparse.ArgumentParser(
        description="需求层变异强度审计：用例 × requirements.json → 变异得分与零强度规则（EXPERIMENTAL）")
    ap.add_argument("cases", help="用例文件（.json / .xlsx）")
    ap.add_argument("requirements", help="requirements.json")
    ap.add_argument("-o", "--out", help="报告输出路径（默认打印到 stdout）")
    ap.add_argument("--format", choices=["markdown", "json"], default="markdown")
    ap.add_argument("--mut-min", type=float, default=DEFAULT_MUT_MIN,
                    help=f"全局变异得分达标线（默认 {DEFAULT_MUT_MIN}）")
    ap.add_argument("--p0-mut-min", type=float, default=DEFAULT_P0_MUT_MIN,
                    help=f"P0 规则得分达标线（默认 {DEFAULT_P0_MUT_MIN}）")
    ap.add_argument("--rule-floor-block", type=float, default=0.0,
                    help="单规则得分低于该值即判零强度（默认 0.0）")
    ap.add_argument("--mut-gate", choices=["p0", "warn", "block", "off"], default="p0",
                    help="闸门模式：p0=P0 规则不达标即阻断（v1.7.0 默认）/ warn 只出报告 / "
                         "block 任何不达标都阻断 / off 不判定")
    ap.add_argument("--max-per-rule", type=int, default=DEFAULT_MAX_PER_RULE,
                    help=f"每条规则自动生成变异体上限（默认 {DEFAULT_MAX_PER_RULE}）")
    ap.add_argument("--min-mutants-for-zero", type=int, default=DEFAULT_MIN_MUTANTS_FOR_ZERO,
                    help="变异体少于该数的规则判「证据不足」，不算零强度（默认 "
                         f"{DEFAULT_MIN_MUTANTS_FOR_ZERO}；设 1 则回到「有一个变异体算一个」）")
    ap.add_argument("--match-scope", choices=["expected", "expected+steps"], default="expected",
                    help="杀死判定的文本范围（默认 expected，避免 steps 里的枚举动作造成假杀死）")
    ap.add_argument("--semantic", metavar="PATH", help="语义变异体 JSON（ORD/STM/IDEM，可选）")
    ap.add_argument("--ignore", metavar="PATH", help="等价变异体白名单 JSON（mid 数组或 [{mid,reason}]）")
    ap.add_argument("--rule", action="append", help="只评审指定规则（可多次），用于 --explain 排查")
    ap.add_argument("--operators", metavar="LIST",
                    help="只用指定算子，逗号分隔（如 NUM,BND,NEG）；默认全部确定性算子")
    ap.add_argument("--explain", action="store_true", help="逐条打印变异体 pattern 与命中用例")
    args = ap.parse_args()

    try:
        cases = load_cases(args.cases)
        rules = load_rules(args.requirements)
    except Exception as e:
        print(f"[错误] 读取输入失败: {e}", file=sys.stderr)
        return 2
    if not cases:
        print("[错误] 未解析到任何用例", file=sys.stderr)
        return 2
    if not rules:
        print("[错误] 未解析到任何需求规则", file=sys.stderr)
        return 2

    ignore_ids = []
    for it in load_json_optional(args.ignore, "等价变异体白名单"):
        ignore_ids.append(it if isinstance(it, str) else it.get("mid"))
    semantic = load_json_optional(args.semantic, "语义变异体")

    ops = None
    if args.operators:
        ops = {x.strip().upper() for x in args.operators.split(",") if x.strip()}

    res = audit(cases, rules, max_per_rule=args.max_per_rule, semantic=semantic,
                ignore_ids=[i for i in ignore_ids if i], scope=args.match_scope,
                p0_mut_min=args.p0_mut_min, mut_min=args.mut_min,
                rule_floor_block=args.rule_floor_block,
                rule_filter=set(args.rule) if args.rule else None,
                operators=ops, min_mutants_for_zero=args.min_mutants_for_zero)

    if args.explain:
        print("=" * 78)
        print("变异体明细（--explain）：pattern 与命中用例")
        print("=" * 78)
        for m in res["mutants"]:
            kills = res["kill_map"].get(m["mid"], [])
            flag = "KILLED " if kills else "SURVIVE"
            print(f"[{flag}] {m['mid']}  {OPERATOR_NAME.get(m['operator'], m['operator'])}")
            print(f"         错误实现: {m['wrong_claim']}")
            print(f"         pattern : {m['killer_pattern']}")
            print(f"         命中用例: {', '.join(kills) if kills else '—'}")
        print("-" * 78)
        print(f"有效变异体 {res['valid_mutants']} 个，杀死 {res['killed']} 个，"
              f"得分 {res['overall']*100:.1f}%")
        print()

    text = render_markdown(res, args.cases, args.requirements, args.match_scope) \
        if args.format == "markdown" else render_json(res)

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text + "\n")
        print(f"[✓] 报告已写入 {args.out}")
    else:
        print(text)

    print(f"    全局变异得分 {res['killed']}/{res['valid_mutants']} "
          f"({res['overall']*100:.1f}%)，零强度规则 {len(res['zero_strength'])} 个，"
          f"零贡献用例 {len(res['zero_cases'])}/{res.get('scoped_cases', 0)} 条（评估范围内）",
          file=sys.stderr)

    if args.mut_gate == "off":
        return 0
    if args.mut_gate == "warn":
        if not res["pass"]:
            print(f"[警告] 强度未达标（warn 模式不阻断）：{'; '.join(res['fails'])}", file=sys.stderr)
        return 0
    if args.mut_gate == "p0":
        if not res.get("p0_rules"):
            # 没有 P0 规则时 p0 模式会静默变成"什么都不拦"——这比明确失败更危险，
            # 所以必须显式告警，让使用者知道闸门这次是空转的。
            print("[警告] 需求清单里没有 P0 规则（priority 未标或全为非 P0），"
                  "p0 模式本次不生效＝只出报告。建议在 requirements.json 补 priority。",
                  file=sys.stderr)
            if not res["pass"]:
                print(f"       （强度未达标项）：{'; '.join(res['fails'])}", file=sys.stderr)
            return 0
        if res["p0_fails"]:
            print(f"[阻断] P0 规则强度不达标：{'; '.join(res['p0_fails'])}", file=sys.stderr)
            print("       修法：按强度报告第二节补「断言要素」（数值/边界两侧/否定结果/动作结果），"
                  "不要靠新增用例凑数。", file=sys.stderr)
            return 1
        if not res["pass"]:
            print(f"[警告] 非 P0 项未达标（p0 模式不阻断）：{'; '.join(res['fails'])}", file=sys.stderr)
        return 0
    return 0 if res["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
