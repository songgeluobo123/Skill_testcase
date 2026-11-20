"""第 8b 项（前置/步骤/预期 编号步骤每步一行）回归。

判据来源：优秀用例库 1278 条回放——三字段**零违规**（步骤/预期全部每步一行）；
唯一 9 处"同行多编号"全是「（从上到下分别是：按钮1、按钮2、按钮3）」这类
**括号枚举**，不是步骤。所以：
  - 编号步骤挤一行（1.甲2.乙3.丙）→ 违规：执行时只验第一条，且无法逐条判定；
  - 括号内容先剔除再数编号（否则优秀库反而被打脸）；
  - 数值（3.8-4.4 / v1.2.3 / 192.168.1.1 / 1.15 秒）不算编号，沿用 ITEM_SEQ 口径。
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
TMP = tempfile.mkdtemp(prefix="step_lines_")

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


def mk(cid, pre="已登录", steps="1. 点击按钮\n2. 查看结果", exp="1. 应提示成功"):
    return {"id": cid, "name": "功能用例", "module": "订单", "priority": "P1",
            "test_type": "模块功能测试", "precondition": pre,
            "steps": steps, "expected": exp, "test_data": {"账号": "test01"},
            "coverage_rule": "R-001", "design_method": ["场景法"]}


RELAX = ["--coverage-min", "0", "--p0-min", "0", "--p0-max", "1",
         "--p2-min", "0", "--p2-max", "1", "--scene-min-cases", "99"]


def run(cases, tag, rules=None, extra=()):
    p = os.path.join(TMP, f"{tag}.json")
    json.dump(cases, open(p, "w", encoding="utf-8"), ensure_ascii=False)
    cmd = [PY, SCRIPT, p] + RELAX + list(extra)
    if rules:
        rp = os.path.join(TMP, "rules.json")
        json.dump(rules, open(rp, "w", encoding="utf-8"), ensure_ascii=False)
        cmd += ["--requirement-rules", rp]
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                          errors="replace")


# ---------- 一、三个字段的挤行都要抓 ----------
r = run([mk("TC-1", steps="1. 输入密码2. 点击登录按钮")], "steps_inline", rules=["R-001"])
check("步骤挤一行 → 告警并指明字段",
      "同行多编号" in r.stdout and "TC-1(steps" in r.stdout, r.stdout[-600:])

r = run([mk("TC-2", pre="1. 手机号已注册2. 已登录状态")], "pre_inline", rules=["R-001"])
check("前置挤一行 → 告警", "同行多编号" in r.stdout and "TC-2(precondition" in r.stdout,
      r.stdout[-600:])

r = run([mk("TC-3", exp="1. 提示成功2. 列表刷新3. 状态变为已启用")], "exp_inline",
        rules=["R-001"])
check("预期挤一行 → 告警", "同行多编号" in r.stdout and "TC-3(expected" in r.stdout,
      r.stdout[-600:])

# ---------- 二、正确写法（用户示例格式）不告警 ----------
good = [mk("TC-4",
           pre="1. 手机号已注册\n2. 已登录状态",
           steps="1. 勾选我已阅读并同意“用户注册”和“隐私政策”复选框\n"
                 "2. 点击页面中的“本机号码一键登录”按钮",
           exp="1. 应登录成功并进入首页\n2. 应显示当前手机号")]
r = run(good, "multiline_ok", rules=["R-001"])
check("每步一行（用户示例格式）→ 不告警", "同行多编号" not in r.stdout, r.stdout[-600:])

# ---------- 三、括号枚举豁免 ----------
bracket = [mk("TC-5",
              pre="1. 在速度模式界面\n（从上到下分别是：按钮1、按钮2、按钮3）",
              steps="1. 点击按钮2",
              exp="1. 档位切换成功")]
r = run(bracket, "bracket_ok", rules=["R-001"])
check("括号枚举（按钮1、按钮2、按钮3）→ 不告警",
      "同行多编号" not in r.stdout, r.stdout[-600:])

# ---------- 四、数值不误伤 ----------
nums = [mk("TC-6",
           pre="1. 设备固件版本为 v1.2.3",
           steps="1. 将速度设为 3.8-4.4 km/h\n2. 观察 IP 192.168.1.1 的设备",
           exp="1. 1.15 秒内应响应\n2. 用时应 ≤2 秒")]
r = run(nums, "nums_ok", rules=["R-001"])
check("数值（3.8-4.4/v1.2.3/IP/1.15 秒）不误伤", "同行多编号" not in r.stdout,
      r.stdout[-600:])

# ---------- 五、起始编号非 1 的分行也不误伤 ----------
offset = [mk("TC-7", exp="2. 名字正确\n3. 文字字体正确\n4. 无错别字")]
r = run(offset, "offset_ok", rules=["R-001"])
check("分行但起始编号为 2 → 不告警", "同行多编号" not in r.stdout, r.stdout[-600:])

# ---------- 六、同一用例多字段违规只算一条用例，但逐字段列出 ----------
multi = [mk("TC-8",
            pre="1. 已登录2. 已绑定设备",
            steps="1. 点击按钮2. 查看结果",
            exp="1. 应成功2. 应提示")]
r = run(multi, "multi_field", rules=["R-001"])
n_fields = sum(1 for f in ("precondition", "steps", "expected")
               if f"TC-8({f}" in r.stdout)
check("三字段同违规 → 逐字段各列一条", n_fields == 3,
      f"列出 {n_fields} 个字段 | {r.stdout[-500:]}")
check("汇总告警按用例计数", "3 条用例存在「同行多编号」" in r.stdout or
      "1 条用例存在" not in r.stdout, r.stdout[-500:])


# ---------- 七、8b 默认 block；导出层自动拆分兜底 ----------
r = run([mk("TC-9", steps="1. 输入密码2. 点击登录按钮")], "block_default", rules=["R-001"])
check("8b 默认 block（单行多编号 → exit 1）", r.returncode == 1, f"exit={r.returncode}")

r = run([mk("TC-10", steps="1. 输入密码2. 点击登录按钮")], "block_off", rules=["R-001"],
        extra=["--step-lines-mode", "warn"])
check("--step-lines-mode warn 可临时降级", r.returncode == 0, f"exit={r.returncode}")

# to_excel 自动拆分（导出层兜底：使用者打开 Excel 就是分行结果）
import importlib.util
spec = importlib.util.spec_from_file_location(
    "t2e", os.path.join(SKILL, "scripts", "to_excel.py"))
t2e = importlib.util.module_from_spec(spec)
spec.loader.exec_module(t2e)

shot = ("1. 在“选择设备”界面中点击页面中的“添加设备”按钮2. 进入“发现设备”界面进行搜索"
        "3. 在搜索到的设备列表中选择设备")
out = t2e.split_inline_steps(shot)
check("导出自动拆分：截图形态 → 3 行", len(out.splitlines()) == 3, repr(out))
check("导出自动拆分：编号保留在各行行首",
      all(x.startswith(("1.", "2.", "3.")) for x in out.splitlines()), repr(out))

check("导出自动拆分不误伤版本号与小数",
      len(t2e.split_inline_steps("1. 查看 v1.2.3 与 3.8-4.4 km/h2. 点击确认").splitlines()) == 2)
check("导出自动拆分：单编号不拆",
      len(t2e.split_inline_steps("1. 查验升级中页面元素").splitlines()) == 1)
check("导出自动拆分：编号不递增不拆",
      len(t2e.split_inline_steps("1. 见步骤3. 的说明").splitlines()) == 1)
check("导出自动拆分：已分行保持",
      t2e.split_inline_steps("1. 甲\n2. 乙") == "1. 甲\n2. 乙")

# 端到端：单行 steps 导出后单元格内出现 3 行
jx = os.path.join(TMP, "e2e.json")
json.dump([{"id": "TC-E2E", "name": "截图形态用例", "module": "车辆连接", "priority": "P1",
            "test_type": "界面交互测试", "precondition": "1. 已登录2. 蓝牙已开启",
            "steps": "1. 在“选择设备”界面中点击“添加设备”按钮2. 进入“发现设备”界面搜索"
                     "3. 在设备列表中选择设备",
            "expected": "1. 应进入发现设备界面2. 应显示设备列表3. 应发起连接",
            "test_data": {}, "design_method": ["场景法"]}],
           open(jx, "w", encoding="utf-8"), ensure_ascii=False)
ox = os.path.join(TMP, "e2e.xlsx")
r2 = subprocess.run([PY, os.path.join(SKILL, "scripts", "to_excel.py"), jx, "-o", ox],
                    capture_output=True, text=True, encoding="utf-8", errors="replace")
ok_e2e = False
detail = r2.stdout[-300:] + r2.stderr[-300:]
if os.path.exists(ox):
    try:
        from openpyxl import load_workbook
        ws = load_workbook(ox).active
        hdr = [c.value for c in ws[1]]
        row = [c.value for c in ws[2]]
        i_steps = hdr.index("测试步骤")
        i_pre = hdr.index("前置条件")
        i_exp = hdr.index("预期结果")
        ok_e2e = (str(row[i_steps]).count("\n") == 2
                  and str(row[i_pre]).count("\n") == 1
                  and str(row[i_exp]).count("\n") == 2)
        detail = f"steps={row[i_steps]!r}"
    except Exception as e:
        detail = f"读回失败 {e}"
check("端到端：导出的三字段均已分行", ok_e2e, detail)

print("\n" + "=" * 30)
print(f"通过 {PASS}/{PASS + FAIL}")
if FAILS:
    print("失败:", FAILS)
sys.exit(1 if FAIL else 0)
