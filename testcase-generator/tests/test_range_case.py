"""prescreen.py 第 14 项（范围性用例）+ 退出码语义化 回归测试。

第 14 项补的是 13 项闸门里唯一没兜底的缺口：
第 9/11/13 项都只数"条数"，数不出"4 条用例覆盖 16 个场景"。

退出码测试补的是另一个盲区：
崩溃（exit 3）和不达标（exit 1）必须可区分，否则会对着不存在的质量问题返工。
"""
import json
import os
import subprocess
import sys
import tempfile

# 技能目录：可用环境变量 TC_SKILL 覆盖，默认取 tests/ 的上级目录。
# 这样脚本在"本地技能目录"与"仓库克隆副本"两处都能跑，不再依赖本机绝对路径。
SKILL = os.environ.get("TC_SKILL") or os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))
PRESCREEN = os.path.join(SKILL, "scripts", "prescreen.py")
PY = sys.executable
TMP = tempfile.mkdtemp(prefix="range_case_")
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


def base_cases(n=20, p0=2, p2=8):
    """构造一组能过结构闸门的干净用例：P0/P2 占比达标、每个模块都有负向。

    neg 取 i∈{1..5}：按 mods[i%3] 分布正好覆盖 订单/支付/退款 三个模块，
    且每模块至少 1 条，满足第 9 项「模块内无异常/边界即阻断」。
    """
    out = []
    mods = ["订单", "支付", "退款"]
    for i in range(n):
        pri = "P1"
        if i < p0:
            pri = "P0"
        elif i < p0 + p2:
            pri = "P2"
        neg = i in (1, 2, 3, 4, 5)
        out.append({
            "id": f"TC-{mods[i % 3]}-{i + 1:03d}",
            "name": f"第{i + 1}项{'异常' if neg else '功能'}校验",
            "module": mods[i % 3],
            "priority": pri,
            "test_type": "异常测试" if neg else "功能测试",
            "precondition": "已登录",
            "steps": f"1. 进入第{i + 1}页\n2. 点击保存按钮",
            "expected": f"1. 应提示保存成功且编号为{i + 1}",
            "test_data": {"编号": str(i + 1)},
            "coverage_rule": f"R-{i % 6 + 1:03d}",
            "design_method": ["场景法"],
        })
    return out


def run(cases, extra=None, tag="t"):
    p = os.path.join(TMP, f"{tag}.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(cases, f, ensure_ascii=False)
    cmd = [PY, PRESCREEN, p, "--coverage-min", "0"] + (extra or [])
    return subprocess.run(cmd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", env=ENV)


def inject(cases, **over):
    """把第 5 条（P1、正向、支付模块）替换成测试样本。

    不动 i∈{1..5} 里 i=1 的负向用例，保证注入后各模块仍满足第 9 项。
    """
    c = dict(cases[4])
    c.update(over)
    out = list(cases)
    out[4] = c
    return out, c["id"]


# ---------- 基线：干净库不应有任何范围性告警 ----------
r0 = run(base_cases(), tag="base")
check("基线 干净库零范围性告警",
      "[!] 范围性用例" not in r0.stdout and "疑似范围性" not in r0.stdout,
      r0.stdout[-400:])
check("基线 干净库 exit 0", r0.returncode == 0, r0.stdout[-600:])

# ---------- 强证据：范围词 + ≥3 对象 + 仅 1 条预期 ----------
cs, cid = inject(base_cases(),
                 steps="依次点击 首页、课程库、个人档案、训练记录",
                 expected="1. 各页面应正常跳转")
r = run(cs, tag="strong")
check("强证据 被报出", cid in r.stdout and "[!] 范围性用例" in r.stdout, r.stdout[-500:])
check("强证据 报告含对象数", "4对象" in r.stdout or "对象 4 个" in r.stdout, r.stdout[-500:])
check("强证据 warn 模式不阻断", r.returncode == 0, f"exit={r.returncode}")

r_blk = run(cs, extra=["--range-mode", "block"], tag="strong_blk")
check("强证据 block 模式阻断", r_blk.returncode == 1, f"exit={r_blk.returncode}")
check("强证据 block 模式进 ✗ 列表",
      any(cid in l and l.strip().startswith("✗") for l in r_blk.stdout.split("\n")),
      r_blk.stdout[-500:])

# ---------- 不应误伤 ----------
cs, cid = inject(base_cases(),
                 steps="逐一安装 APP、驱动、插件",
                 expected="1. 安装成功\n2. 应提示重启\n3. 状态应可用")
r = run(cs, tag="multi_exp")
check("误伤防护 3 对象但 3 条预期 → 不报强证据",
      f"{cid}(3对象)" not in r.stdout, r.stdout[-400:])

cs, cid = inject(base_cases(),
                 steps="依次点击 首页、课程库",
                 expected="1. 应跳转成功")
r = run(cs, tag="obj2")
check("误伤防护 并列对象仅 2 个 → 不报强证据",
      f"{cid}(2对象)" not in r.stdout, r.stdout[-400:])

cs, cid = inject(base_cases(),
                 steps="点击保存按钮",
                 expected="1. 应逐一核对 订单号、用户、金额 三项并提示成功")
r = run(cs, tag="exp_only")
check("误伤防护 范围词只在预期、不在步骤 → 不报",
      f"{cid}(" not in r.stdout.split("=== 预审")[0].split("范围性用例")[0],
      r.stdout[-400:])

# ---------- 备注列展开 → 降级为弱告警 ----------
cs, cid = inject(base_cases(),
                 steps="分别校验 亮度、音量、亮度记忆",
                 expected="1. 全部应生效",
                 remark="亮度=50 应生效；音量=80 应生效；亮度记忆=开 应生效")
r = run(cs, tag="remark")
check("备注已展开 → 不计入强证据", f"{cid}(3对象)" not in r.stdout, r.stdout[-400:])
check("备注已展开 → 弱告警提及",
      "疑似范围性" in r.stdout and cid in r.stdout, r.stdout[-500:])
r_blk = run(cs, extra=["--range-mode", "block"], tag="remark_blk")
check("备注已展开 → block 模式也不阻断", r_blk.returncode == 0,
      f"exit={r_blk.returncode}")

# ---------- off 开关 ----------
r = run(cs, extra=["--range-mode", "off"], tag="off")
check("--range-mode off 完全不输出第 14 项",
      "范围性用例" not in r.stdout and "疑似范围性" not in r.stdout, r.stdout[-400:])

# ---------- 阈值可调 ----------
cs, cid = inject(base_cases(),
                 steps="依次点击 首页、课程库",
                 expected="1. 应跳转成功")
r = run(cs, extra=["--range-min-objs", "2"], tag="objs2")
check("--range-min-objs 2 时 2 个对象即判强证据",
      f"{cid}(2对象)" in r.stdout, r.stdout[-400:])

# ---------- 退出码语义化 ----------
p_bad = os.path.join(TMP, "crash.json")
with open(p_bad, "w", encoding="utf-8") as f:
    json.dump(["not-a-dict"], f, ensure_ascii=False)
r_crash = subprocess.run([PY, PRESCREEN, p_bad, "--coverage-min", "0"],
                         capture_output=True, text=True, encoding="utf-8",
                         errors="replace", env=ENV)
check("崩溃返回 exit 3（不是 1）", r_crash.returncode == 3, f"exit={r_crash.returncode}")
check("崩溃时 stderr 明示『不是用例质量问题』",
      "不是数据不达标" in r_crash.stderr, r_crash.stderr[-300:])

p_missing = os.path.join(TMP, "nope.json")
r_miss = subprocess.run([PY, PRESCREEN, p_missing], capture_output=True, text=True,
                        encoding="utf-8", errors="replace", env=ENV)
check("输入文件不存在返回 exit 2（不是 1/3）", r_miss.returncode == 2,
      f"exit={r_miss.returncode}")

r_fail = run(inject(base_cases(), steps="点击保存", expected="1. 应合理显示")[0], tag="fail1")
check("不达标返回 exit 1", r_fail.returncode == 1, f"exit={r_fail.returncode}")

check("三种退出码互不混用",
      {0, 1, 2, 3} - {r0.returncode, r_fail.returncode, r_miss.returncode, r_crash.returncode} == {0} or
      len({r0.returncode, r_fail.returncode, r_miss.returncode, r_crash.returncode}) == 4,
      f"得到 {r0.returncode}/{r_fail.returncode}/{r_miss.returncode}/{r_crash.returncode}")

print("\n" + "=" * 30)
print(f"通过 {PASS}/{PASS + FAIL}")
if FAILS:
    print("失败:", FAILS)
print("临时目录:", TMP)
sys.exit(1 if FAIL else 0)
