#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""mutation_audit.py 自测（自包含，无外部 fixture 依赖）。

16 项断言分两组：
  A. 固定基线——用内置的 6 条需求 × 8 条用例，钉住变异得分与清单。
     这些数字漂移必须是有意识的（否则说明算子或匹配口径被无意放宽）。
  B. 防假杀死 / 防口径漂移——弱预期必须判 survive、强预期必须判 killed、
     等价白名单必须改分母、p0 模式只卡 P0、无 P0 规则时不得静默空转。

用法：python scripts/selftest_mutation.py
"""
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "mutation_audit.py")
PY = sys.executable

RULES = [
    {"id": "R-101", "module": "登录", "priority": "P0",
     "text": "密码连续输入错误5次，账号锁定10分钟，锁定期间输入正确密码也不允许登录"},
    {"id": "R-102", "module": "登录", "priority": "P1",
     "text": "验证码有效期为60秒，过期后需重新获取，且旧验证码不可复用"},
    {"id": "R-103", "module": "登录", "priority": "P1",
     "text": "未登录用户访问订单详情页，应跳转登录页并在登录后回跳原访问地址"},
    {"id": "R-201", "module": "支付", "priority": "P0",
     "text": "单笔订单金额超过5000元需二次短信验证，5000元及以下免验证"},
    {"id": "R-202", "module": "支付", "priority": "P1",
     "text": "支付超时时间为15分钟，超时后订单自动关闭并释放库存"},
    {"id": "R-301", "module": "搜索", "priority": "P2",
     "text": "搜索关键词最大长度50字符，超出部分截断并提示；空关键词返回热门搜索"},
]

CASES = [
    {"id": "TC-LOGIN-001", "name": "连续输错密码后账号锁定", "module": "登录",
     "priority": "P0", "test_type": "异常", "design_method": "边界值分析",
     "coverage_rule": "R-101", "steps": "在登录页输入已注册手机号，连续5次输入错误密码并点击登录",
     "expected": "应提示账号已锁定，登录失败", "test_data": {"手机号": "13800000001"}},
    {"id": "TC-LOGIN-002", "name": "锁定期间正确密码登录", "module": "登录",
     "priority": "P0", "test_type": "异常", "design_method": "场景法",
     "coverage_rule": "R-101", "steps": "在登录页输入已锁定账号与正确密码并点击登录",
     "expected": "应仍提示账号已锁定，不允许登录", "test_data": {"手机号": "13800000001"}},
    {"id": "TC-LOGIN-003", "name": "验证码过期后登录", "module": "登录",
     "priority": "P1", "test_type": "异常", "design_method": "边界值分析",
     "coverage_rule": "R-102", "steps": "等待验证码过期后在登录页输入该验证码并点击登录",
     "expected": "应提示验证码已过期，请重新获取", "test_data": {"验证码": "123456"}},
    {"id": "TC-LOGIN-004", "name": "未登录访问订单详情", "module": "登录",
     "priority": "P1", "test_type": "异常", "design_method": "场景法",
     "coverage_rule": "R-103", "steps": "在浏览器直接访问订单详情页地址",
     "expected": "应跳转至登录页", "test_data": {"订单号": "SO20261102001"}},
    {"id": "TC-PAY-001", "name": "大额订单二次短信验证", "module": "支付",
     "priority": "P0", "test_type": "功能", "design_method": "边界值分析",
     "coverage_rule": "R-201", "steps": "提交金额大于5000元的订单并点击支付",
     "expected": "应弹出短信验证弹窗，未验证不可支付", "test_data": {"订单金额": "6000"}},
    {"id": "TC-PAY-002", "name": "支付超时订单关闭", "module": "支付",
     "priority": "P1", "test_type": "异常", "design_method": "场景法",
     "coverage_rule": "R-202", "steps": "提交订单后等待超时并查询订单状态",
     "expected": "应提示订单已关闭", "test_data": {"订单号": "SO20261102002"}},
    {"id": "TC-SEARCH-001", "name": "超长关键词搜索", "module": "搜索",
     "priority": "P2", "test_type": "边界", "design_method": "边界值分析",
     "coverage_rule": "R-301", "steps": "在搜索框输入超长关键词并点击搜索",
     "expected": "应提示关键词过长", "test_data": {"关键词": "60字符字符串"}},
    {"id": "TC-SEARCH-002", "name": "空关键词搜索", "module": "搜索",
     "priority": "P2", "test_type": "异常", "design_method": "等价类划分",
     "coverage_rule": "R-301", "steps": "在搜索框不输入内容直接点击搜索",
     "expected": "应展示热门搜索列表", "test_data": {"关键词": ""}},
]

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(("[PASS] " if cond else "[FAIL] ") + name + (f"  {detail}" if detail else ""))


def run(args, td):
    out = os.path.join(td, "r.json")
    p = subprocess.run([PY, SCRIPT] + args + ["--format", "json", "-o", out],
                       capture_output=True, text=True, encoding="utf-8")
    data = None
    if os.path.exists(out):
        try:
            with open(out, encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError:
            data = None
    return p.returncode, data, (p.stderr or "") + (p.stdout or "")


def dump(name, obj, td):
    p = os.path.join(td, name)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False)
    return p


def main():
    with tempfile.TemporaryDirectory() as td:
        rp = dump("requirements.json", RULES, td)
        cp = dump("test_cases.json", {"cases": CASES}, td)

        # ---------------- A. 固定基线
        code, base, log = run([cp, rp, "--mut-gate", "warn"], td)
        check("A1 JSON 报告可解析", base is not None, "" if base else log[-300:])
        if base:
            check("A2 自动抽出有效变异体 ≥ 12", base["valid_mutants"] >= 12,
                  f"实际 {base['valid_mutants']}")
            check("A3 全局变异得分 == 4/19 (21.1%)",
                  abs(base["overall"] - 4 / 19) < 0.001, f"实际 {base['overall']*100:.1f}%")
            check("A4 零强度规则 == {R-102, R-201}（R-103 仅 1 个变异体→证据不足）",
                  set(base["zero_strength_rules"]) == {"R-102", "R-201"}
                  and base.get("weak_evidence_rules") == ["R-103"],
                  f"零强度 {base['zero_strength_rules']} / 证据不足 {base.get('weak_evidence_rules')}")
            check("A5 零贡献用例 == 5 条（含 TC-LOGIN-001：只验证提示文案≠锁定生效）",
                  set(base["zero_case_ids"]) == {"TC-LOGIN-001", "TC-LOGIN-003",
                                                 "TC-LOGIN-004", "TC-PAY-001",
                                                 "TC-SEARCH-001"},
                  str(base["zero_case_ids"]))
            check("A6 warn 模式不阻断（退出码 0）", code == 0, f"退出码 {code}")
            r101 = next((r for r in base["rules"] if r["id"] == "R-101"), None)
            check("A7 R-101(P0) 50% 被判 P0 不达标",
                  r101 is not None and r101["status"] == "P0 不达标" and not base["pass"],
                  r101["status"] if r101 else "缺失")

        # ---------------- B. 防假杀死 / 口径
        weak_rules = [{"id": "R-901", "module": "弱断言", "priority": "P1",
                       "text": "密码错误5次锁定10分钟"}]
        weak_cases = [{"id": "TC-W-001", "name": "锁定提示", "module": "弱断言",
                       "priority": "P1", "test_type": "异常",
                       "steps": "连续5次输入错误密码后登录",
                       "expected": "应提示账号已锁定", "test_data": {"密码": "x"},
                       "coverage_rule": "R-901", "design_method": ["边界值分析"]}]
        wr = dump("wr.json", weak_rules, td)
        wc = dump("wc.json", {"cases": weak_cases}, td)
        _, wres, _ = run([wc, wr], td)
        check("B1 只写功能名的弱预期 → 得分 0（fake-kill 拦住）",
              wres is not None and wres["overall"] == 0.0 and wres["killed"] == 0,
              f"得分 {wres['overall'] if wres else '?'}")

        strong = json.loads(json.dumps(weak_cases))
        strong.append({
            "id": "TC-W-002", "name": "第4次不锁定", "module": "弱断言",
            "priority": "P1", "test_type": "边界",
            "steps": "连续输入3次错误密码后再输入第4次错误密码",
            "expected": "第4次输错后应仍停留在登录页且不出现锁定提示",
            "test_data": {"密码": "x"}, "coverage_rule": "R-901",
            "design_method": ["边界值分析"]})
        sc = dump("sc.json", {"cases": strong}, td)
        _, sres, _ = run([sc, wr], td)
        check("B2 强断言（第4次不锁定）→ 至少杀死 1 个变异体",
              sres is not None and sres["killed"] >= 1,
              f"killed={sres['killed'] if sres else '?'}")

        if base and base["valid_mutants"]:
            p = subprocess.run([PY, SCRIPT, cp, rp, "--explain", "--rule", "R-102"],
                               capture_output=True, text=True, encoding="utf-8")
            mids = [ln.split()[1] for ln in p.stdout.splitlines()
                    if ln.startswith("[") and "]" in ln and len(ln.split()) > 1]
            if mids:
                ig = dump("ig.json", [{"mid": mids[0], "reason": "自测用等价变异体"}], td)
                _, ires, _ = run([cp, rp, "--ignore", ig], td)
                check("B3 等价白名单使分母 -1",
                      ires is not None and
                      ires["valid_mutants"] == base["valid_mutants"] - 1,
                      f"{ires['valid_mutants'] if ires else '?'} vs {base['valid_mutants']}")
            else:
                check("B3 等价白名单使分母 -1", False, "未能从 --explain 取到 mid")

        code_b, _, _ = run([cp, rp, "--mut-gate", "block"], td)
        check("B4 block 模式未达标 → 退出码 1", code_b == 1, f"退出码 {code_b}")

        code_o, _, _ = run([cp, rp, "--mut-gate", "off"], td)
        check("B5 off 模式 → 退出码 0", code_o == 0, f"退出码 {code_o}")

        code_p0, pres_p0, _ = run([cp, rp, "--mut-gate", "p0"], td)
        p0f = (pres_p0 or {}).get("p0_fails", [])
        check("B6 p0 模式：P0 规则 50% < 90% → 退出码 1 且点名 R-101",
              code_p0 == 1 and any("R-101" in x for x in p0f),
              f"退出码 {code_p0}；p0_fails={p0f}")

        p1_rules = [{"id": "R-903", "module": "弱断言P1", "priority": "P1",
                     "text": "密码错误5次锁定10分钟"}]
        p1_cases = [dict(weak_cases[0], id="TC-P1-001", module="弱断言P1",
                         coverage_rule="R-903")]
        p1r = dump("p1r.json", p1_rules, td)
        p1c = dump("p1c.json", {"cases": p1_cases}, td)
        code_p1_p0, _, _ = run([p1c, p1r, "--mut-gate", "p0"], td)
        code_p1_blk, _, _ = run([p1c, p1r, "--mut-gate", "block"], td)
        check("B7 p0 模式放过非 P0 未达标（0）而 block 仍拦（1）",
              code_p1_p0 == 0 and code_p1_blk == 1,
              f"p0={code_p1_p0} block={code_p1_blk}")

        code_def, _, _ = run([cp, rp], td)
        check("B8 默认模式 = p0（含 P0 不达标 → 退出码 1）", code_def == 1,
              f"退出码 {code_def}")

        noP_rules = [{"id": "R-904", "module": "无优先级", "text": "密码错误5次锁定10分钟"}]
        noP_cases = [dict(weak_cases[0], id="TC-NP-001", module="无优先级",
                          coverage_rule="R-904")]
        npr = dump("npr.json", noP_rules, td)
        npc = dump("npc.json", {"cases": noP_cases}, td)
        code_np, _, log_np = run([npc, npr, "--mut-gate", "p0"], td)
        check("B9 无 P0 规则时 p0 模式不静默空转（退出码 0 + 告警）",
              code_np == 0 and "没有 P0 规则" in log_np, f"退出码 {code_np}")

        vague_rules = [{"id": "R-902", "module": "空话", "priority": "P2",
                        "text": "整体体验流畅，交互友好"}]
        vr = dump("vr.json", vague_rules, td)
        vc = dump("vc.json", {"cases": [{"id": "TC-V-001", "name": "体验", "module": "空话",
                                         "priority": "P2", "steps": "使用产品",
                                         "expected": "应流畅", "test_data": {"x": 1}}]}, td)
        _, vres, _ = run([vc, vr], td)
        check("B10 空话规则进「不可测量规则」",
              vres is not None and vres["unmeasurable_rules"] == ["R-902"],
              str(vres["unmeasurable_rules"] if vres else "?"))

        # B11 无「用例编号」列时：每行必须有独立键，不能全部塌成同一个 "(无编号)"
        # （真实库 2405 条无编号，塌键会让"一条杀死"变成"全部杀死"，得分虚高且零贡献失效）
        noid = [{"id": "", "name": "弱", "module": "无编号", "priority": "P1",
                 "test_type": "异常", "steps": "输错5次", "expected": "应提示账号已锁定",
                 "test_data": {"x": 1}, "coverage_rule": "R-905"},
                {"id": "", "name": "强", "module": "无编号", "priority": "P1",
                 "test_type": "边界", "steps": "第4次输错",
                 "expected": "第4次输错后应仍停留在登录页且不出现锁定提示",
                 "test_data": {"x": 2}, "coverage_rule": "R-905"}]
        nr = dump("nr.json", [{"id": "R-905", "module": "无编号", "priority": "P1",
                              "text": "密码错误5次锁定10分钟"}], td)
        nc = dump("nc.json", {"cases": noid}, td)
        _, nres, _ = run([nc, nr], td)
        got = (nres or {}).get("zero_case_ids", [])
        check("B11 无编号用例按行号区分（仅弱用例计零贡献，不被强用例连带）",
              got == ["第2行"] and nres["killed"] == 2,
              f"zero={got} killed={nres['killed'] if nres else '?'}")

        # B12 NUM 反证式边界断言：实现把 3s 改成 2s 时，「未达 3s 不该播」要能杀死它
        # （真实库原写法，上一版会误判为"杀不死"→ 好用例被打成零贡献）
        num_rules = [{"id": "R-906", "module": "反证", "priority": "P1",
                      "text": "热身开始：进入热身阶段3s后播报"}]
        num_cases = [{"id": "TC-NU-001", "name": "未达3s不播", "module": "反证",
                      "priority": "P1", "test_type": "边界", "steps": "进入热身阶段后计时",
                      "expected": "计时未达3s时无任何热身开始播报输出",
                      "test_data": {"x": 1}, "coverage_rule": "R-906"}]
        nur = dump("nur.json", num_rules, td)
        nuc = dump("nuc.json", {"cases": num_cases}, td)
        _, nu_res, _ = run([nuc, nur], td)
        check("B12 反证式边界断言（未达3s不播）能杀死「阈值调小」变异体",
              nu_res is not None and nu_res["killed"] >= 1,
              f"killed={nu_res['killed'] if nu_res else '?'}/{nu_res['valid_mutants'] if nu_res else '?'}")

        # B13 NEG 变体：规则写「不允许出现」，用例写「不出现」也要能杀死
        neg_rules = [{"id": "R-907", "module": "否定变体", "priority": "P1",
                      "text": "本期不允许出现课程播一次加系统播一次"}]
        neg_cases = [{"id": "TC-NG-001", "name": "仅一条", "module": "否定变体",
                      "priority": "P1", "test_type": "功能", "steps": "同时触发课程与系统事件",
                      "expected": "该时间点仅形成一条有效主播报，不出现课程播一次加系统播一次",
                      "test_data": {"x": 1}, "coverage_rule": "R-907"}]
        ngr = dump("ngr.json", neg_rules, td)
        ngc = dump("ngc.json", {"cases": neg_cases}, td)
        _, ng_res, _ = run([ngc, ngr], td)
        check("B13 用例写「不出现」能杀死「不允许出现」变异体",
              ng_res is not None and ng_res["killed"] >= 1,
              f"killed={ng_res['killed'] if ng_res else '?'}/{ng_res['valid_mutants'] if ng_res else '?'}")

        # B14 防误杀：规则复述式断言「超过5000元需验证」不得杀死「阈值改 5001」变异体
        fk_rules = [{"id": "R-908", "module": "防误杀", "priority": "P1",
                     "text": "单笔订单金额超过5000元需二次短信验证"}]
        fk_cases = [{"id": "TC-FK-001", "name": "大额验证", "module": "防误杀",
                     "priority": "P1", "test_type": "功能", "steps": "提交 6000 元订单",
                     "expected": "超过5000元的订单应弹出短信验证弹窗",
                     "test_data": {"金额": "6000"}, "coverage_rule": "R-908"}]
        fkr = dump("fkr.json", fk_rules, td)
        fkc = dump("fkc.json", {"cases": fk_cases}, td)
        _, fk_res, _ = run([fkc, fkr], td)
        check("B14 规则复述式断言不得误杀「阈值微调」变异体",
              fk_res is not None and fk_res["killed"] < fk_res["valid_mutants"],
              f"killed={fk_res['killed'] if fk_res else '?'}/{fk_res['valid_mutants'] if fk_res else '?'}")

    print("-" * 60)
    print(f"通过 {len(PASS)} / {len(PASS)+len(FAIL)}")
    if FAIL:
        print("失败项：" + "；".join(FAIL))
    return 0 if not FAIL else 1


if __name__ == "__main__":
    sys.exit(main())
