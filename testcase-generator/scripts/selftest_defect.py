#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
selftest_defect.py — defect_audit.py 离线自测（17 项断言，自包含 fixture）

对应《testcase-generator_优化方案_2026-11-09.md》7.1。
不联网、不读真实库、不依赖 openpyxl（除 CLI 用例外全部走内存 fixture）。

跑法：python selftest_defect.py
退出码：0 全绿 / 1 有失败
"""

import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import defect_audit as da   # noqa: E402

PASS, FAIL = [], []


def check(no, name, cond, detail=""):
    if cond:
        PASS.append(no)
        print(f"  [PASS] {no:>2}. {name}")
    else:
        FAIL.append((no, name))
        print(f"  [FAIL] {no:>2}. {name}   {detail}")


# ---------------------------------------------------------------- fixture

RAW_BUGS = [
    # B1 有现象、无强要素（"记录/保存"不算 ACT 里的强判别？——"保存"在 ACT_WORDS 里，故意只给
    #    expected 不含"保存"分句，用来验证「挂着拦不住」）
    {"id": "B1", "title": "【V1】【APP】【训练】训练完成后，训练记录未正确保存",
     "description": "<style>.a{font-size:18px}</style><p>2 次训练后记录丢失</p>",
     "severity": "serious", "resolution": "fixed", "regression_number": "0",
     "sourcephase": "测试"},
    # B2 动作类要素：弹出
    {"id": "B2", "title": "【V1】【APP】【训练】训练完成后无训练反馈弹出",
     "description": "", "severity": "normal", "resolution": "fixed",
     "regression_number": "0", "sourcephase": "测试"},
    # B3 逐字文案元素：应弹出「训练完成」
    {"id": "B3", "title": "【V1】【APP】【训练】训练结束后应弹出「训练完成」提示",
     "description": "", "severity": "normal", "resolution": "fixed",
     "regression_number": "0", "source": "线上"},
    # B4 被驳回 + 线上（若计入分母会把 DER 拉低）
    {"id": "B4", "title": "【V1】【APP】【训练】建议把两个界面合成一个",
     "description": "纯交互建议，不是缺陷", "severity": "advice", "resolution": "",
     "reject_time": "2026-05-01 10:00:00", "source": "线上"},
    # B5 只有标签，没有现象
    {"id": "B5", "title": "【V1】", "description": "", "severity": "normal",
     "resolution": "fixed", "sourcephase": "测试"},
    # B6 数值类要素：220（3 位，强）
    {"id": "B6", "title": "【V1】【APP】【训练】心率超过220未停止",
     "description": "", "severity": "fatal", "resolution": "fixed",
     "regression_number": "0", "sourcephase": "测试"},
    # B7 移动端登录：用于 L1 显式关联
    {"id": "B7", "title": "【V1】【移动端】【登录】验证码倒计时不起作用",
     "description": "", "severity": "normal", "resolution": "fixed",
     "regression_number": "0", "sourcephase": "测试"},
    # B8 模块同名但关键词完全不重合（"界面" 是泛词，会被 STOP_KW 过滤）
    {"id": "B8", "title": "【V1】【APP】【训练】界面颜色偏暗",
     "description": "", "severity": "normal", "resolution": "fixed",
     "regression_number": "0", "sourcephase": "测试"},
    # B9 与 B1 同 id，用于去重断言
    {"id": "B1", "title": "【V1】【APP】【训练】训练完成后，训练记录未正确保存",
     "description": "", "severity": "serious", "resolution": "fixed",
     "regression_number": "0", "sourcephase": "测试"},
]

CASES = [
    {"id": "TC-1", "module": "设备端-训练", "title": "训练完成后记录生成",
     "steps": "完成一次训练后返回", "expected": "记录生成完成后自动跳转至完成界面",
     "result": "", "defect": ""},
    {"id": "TC-2", "module": "设备端-训练", "title": "训练完成后弹出提示",
     "steps": "完成一次训练", "expected": "训练完成后弹出「训练完成」提示且训练记录保存成功",
     "result": "通过", "defect": ""},
    {"id": "TC-3", "module": "设备端-训练", "title": "训练中心率过高保护",
     "steps": "以心率 230 次/分持续训练", "expected": "心率达到 220 次/分时设备停止运行",
     "result": "", "defect": ""},
    {"id": "TC-4", "module": "移动端-登录", "title": "验证码倒计时校验",
     "steps": "获取验证码后等待", "expected": "倒计时结束后「重新获取」按钮恢复",
     "result": "", "defect": "B7"},
    {"id": "TC-5", "module": "设备端-训练", "title": "逐一遍历各训练模式",
     "steps": "逐一进入每个训练模式并完成", "expected": "逐一显示各模式名称且可进入",
     "result": "通过", "defect": ""},
]

MODULE_MAP = {"训练": "设备端-训练", "移动端/登录": "移动端-登录"}


def build(map_=None, prevented_mode="off"):
    bugs = [da.normalize_bug(b, map_) for b in da.dedupe_bugs(RAW_BUGS)]
    l1 = da.compute_layer1(bugs)
    l2 = da.compute_layer2(bugs, CASES, prevented_mode=prevented_mode)
    return bugs, l1, l2


def bug_row(l2, bid):
    for r in l2["rows"]:
        if r["id"] == bid:
            return r
    raise KeyError(bid)


def run_cli(bugs_path, cases_path=None, extra=None):
    cmd = [sys.executable, os.path.join(HERE, "defect_audit.py"), bugs_path]
    if cases_path:
        cmd.append(cases_path)
    cmd += ["--format", "json"] + (extra or [])
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    return p


# ---------------------------------------------------------------- 断言

def t_metrics(bugs, l1, l2):
    # ① DER 分母排除 undecidable（被驳回的 B4 带"线上"阶段，若计入会把 DER 拉低）
    ok = l1["der"] is not None and abs(l1["der"] - round(6 / 7, 4)) < 1e-9
    check(1, "DER 分母排除无效缺陷（6 测试 / 1 线上 → 6/7）", ok,
          f"der={l1['der']} probe={l1['probe']['phase_test']}/{l1['probe']['phase_online']}")

    # ② DLR = 1 − DER，方向相反
    ok = l1["dlr"] is not None and abs(l1["dlr"] - (1 - l1["der"])) < 1e-6 and l1["dlr"] < l1["der"]
    check(2, "DLR = 1 − DER 且方向正确", ok, f"der={l1['der']} dlr={l1['dlr']}")

    # ③ 同 id 去重（RAW_BUGS 里 B1 出现两次）
    ok = l1["total"] == len(set(b["id"] for b in RAW_BUGS))
    check(3, "缺陷按 id 去重（B1 重复导出只算 1）", ok,
          f"total={l1['total']} expect={len(set(b['id'] for b in RAW_BUGS))}")

    # ④ DDF 分子按用例去重：B1/B2 都只挂到 TC-1，不能算 2
    total_matches = sum(len(r["matched_cases"]) for r in l2["rows"])
    ok = l2["linked_cases"] < total_matches and \
        l2["linked_cases"] == len({c for r in l2["rows"] for c in r["matched_cases"]})
    check(4, "DDF 分子按用例去重（同一条用例被 2 个缺陷挂上只算 1）", ok,
          f"linked_cases={l2['linked_cases']} 累计匹配次数={total_matches}")


def t_verdict(bugs, l1, l2):
    # ⑤ 无任何关联用例 → escaped
    #    用不带模块归一副本时 B1 的模块"训练"在库里不存在
    _, _, l2n = build(None)
    r = bug_row(l2n, "B1")
    check(5, "无关联用例 → escaped", r["verdict"] == "escaped" and not r["matched_cases"],
          f"{r['verdict']} matched={r['matched_cases']} reason={r['reason']}")

    # ⑥ 有关联但 expected 无判别要素 → escaped（不得判 suspected / prevented）
    #    单独一组 fixture：缺陷只有"体验不好"（弱 NEG），用例 expected 只有"正常显示"
    raw = [{"id": "W1", "title": "【V1】【APP】【训练】训练完成后体验不好",
            "description": "", "resolution": "fixed", "sourcephase": "测试"}]
    cases = [{"id": "TC-W1", "module": "设备端-训练", "title": "训练完成后页面展示",
              "steps": "完成训练", "expected": "训练完成后页面正常显示", "result": "",
              "defect": ""}]
    nb = [da.normalize_bug(b, MODULE_MAP) for b in raw]
    l2w = da.compute_layer2(nb, cases)
    r = bug_row(l2w, "W1")
    check(6, "有关联但 expected 无断言要素 → escaped（不虚报拦住）",
          r["verdict"] == "escaped" and r["gap_type"] == "NEG"
          and r["matched_cases"] and not r["killed_by"],
          f"{r['verdict']} gap={r['gap_type']} killed={r['killed_by']} "
          f"matched={r['matched_cases']}")

    # ⑦ 强要素命中 → 默认 suspected；--prevented-mode auto 才 prevented
    rs = bug_row(l2, "B6")                        # 数值 220，TC-3 expected 含 220
    _, _, l2a = build(MODULE_MAP, prevented_mode="auto")
    ra = bug_row(l2a, "B6")
    check(7, "强要素命中 → 默认 suspected；prevented 需显式 auto",
          rs["verdict"] == "suspected" and ra["verdict"] == "prevented",
          f"默认={rs['verdict']} auto={ra['verdict']} killed={rs['killed_by']}")

    # ⑧ 标题只有标签、无现象描述 → undecidable
    r = bug_row(l2, "B5")
    check(8, "只有标签无现象 → undecidable（不硬判逃逸）",
          r["verdict"] == "undecidable", f"{r['verdict']} reason={r['reason']}")

    # ⑨ undecidable 不进分母，但计入 undecidable_rate
    ne = l2["evaluable"]
    ok = (l2["undecidable"] == 2 and l2["evaluable"] == l2["total"] - l2["undecidable"]
          and abs(l2["undecidable_rate"] - l2["undecidable"] / l2["total"]) < 1e-6
          and l2["escape_rate"] is not None and ne == 6)
    check(9, "undecidable 不进分母、计入 undecidable_rate", ok,
          f"total={l2['total']} undec={l2['undecidable']} evaluable={l2['evaluable']} "
          f"rate={l2['undecidable_rate']}")


def t_match(bugs, l1, l2):
    # ⑩ L1 显式关联（用例「关联缺陷」列写了 B7）
    r = bug_row(l2, "B7")
    check(10, "L1 显式关联命中（confidence=L1）",
          r["confidence"] == "L1" and "TC-4" in r["matched_cases"],
          f"conf={r['confidence']} matched={r['matched_cases']}")

    # ⑪ L2 模块同名但关键词不命中 → 不计入
    r = bug_row(l2, "B8")
    check(11, "模块同名但关键词不命中 → 不计入（防模块级泛匹配）",
          not r["matched_cases"] and r["verdict"] == "escaped",
          f"matched={r['matched_cases']} {r['verdict']}")

    # ⑫ L3 只作提示不改判决；阈值 0 关闭
    bug = [b for b in bugs if b["id"] == "B8"][0]
    hits_off = da.match_l3(bug, CASES, 0)
    hits_on = da.match_l3(bug, CASES, 0.01)
    check(12, "L3 只作提示不改判决（阈值 0 关闭，开启也不进 prevented）",
          hits_off == [] and isinstance(hits_on, list)
          and bug_row(l2, "B8")["verdict"] == "escaped",
          f"off={len(hits_off)} on={len(hits_on)}")

    # ⑬ 模块归一副本生效后 L2 才命中
    r_no = bug_row(build(None)[2], "B2")
    r_yes = bug_row(build(MODULE_MAP)[2], "B2")
    check(13, "模块归一副本生效后 L2 才可能命中",
          (not r_no["matched_cases"]) and r_yes["matched_cases"]
          and r_yes["confidence"] == "L2",
          f"无map={r_no['matched_cases']} 有map={r_yes['matched_cases']}/{r_yes['confidence']}")


def t_robust(bugs, l1, l2):
    tmp = tempfile.mkdtemp(prefix="defect_selftest_")
    empty = os.path.join(tmp, "empty.json")
    with open(empty, "w", encoding="utf-8") as f:
        json.dump({"data": []}, f)

    # ⑭ 缺陷 0 条 → 输出「无数据」且退出码 0
    p = run_cli(empty)
    md_cmd = [sys.executable, os.path.join(HERE, "defect_audit.py"), empty]
    pm = subprocess.run(md_cmd, capture_output=True, text=True, encoding="utf-8",
                        errors="replace")
    check(14, "缺陷 0 条 → 无数据报告 + 退出码 0（不报错）",
          p.returncode == 0 and "无缺陷数据" in pm.stdout,
          f"rc={p.returncode}")

    # ⑮ 用例库没有「关联缺陷 / coverage_rule」列 → 走文本匹配不崩
    cases_json = os.path.join(tmp, "cases.json")
    with open(cases_json, "w", encoding="utf-8") as f:
        json.dump([{"title": "训练完成后记录生成", "module": "设备端-训练",
                    "expected": "记录生成完成后自动跳转至完成界面"}], f, ensure_ascii=False)
    loaded = da.load_cases(cases_json)
    ok = len(loaded) == 1 and loaded[0]["defect"] == "" and loaded[0]["id"] == "ROW1"
    check(15, "用例库缺关联缺陷列 → 不崩，defect 为空", ok, str(loaded)[:120])

    # ⑯ 范围性用例标 range_case 且不进死用例候选
    rc = [c for c in CASES if c["id"] == "TC-5"][0]
    dead_ids = [d["id"] for d in l2["dead_case_candidates"]]
    ok = da.is_enum_case(rc) and "TC-5" not in dead_ids
    check(16, "枚举词用例识别为范围性用例，不进死用例候选",
          ok, f"is_enum={da.is_enum_case(rc)} dead={dead_ids}")

    # ⑰ --gate off / warn 恒退出码 0
    bugs_json = os.path.join(tmp, "bugs.json")
    with open(bugs_json, "w", encoding="utf-8") as f:
        json.dump({"data": [{"Bug": b} for b in RAW_BUGS]}, f, ensure_ascii=False)
    p_off = run_cli(bugs_json, cases_json, ["--layer", "1", "--gate", "off"])
    p_warn = run_cli(bugs_json, cases_json,
                     ["--layer", "2", "--gate", "warn", "--escaped-warn", "0.0"])
    check(17, "--gate off / warn 均不阻断（退出码 0）",
          p_off.returncode == 0 and p_warn.returncode == 0,
          f"off={p_off.returncode} warn={p_warn.returncode}")


def main():
    print("defect_audit.py 自测（17 项）")
    bugs, l1, l2 = build(MODULE_MAP)
    print("-- 指标口径 --")
    t_metrics(bugs, l1, l2)
    print("-- 四态判定 --")
    t_verdict(bugs, l1, l2)
    print("-- 匹配分级 --")
    t_match(bugs, l1, l2)
    print("-- 边界与健壮 --")
    t_robust(bugs, l1, l2)

    print()
    print(f"结果：{len(PASS)}/{len(PASS)+len(FAIL)} 通过")
    if FAIL:
        for no, name in FAIL:
            print(f"  失败 {no}. {name}")
        return 1
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
        print("\n[内部错误] selftest_defect.py 自身崩溃（exit 3），不是数据不达标。", file=sys.stderr)
        print("请把下面的堆栈连同输入样例一起报给技能维护者：", file=sys.stderr)
        traceback.print_exc()
        sys.exit(3)
