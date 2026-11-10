"""第 6 项「语义重复」指纹回归。

守的是一个会**逼人删掉正确用例**的坑（本项是 fails 阻断，不是 warn）：

真实库报了 1 组「重复」——
    TC-首页-006  前置 = 已进入「本周训练」界面
    TC-首页-010  前置 = 已进入「四周训练」界面
步骤与预期逐字相同，于是被判重复。但这是两个**不同入口**的用例，而
`case_design.md` 第七节自己就写着「多入口 → 一律拆条」。
漏掉前置，等于让工具推翻它自己刚下的设计规范。

所以指纹必须是 (module, precondition, steps, expected)：
- 前置不同 → 不报（本例）
- 前置相同/都为空 → 照旧报（否则就是修完假阳性换来假阴性）
"""
import json
import os
import subprocess
import sys
import tempfile

SKILL = os.environ.get("TC_SKILL") or os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))
PRESCREEN = os.path.join(SKILL, "scripts", "prescreen.py")
PY = sys.executable
TMP = tempfile.mkdtemp(prefix="dup_fp_")
ENV = dict(os.environ, PYTHONIOENCODING="utf-8")

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


def case(cid, pre, steps, exp, module="首页", pri="P1"):
    return {"id": cid, "name": f"用例{cid}", "module": module, "priority": pri,
            "test_type": "功能测试", "precondition": pre, "steps": steps,
            "expected": exp, "test_data": {"k": "v"},
            "coverage_rule": "R-001", "design_method": ["场景法"]}


def run(cases, tag):
    p = os.path.join(TMP, f"{tag}.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(cases, f, ensure_ascii=False)
    r = subprocess.run([PY, PRESCREEN, p, "--coverage-min", "0"],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", env=ENV)
    return r


STEPS = "1. 点击「回到今日训练」按钮，查看界面跳转"
EXP = "1. 应跳转至首页界面"

# ---------- 一、前置不同 → 不得报重复（本次修复的方向）----------
r = run([case("TC-首页-006", "已进入「本周训练」界面", STEPS, EXP),
         case("TC-首页-010", "已进入「四周训练」界面", STEPS, EXP)], "diff_pre")
check("前置不同（两个入口）→ 不报语义重复", "组语义重复" not in r.stdout, r.stdout[-400:])

# ---------- 二、前置相同 → 必须照旧报（防假阴性）----------
r = run([case("TC-A-001", "已进入「本周训练」界面", STEPS, EXP),
         case("TC-A-002", "已进入「本周训练」界面", STEPS, EXP)], "same_pre")
check("前置相同 + 步骤预期相同 → 仍报语义重复", "组语义重复" in r.stdout, r.stdout[-400:])
check("前置相同 → 阻断 exit 1", r.returncode == 1, f"exit={r.returncode}")

# ---------- 三、前置都为空 → 仍要报（不能靠"空前置"免罚）----------
r = run([case("TC-B-001", "", STEPS, EXP),
         case("TC-B-002", "", STEPS, EXP)], "empty_pre")
check("前置均为空 + 步骤预期相同 → 仍报语义重复", "组语义重复" in r.stdout, r.stdout[-400:])

# ---------- 四、前置仅空白/换行差异 → 视为相同 ----------
r = run([case("TC-C-001", "已进入本周训练界面", STEPS, EXP),
         case("TC-C-002", "已进入本周训练界面\n", STEPS, EXP)], "ws_pre")
check("前置仅尾随换行差异 → 仍判重复（norm 生效）", "组语义重复" in r.stdout, r.stdout[-400:])

# ---------- 五、其他维度不同 → 不得误报 ----------
r = run([case("TC-D-001", "已登录", STEPS, EXP, module="首页"),
         case("TC-D-002", "已登录", STEPS, EXP, module="个人中心")], "diff_mod")
check("模块不同 → 不报重复", "组语义重复" not in r.stdout, r.stdout[-400:])

r = run([case("TC-E-001", "已登录", STEPS, EXP),
         case("TC-E-002", "已登录", "1. 点击按钮并长按 3 秒", EXP)], "diff_steps")
check("步骤不同 → 不报重复", "组语义重复" not in r.stdout, r.stdout[-400:])

r = run([case("TC-F-001", "已登录", STEPS, EXP),
         case("TC-F-002", "已登录", STEPS, "1. 应停留在当前页")], "diff_exp")
check("预期不同 → 不报重复", "组语义重复" not in r.stdout, r.stdout[-400:])

# ---------- 六、三条同指纹 → 只算 1 组 ----------
r = run([case("TC-G-001", "已登录", STEPS, EXP),
         case("TC-G-002", "已登录", STEPS, EXP),
         case("TC-G-003", "已登录", STEPS, EXP)], "triple")
check("三条同指纹 → 报 1 组", "1 组语义重复" in r.stdout, r.stdout[-400:])

# ---------- 七、源码级防回退 ----------
SRC = open(PRESCREEN, encoding="utf-8").read()
check("源码 指纹含 precondition",
      'norm(c.get("precondition", ""))' in SRC)
check("源码 指纹仍是四元组（module/pre/steps/exp）",
      'key = (c.get("module", ""), norm(c.get("precondition", "")),' in SRC)

print("\n" + "=" * 30)
print(f"通过 {PASS}/{PASS + FAIL}")
if FAILS:
    print("失败:", FAILS)
sys.exit(1 if FAIL else 0)
