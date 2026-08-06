#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
score_testcases.py — 测试用例结构化质量评分器

对生成的测试用例做首轮结构化自动评分，覆盖四维度：
  覆盖完整性(30%) + 准确性(25%) + 可执行性(25%) + 优先级合理性(20%)
评分 0-100；低于阈值(默认 70)的用例会被标记并触发工作流回退重生成。

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
  python score_testcases.py cases.json --threshold 70
  python score_testcases.py cases.json --rules my_rules.json
  cat cases.json | python score_testcases.py -

退出码：
  0  —— 全部用例 >= 阈值（可交付）
  1  —— 存在用例 < 阈值（需回退重生成）
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

PRIORITIES = {"P1", "P2", "P3", "P4"}


def norm_priority(p):
    p = (p or "").strip().upper()
    if p == "P0":
        return "P1"
    return p
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
    """返回 (ok, reason)。未知字段不扣分。"""
    rule = rules.get(key)
    if rule is None:
        return True, ""
    if rule["type"] == "phone":
        if re.match(rule["pattern"], str(value)):
            return True, ""
        return False, f"{key}='{value}' 不符合 {rule['hint']}"
    if rule["type"] == "amount":
        try:
            v = float(value)
        except (TypeError, ValueError):
            return False, f"{key}='{value}' 不是合法数值"
        if v < rule["min"]:
            return False, f"{key}={v} 小于最小值 {rule['min']}"
        txt = str(value)
        if "." in txt and len(txt.split(".")[1]) > rule["decimals"]:
            return False, f"{key}={value} 小数位超过 {rule['decimals']} 位"
        return True, ""
    if rule["type"] == "enum":
        if value in rule["values"]:
            return True, ""
        return False, f"{key}='{value}' 不在枚举 {rule['values']}"
    return True, ""


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
        issues.append(f"priority='{case.get('priority')}' 非法，需为 P1/P2/P3/P4（旧 P0 已归一为 P1）")

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
    ap.add_argument("--threshold", type=float, default=70.0, help="合格阈值，默认 70")
    ap.add_argument("--rules", help="可选：自定义数据-规则映射库 JSON 路径")
    args = ap.parse_args()

    try:
        cases = load_cases(args.input)
    except Exception as e:
        print(f"[错误] 读取/解析输入失败: {e}", file=sys.stderr)
        return 2

    rules = DEFAULT_DATA_RULES
    if args.rules:
        try:
            with open(args.rules, "r", encoding="utf-8") as f:
                rules = json.load(f)
        except Exception as e:
            print(f"[错误] 读取规则文件失败: {e}", file=sys.stderr)
            return 2

    if not cases:
        print("[警告] 未找到任何用例", file=sys.stderr)
        return 2

    results = [score_case(c, rules) for c in cases]
    avg = round(sum(r["score"] for r in results) / len(results), 1)
    failed = [r for r in results if r["score"] < args.threshold]

    print(f"=== 测试用例质量评分（阈值 {args.threshold}，平均 {avg}）===\n")
    for r in results:
        flag = "✗ 不通过" if r["score"] < args.threshold else "✓ 通过"
        print(f"[{flag}] {r['id']}  总分 {r['score']}")
        print(f"    分解: 覆盖 {r['breakdown']['coverage']} | "
              f"准确 {r['breakdown']['accuracy']} | "
              f"可执行 {r['breakdown']['executability']} | "
              f"优先级 {r['breakdown']['priority']}")
        for it in r["issues"]:
            print(f"    - 问题: {it}")
        print()

    print(f"汇总: 共 {len(results)} 条，合格 {len(results) - len(failed)} 条，"
          f"需重生成 {len(failed)} 条。")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
