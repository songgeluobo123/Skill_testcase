#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
score_testcases.py — 测试用例结构化质量评分器

对生成的测试用例做首轮结构化自动评分，覆盖四维度：
  覆盖完整性(30%) + 准确性(25%) + 可执行性(25%) + 优先级合理性(20%)
评分 0-100；**每个维度均需 ≥ 阈值(默认 90)**，任一维度不足即标记并触发工作流回退重生成。

输入格式(JSON)：
{
  "cases": [
    {
      "id": "TC-001",
      "module": "登录",
      "priority": "P0",
      "precondition": "用户已注册且未登录",
      "steps": "在顶部导航栏点击右侧蓝色'登录'按钮，输入正确手机号与密码后点击登录",
      "test_data": { "手机号": "13800138000", "订单金额": "9.99", "用户等级": "VIP" },
      "expected": "登录成功并跳转至首页",
      "coverage_rule": "正常登录"
    }
  ]
}

用法：
  python score_testcases.py cases.json
  python score_testcases.py cases.json --threshold 90
  python score_testcases.py cases.json --rules my_rules.json
  cat cases.json | python score_testcases.py -

退出码：
  0  —— 全部用例每个维度均 >= 阈值（可交付）
  1  —— 存在用例任一维度 < 阈值（需回退重生成）
  2  —— 输入/参数错误
"""

import argparse
import json
import re
import sys


# 内置数据-规则映射库（可被 --rules 覆盖）。仅做结构化硬校验。
DEFAULT_DATA_RULES = {
    "手机号": {
        "type": "phone",
        "pattern": r"^1\d{10}$",   # 11 位数字，1 开头
        "hint": "需为 11 位数字",
    },
    "订单金额": {
        "type": "amount",
        "min": 0.01,
        "decimals": 2,
        "hint": "需为 >=0.01 的数值，保留 2 位小数",
    },
    "用户等级": {
        "type": "enum",
        "values": ["普通", "VIP", "SVIP"],
        "hint": "只能取 普通/VIP/SVIP",
    },
}

PRIORITIES = {"P0", "P1", "P2", "P3"}


def norm_priority(p):
    return (p or "").strip().upper()
WEIGHTS = {"coverage": 0.30, "accuracy": 0.25, "executability": 0.25, "priority": 0.20}


def load_cases(path):
    if path == "-":
        raw = sys.stdin.read()
    else:
        with open(path, "r", encoding="utf-8") as f:
            raw = f.read()
    data = json.loads(raw)
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and "cases" in data:
        return data["cases"]
    raise ValueError("输入 JSON 需为用例数组，或含 'cases' 键的对象")


def validate_data_value(key, value, rules):
    """按规则库校验一个测试数据取值，返回 (ok, reason)。未知字段不扣分。

    支持的规则类型（见 references/data_rules.json 模板）：
      phone  {pattern, hint}                     正则匹配（11 位手机号等）
      amount {min, decimals, hint}               数值下限 + 小数位上限
      range  {min, max, hint}                    数值区间（闭区间）
      length {min, max, hint}                    字符串长度区间
      regex  {pattern, hint}                     任意正则
      enum   {values, hint}                      枚举白名单
    """
    rule = rules.get(key)
    if rule is None:
        return True, ""
    hint = rule.get("hint") or key
    t = rule.get("type")

    if t == "phone":
        if re.match(rule["pattern"], str(value)):
            return True, ""
        return False, f"{key}='{value}' 不符合 {hint}"

    if t in ("amount", "range"):
        try:
            v = float(value)
        except (TypeError, ValueError):
            return False, f"{key}='{value}' 不是合法数值"
        lo = rule.get("min")
        hi = rule.get("max")
        if lo is not None and v < lo:
            return False, f"{key}={v} 小于最小值 {lo}"
        if hi is not None and v > hi:
            return False, f"{key}={v} 大于最大值 {hi}"
        if t == "amount":
            decimals = rule.get("decimals", 2)
            txt = str(value)
            if "." in txt and len(txt.split(".")[1]) > decimals:
                return False, f"{key}={value} 小数位超过 {decimals} 位"
        return True, ""

    if t == "length":
        n = len(str(value))
        lo = rule.get("min", 0)
        hi = rule.get("max", 10 ** 9)
        if not (lo <= n <= hi):
            return False, f"{key}='{value}' 长度 {n} 不在 [{lo},{hi}]"
        return True, ""

    if t == "regex":
        ok = bool(re.search(rule["pattern"], str(value)))
        return (True, "") if ok else (False, f"{key}='{value}' 不符合 {hint}")

    if t == "enum":
        if value in rule["values"]:
            return True, ""
        return False, f"{key}='{value}' 不在枚举 {rule['values']}"

    # 未知 type 不静默放行：规则写错了要能看见，否则等于没配
    return False, f"{key} 的规则 type='{t}' 不受支持（只认 phone/amount/range/length/regex/enum）"


def score_case(case, rules):
    issues = []

    # 1) 覆盖完整性 (30%)
    mod = (case.get("module") or "").strip()
    cov = (case.get("coverage_rule") or "").strip()
    coverage = (40 if mod else 0) + (60 if cov else 0)
    if not mod:
        issues.append("缺少 module（所属模块），覆盖完整性不足")
    if not cov:
        issues.append("缺少 coverage_rule（覆盖的需求规则），无法确认场景对应需求")

    # 2) 准确性 (25%)
    expected = (case.get("expected") or "").strip()
    steps = (case.get("steps") or "").strip()
    accuracy = 100 if expected else 0
    if not expected:
        issues.append("缺少 expected（预期结果），准确性无法判定")
    # 轻量矛盾检测：步骤含'正确'但预期含'失败/错误'
    if re.search(r"正确", steps) and re.search(r"(失败|错误|不通过)", expected):
        accuracy = min(accuracy, 40)
        issues.append("疑似矛盾：步骤含'正确'但预期结果为失败/错误")

    # 3) 可执行性 (25%)
    pre = (case.get("precondition") or "").strip()
    exec_score = 0
    exec_score += 40 if pre else 0
    if not pre:
        issues.append("缺少 precondition（前置条件），可执行性不足")
    if steps:
        exec_score += 40 if len(steps) >= 15 else 20
        if len(steps) < 15:
            issues.append("steps 过短，步骤可能不清晰/不可操作")
        # 模糊步骤启发式：只说'点击按钮'未说明位置
        if "点击" in steps and "按钮" in steps and not ("导航" in steps or "页面" in steps or "右侧" in steps or "左侧" in steps):
            exec_score = max(0, exec_score - 20)
            issues.append("步骤含'点击按钮'但未说明位置，存在歧义")
    else:
        issues.append("缺少 steps（测试步骤）")

    # 测试数据有效性
    data = case.get("test_data") or {}
    data_ok = True
    if data:
        for k, v in data.items():
            ok, reason = validate_data_value(k, v, rules)
            if not ok:
                data_ok = False
                issues.append(reason)
        exec_score += 20 if data_ok else 0
    else:
        # 无数据不强制扣分，但提示
        issues.append("无 test_data，若用例需要数据请补充以保证可执行性")

    executability = min(100, exec_score)

    # 4) 优先级合理性 (20%)
    pri = norm_priority(case.get("priority"))
    priority_score = 100 if pri in PRIORITIES else 0
    if pri not in PRIORITIES:
        issues.append(f"priority='{case.get('priority')}' 非法，需为 P0/P1/P2/P3")

    total = (
        WEIGHTS["coverage"] * coverage
        + WEIGHTS["accuracy"] * accuracy
        + WEIGHTS["executability"] * executability
        + WEIGHTS["priority"] * priority_score
    )
    total = round(total, 1)

    return {
        "id": case.get("id", "?"),
        "score": total,
        "breakdown": {
            "coverage": coverage,
            "accuracy": accuracy,
            "executability": executability,
            "priority": priority_score,
        },
        "issues": issues,
    }


def main():
    ap = argparse.ArgumentParser(description="测试用例结构化质量评分器")
    ap.add_argument("input", help="用例 JSON 文件路径，或 '-' 读取 stdin")
    ap.add_argument("--threshold", type=float, default=90.0, help="每个维度合格阈值，默认 90")
    ap.add_argument("--rules", help="可选：自定义数据-规则映射库 JSON 路径（模板见 "
                                    "references/data_rules.json）")
    ap.add_argument("--rules-mode", choices=["merge", "replace"], default="merge",
                    help="--rules 与内置规则的关系：merge=合并（默认，保留内置三条）；"
                         "replace=整体替换（早期行为，会静默丢掉内置规则，只在明确要时才用）")
    ap.add_argument("--quiet", action="store_true", help="只输出结论，不打印提示")
    args = ap.parse_args()

    try:
        cases = load_cases(args.input)
    except Exception as e:
        print(f"[错误] 读取/解析输入失败: {e}", file=sys.stderr)
        return 2

    rules = dict(DEFAULT_DATA_RULES)
    if args.rules:
        try:
            with open(args.rules, "r", encoding="utf-8") as f:
                ext = json.load(f)
        except Exception as e:
            print(f"[错误] 读取规则文件失败: {e}", file=sys.stderr)
            return 2
        if not isinstance(ext, dict):
            print("[错误] 规则文件需为对象：{\"字段名\": {\"type\": ...}}", file=sys.stderr)
            return 2
        if args.rules_mode == "replace":
            rules = ext
        else:
            # 默认**合并**：只写项目自己的字段，不清掉内置的三条。
            # 早期是整体替换，项目一传 --rules，手机号/订单金额/用户等级就不再校验了，
            # 而且没有任何提示——配了规则反而丢掉规则，比不配更危险。
            rules.update(ext)
        if not args.quiet:
            if args.rules_mode == "replace":
                print(f"[i] 数据规则库：{len(rules)} 条（--rules-mode replace，"
                      f"内置 {len(DEFAULT_DATA_RULES)} 条已被丢弃）")
            else:
                print(f"[i] 数据规则库：内置 {len(DEFAULT_DATA_RULES)} 条 + 外部 {len(ext)} 条"
                      f" = {len(rules)} 条（--rules-mode merge）")

    if not cases:
        print("[警告] 未找到任何用例", file=sys.stderr)
        return 2

    results = [score_case(c, rules) for c in cases]
    avg = round(sum(r["score"] for r in results) / len(results), 1)
    def _case_failed(r):
        return any(v < args.threshold for v in r["breakdown"].values())
    failed = [r for r in results if _case_failed(r)]

    print(f"=== 测试用例质量评分（每项维度需 ≥ {args.threshold}，平均总分 {avg}）===\n")
    for r in results:
        failed_case = any(v < args.threshold for v in r["breakdown"].values())
        flag = "✗ 不通过" if failed_case else "✓ 通过"
        print(f"[{flag}] {r['id']}  总分 {r['score']}")
        bd = r["breakdown"]
        dim_labels = {"coverage": "覆盖", "accuracy": "准确",
                      "executability": "可执行", "priority": "优先级"}
        parts = []
        for dim in ("coverage", "accuracy", "executability", "priority"):
            mark = " ⚠低于阈值" if bd[dim] < args.threshold else ""
            parts.append(f"{dim_labels[dim]} {bd[dim]}{mark}")
        print("    分解: " + " | ".join(parts))
        for it in r["issues"]:
            print(f"    - 问题: {it}")
        print()

    print(f"汇总: 共 {len(results)} 条，合格 {len(results) - len(failed)} 条，"
          f"需重生成 {len(failed)} 条。")

    return 1 if failed else 0


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
        print("\n[内部错误] score_testcases.py 自身崩溃（exit 3），不是数据不达标。", file=sys.stderr)
        print("请把下面的堆栈连同输入样例一起报给技能维护者：", file=sys.stderr)
        traceback.print_exc()
        sys.exit(3)
