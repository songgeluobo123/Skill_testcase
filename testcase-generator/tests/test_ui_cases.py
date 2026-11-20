"""第 7b 项（UI 族附加判据）回归。

判据与阈值全部锚定优秀库实测（1278 条）：
  - UI 族 509 条的预期只有 45% 含**具体视觉值词**（置灰/居中/黑色…），
    所以「每条必须含视觉词」的一刀切会把优秀库一半打脸 —— 该强规则**不成立**。
  - 成立的是两条结构性判据：
    A. 标题声明「UI 元素」清单 → 预期必须真枚举（编号 ≥2 项），只写一句"显示完整"是壳；
    B. 预期**提了样式**（颜色/布局/对齐/字号…）却给不出具体视觉值、
       也没有「与设计稿一致」兜底 → 与「正常显示」同级不可判定（fail）。
  - 不可判定黑名单（美观/合理…）对 UI 族同样一票否决——优秀库里也有
    「UI 布局美观」这种 P4 反例，不能因为类型是 UI 就放行。
"""
import json
import os
import subprocess
import sys
import tempfile

SKILL = os.environ.get("TC_SKILL") or os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(SKILL, "scripts", "prescreen.py")
PY = sys.executable
TMP = tempfile.mkdtemp(prefix="ui_cases_")

PASS = FAIL = 0
FAILS = []


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"PASS {name}")
    else:
        FAIL += 1
        FAILS.append(name)
        print(f"FAIL {name}  {detail}")


def mk(cid, title, ttype, exp, module="订单"):
    return {"id": cid, "name": title, "module": module, "priority": "P1",
            "test_type": ttype, "precondition": "已登录",
            "steps": "1. 进入页面\n2. 点击按钮",
            "expected": exp, "test_data": {"账号": "test01"},
            "coverage_rule": "R-001", "design_method": ["场景法"]}


RELAX = ["--coverage-min", "0", "--p0-min", "0", "--p0-max", "1",
         "--p2-min", "0", "--p2-max", "1", "--scene-min-cases", "99"]


def run(cases, tag, rules=None):
    p = os.path.join(TMP, f"{tag}.json")
    json.dump(cases, open(p, "w", encoding="utf-8"), ensure_ascii=False)
    cmd = [PY, SCRIPT, p] + RELAX
    if rules:
        rp = os.path.join(TMP, "rules.json")
        json.dump(rules, open(rp, "w", encoding="utf-8"), ensure_ascii=False)
        cmd += ["--requirement-rules", rp]
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                          errors="replace")


UI = "UI测试"

# ---------- 一、7b-B：提了样式却没给具体值 ----------
# 「颜色正确」没有可判定内容（哪个控件？什么颜色？）→ 与「正常显示」同级
vague = [mk("TC-1", "重置密码界面文字颜色", UI,
            "1. 界面文字颜色正确")]
r = run(vague, "style_vague", rules=["R-001"])
check("样式断言无具体值 → 判不可判定（fail）",
      "样式断言无具体值" in r.stdout and r.returncode == 1, r.stdout[-600:])

# 同类：布局/对齐/字号
for word, exp in [("布局", "1. 页面布局正确"), ("对齐", "1. 元素对齐正确"),
                  ("样式", "1. 按钮样式正确")]:
    r = run([mk(f"TC-S-{word}", f"界面{word}检查", UI, exp)], f"style_{word}",
            rules=["R-001"])
    check(f"样式词「{word}」无具体值 → 判不可判定",
          "样式断言无具体值" in r.stdout, r.stdout[-400:])

# ---------- 二、样式断言的三个豁免出口 ----------
# 1) 给出具体视觉值
r = run([mk("TC-2", "重置密码界面文字颜色", UI,
            "1. 标题应为黑色\n2. 占位符应置灰\n3. Send 按钮默认蓝色")],
        "style_ok_value", rules=["R-001"])
check("样式断言给出具体值（黑色/置灰/蓝色）→ 不报",
      "样式断言无具体值" not in r.stdout, r.stdout[-500:])

# 2) 设计稿兜底
r = run([mk("TC-3", "重置密码界面布局", UI,
            "1. 界面布局应与设计稿一致")],
        "style_ok_ref", rules=["R-001"])
check("样式断言有「设计稿」兜底 → 不报",
      "样式断言无具体值" not in r.stdout, r.stdout[-500:])

# 3) 原型图兜底
r = run([mk("TC-4", "提示框样式", UI, "1. 提示框样式应与 UI 原型图一致")],
        "style_ok_proto", rules=["R-001"])
check("样式断言有「原型图」兜底 → 不报",
      "样式断言无具体值" not in r.stdout, r.stdout[-500:])

# ---------- 三、7b-A：UI 元素清单壳用例 ----------
thin = [mk("TC-5", "删除账号验证界面UI元素显示完整", UI,
           "删除账号验证界面UI元素应显示完整")]
r = run(thin, "ui_thin", rules=["R-001"])
check("元素清单预期枚举 <2 项 → 告警（壳用例）",
      "「UI 元素」清单用例预期枚举" in r.stdout and "TC-5(0项)" in r.stdout,
      r.stdout[-600:])

rich = [mk("TC-6", "删除账号验证界面UI元素显示完整", UI,
           "删除账号验证界面UI元素应包括：\n"
           "1.返回按钮\n"
           "2.图标：红色三角形，中间有感叹号\n"
           "3.验证码输入框（输入框、获取验证码按钮）\n"
           "4.提示信息：此操作不可逆转，逐字显示")]
r = run(rich, "ui_rich", rules=["R-001"])
check("元素清单枚举 ≥2 项 → 不告警",
      "「UI 元素」清单用例预期枚举" not in r.stdout, r.stdout[-600:])

# ---------- 四、黑名单对 UI 族仍一票否决 ----------
r = run([mk("TC-7", "重置密码界面布局", UI,
            "1. 界面整体应居中显示\n2. 界面颜色搭配合理")],
        "ui_vague", rules=["R-001"])
check("UI 族命中「合理」黑名单 → 仍判不可判定（fail）",
      "预期结果不可判定" in r.stdout and r.returncode == 1, r.stdout[-600:])

# ---------- 五、非 UI 族不受 A 约束 ----------
fn = [mk("TC-8", "删除一条记录", "模块功能测试",
         "1. 记录应被删除\n2. 列表应刷新")]
r = run(fn, "fn_normal", rules=["R-001"])
check("非 UI 清单标题不触发壳用例告警",
      "「UI 元素」清单用例预期枚举" not in r.stdout, r.stdout[-500:])

print("\n" + "=" * 30)
print(f"通过 {PASS}/{PASS + FAIL}")
if FAILS:
    print("失败:", FAILS)
sys.exit(1 if FAIL else 0)
