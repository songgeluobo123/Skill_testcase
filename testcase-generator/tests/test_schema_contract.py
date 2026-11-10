"""字段契约与数值可达性回归（自检发现的三处缺陷）。

对应缺陷：
  D1  标题字段分裂：output_format/to_excel 用 `name`，prescreen/coverage_audit 只读 `title`
      → 按规范写出的用例被判「标题为空」全量阻断。修：name 优先、title 兜底。
  D2  steps/expected 写成数组时 norm() 抛 TypeError
      → 第 6 项崩溃，第 7~13 项全部不执行，退出码 1 被误读成「预审不通过」。修：归一化。
  D3  P0 10%~15% 在 5/6/11/12/13 条库下无整数解（k/n 两端口都出界）
      → 无论怎么排优先级都过不了。修：整数粒度补偿（仅区间无整数解时生效）。

这个文件的存在本身就是教训：旧夹具同时写了 name 和 title，所以 D1 一直是绿的。
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
TMP = tempfile.mkdtemp(prefix="schema_contract_")

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


def build(n, p0k, p2k, key="name", steps_as_list=False, neg=False):
    """key: 'name' / 'title' / 'both'。neg=True 时让部分用例带异常类。"""
    out = []
    mods = ["订单", "支付", "退款"]
    for i in range(n):
        pri = "P1"
        if i < p0k:
            pri = "P0"
        elif i < p0k + p2k:
            pri = "P2"
        ttype = "功能测试"
        title = f"第{i + 1}项功能校验"
        if neg and i % 4 == 1:
            ttype = "异常测试"
            title = f"第{i + 1}项异常校验"
        steps = [f"步骤一{i + 1}", f"步骤二{i + 1}"] if steps_as_list \
            else f"1. 步骤一{i + 1}\n2. 步骤二{i + 1}"
        c = {
            "id": f"TC-{mods[i % 3]}-{i + 1:03d}",
            "module": mods[i % 3],
            "priority": pri,
            "test_type": ttype,
            "precondition": "已登录",
            "steps": steps,
            "expected": f"1. 应显示第{i + 1}条结果",
            "test_data": {"值": f"数据{i + 1}"},
            "coverage_rule": f"R-{i % 6 + 1:03d}",
            "design_method": ["场景法"],
        }
        if key == "name":
            c["name"] = title
        elif key == "title":
            c["title"] = title
        else:
            c["name"] = title
            c["title"] = title
        out.append(c)
    return out


def run(cases, extra=None, tag="x"):
    p = os.path.join(TMP, f"{tag}.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(cases, f, ensure_ascii=False)
    cmd = [PY, PRESCREEN, p, "--coverage-min", "0"] + (extra or [])
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    r = subprocess.run(cmd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env=env)
    return r


# ---------- D1 标题字段分裂 ----------
r_name = run(build(20, 3, 8, key="name"), tag="name_only")
check("D1 name-only 不被判标题为空",
      "标题为空" not in r_name.stdout, r_name.stdout[-400:])
check("D1 name-only 无崩溃（有完整结论行）",
      ("预审全部通过" in r_name.stdout) or ("需修正后重跑" in r_name.stdout),
      "既无通过也无失败结论 = 中途崩溃")

r_title = run(build(20, 3, 8, key="title"), tag="title_only")
check("D1 title-only 同样可用（向后兼容）",
      "标题为空" not in r_title.stdout, r_title.stdout[-400:])

r_both = run(build(20, 3, 8, key="both"), tag="both")
check("D1 两字段都给时按 name 取（无告警）",
      "标题为空" not in r_both.stdout and r_both.stderr == "", r_both.stdout[-300:])

# name 为空串、title 有值时，应回落到 title 而不是报空
c = build(20, 3, 8, key="both")
c[0]["name"] = ""
r_fb = run(c, tag="fallback")
check("D1 name 为空串时回落 title", "标题为空" not in r_fb.stdout, r_fb.stdout[-400:])

# ---------- D2 steps 数组不崩溃 ----------
r_list = run(build(20, 3, 8, key="name", steps_as_list=True), tag="list")
check("D2 steps 为数组不抛异常",
      "TypeError" not in r_list.stderr and "Traceback" not in r_list.stderr,
      r_list.stderr[-500:])
check("D2 steps 为数组时后续闸门仍执行",
      ("预审全部通过" in r_list.stdout) or ("需修正后重跑" in r_list.stdout),
      "第 6 项崩溃会导致第 7~13 项全不执行")
check("D2 steps 为数组不误报标题为空", "标题为空" not in r_list.stdout)

# 数组形式与字符串形式应给出相同结论
r_str = run(build(20, 3, 8, key="name"), tag="strv")
check("D2 数组与字符串结论一致",
      r_list.returncode == r_str.returncode,
      f"array exit={r_list.returncode} str exit={r_str.returncode}")

# ---------- D3 P0/P2 整数粒度补偿 ----------
# 显式固定窄区间 [10%,15%]：本组测的是"补偿机制本身"，不该随 --p0-max 默认值漂移。
# 默认值从 0.15 放宽到 0.25 后，12 条库放 2~3 条 P0 就有解了，不再触发补偿——
# 若不固定区间，这些用例会从"测试补偿"悄悄退化成"测试默认值"。
NARROW = ["--p0-max", "0.15"]
for n, p0k in ((12, 1), (12, 2), (6, 1), (5, 1), (11, 1), (13, 2)):
    r = run(build(n, p0k, 0, neg=True), tag=f"n{n}p{p0k}", extra=NARROW)
    lines = [l for l in r.stdout.split("\n") if l.strip().startswith("[✓] P0")]
    ok = bool(lines) and "整数粒度补偿" in lines[0]
    check(f"D3 n={n} P0={p0k} 条触发补偿并通过", ok,
          lines[0] if lines else "无 P0 结论行")

# 可达时必须精确判，不得补偿
r_ok = run(build(20, 3, 8, neg=True), tag="n20exact", extra=NARROW)
p0_line = [l for l in r_ok.stdout.split("\n") if l.strip().startswith("[✓] P0")]
check("D3 n=20 可达时不打补偿标记",
      bool(p0_line) and "补偿" not in p0_line[0],
      p0_line[0] if p0_line else "无 P0 结论行")

# 关闭补偿后，12 条库必须失败（证明补偿是显式行为，不是把闸门废掉）
r_off = run(build(12, 1, 0, neg=True), extra=NARROW + ["--ratio-tolerance", "0"],
            tag="tol0")
check("D3 --ratio-tolerance 0 关闭补偿后 n=12 P0 失败",
      r_off.returncode == 1 and "P0 占比" in r_off.stdout,
      f"exit={r_off.returncode}")

# 补偿只救"区间无整数解"，不救真的排错（20 条 0 条 P0 仍然必须失败）
r_bad = run(build(20, 0, 8, neg=True), tag="n20zero", extra=NARROW)
check("D3 补偿不豁免真实违规（20 条 0 条 P0 仍失败）",
      r_bad.returncode == 1 and "P0 占比" in r_bad.stdout,
      f"exit={r_bad.returncode}")

print("\n" + "=" * 30)
print(f"通过 {PASS}/{PASS + FAIL}")
if FAILS:
    print("失败:", FAILS)
print("临时目录:", TMP)
sys.exit(1 if FAIL else 0)
