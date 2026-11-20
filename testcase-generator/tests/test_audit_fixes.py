"""体检报告（2026-11-20）驱动的 5 缺陷修复 + 存量库体检脚本回归。

每条都对应一个**已复现的真实误判**（报告附最小复现）：
  1. 边界值不认「下界/上界」→ 50 条边界用例被集体判虚标
  2. UI 枚举行内 ①②③ 被算 0 项 → 真枚举被判壳用例
  3. 位置词表只 4 个词 → 「点击弹窗底部的取消按钮」判歧义
  4. steps<15 字即扣分 → 「查验升级中页面元素」被判不可执行（与 UI 族 1 步合法打架）
  5. naming_rules R2 与 case_design 正例口径不一（文档级，由用例覆盖不检查）
"""
import json
import os
import subprocess
import sys
import tempfile

SKILL = os.environ.get("TC_SKILL") or os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))
PRESCREEN = os.path.join(SKILL, "scripts", "prescreen.py")
SCORE = os.path.join(SKILL, "scripts", "score_testcases.py")
LEGACY = os.path.join(SKILL, "scripts", "normalize_legacy.py")
PY = sys.executable
TMP = tempfile.mkdtemp(prefix="audit_fix_")

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


RELAX = ["--coverage-min", "0", "--p0-min", "0", "--p0-max", "1",
         "--p2-min", "0", "--p2-max", "1", "--scene-min-cases", "99",
         "--ui-cover-mode", "off", "--nf-cover-mode", "off",
         "--single-case-mode", "off", "--min-cases-per-rule", "0"]


def prescreen(cases, tag, extra=()):
    p = os.path.join(TMP, f"{tag}.json")
    json.dump(cases, open(p, "w", encoding="utf-8"), ensure_ascii=False)
    rp = os.path.join(TMP, "rules.json")
    json.dump(["R-040", "R-062"], open(rp, "w", encoding="utf-8"), ensure_ascii=False)
    return subprocess.run([PY, PRESCREEN, p, "--requirement-rules", rp] + RELAX + list(extra),
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace")


def score(cases, tag):
    p = os.path.join(TMP, f"sc_{tag}.json")
    json.dump(cases, open(p, "w", encoding="utf-8"), ensure_ascii=False)
    return subprocess.run([PY, SCORE, p], capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


def mk(cid, name, steps, exp, ttype="界面交互测试", method=("场景法",)):
    return {"id": cid, "name": name, "module": "车辆设置", "priority": "P2",
            "test_type": ttype, "precondition": "已连接车辆",
            "steps": steps, "expected": exp, "test_data": {"账号": "test01"},
            "coverage_rule": "R-062", "design_method": list(method)}


# ---------- 缺陷 1：边界值认「下界/上界」 ----------
r = prescreen([mk("TC-1", "单里程清除时间枚举边界", "1. 打开单里程清除时间设置",
                  "可选项应为立即/1/3/7 天四档，下界 1 天、上界 7 天，2 天为枚举外值不可选",
                  ttype="边界测试", method=("边界值分析",))], "bnd")
check("缺陷1 下界/上界 不再判方法虚标", "虚标" not in r.stdout, r.stdout[-600:])

r = prescreen([mk("TC-2", "无关用例声称边界值", "1. 打开页面",
                  "1. 应显示列表", ttype="边界测试", method=("边界值分析",))], "bnd2")
check("缺陷1 真虚标仍被抓（无边界证据）", "虚标" in r.stdout, r.stdout[-600:])

# ---------- 缺陷 2：行内 ①②③ 识别 ----------
r = prescreen([mk("TC-3", "升级中页面元素完整", "1. 查验升级中页面的元素",
                  "应展示 ① 当前阶段名 ② 进度指示 ③ 不可中断提示 ④ 无取消按钮，共 4 类元素齐全",
                  ttype="UI元素测试")], "ui_inline")
check("缺陷2 行内 ①②③④ 不再判壳用例",
      "清单用例预期枚举" not in r.stdout, r.stdout[-700:])

r = prescreen([mk("TC-4", "升级中页面元素完整", "1. 查验升级中页面的元素",
                  "应展示当前阶段名与进度指示", ttype="UI元素测试")], "ui_thin2")
check("缺陷2 真壳用例（无枚举）仍被抓",
      "清单用例预期枚举" in r.stdout, r.stdout[-700:])

# 小数/版本号不被当枚举
import importlib.util
spec = importlib.util.spec_from_file_location("ps", PRESCREEN)
ps = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ps)
check("缺陷2 小数/版本号不误判为枚举",
      len(ps.UI_LIST_ENUM.findall("速度为 3.8-4.4 km/h，固件 v1.2.3，日期 2025.03")) == 0,
      str(ps.UI_LIST_ENUM.findall("速度为 3.8-4.4 km/h，固件 v1.2.3，日期 2025.03")))
check("缺陷2 分行编号仍正常识别",
      len(ps.UI_LIST_ENUM.findall("1. 返回按钮\n2. 图标：红色三角形\n3. 提示文案")) == 3)

# ---------- 缺陷 3：位置词表 ----------
r = score([mk("TC-5", "取消弹窗", "点击弹窗底部的取消按钮并确认弹窗关闭",
              "1. 弹窗应关闭")], "pos")
check("缺陷3 「弹窗底部」不再判位置歧义", "未说明位置" not in r.stdout, r.stdout[-500:])
check("缺陷3 可执行性不再被扣到 80", "可执行 100" in r.stdout, r.stdout[-500:])

r = score([mk("TC-6", "取消", "点击按钮", "1. 应关闭")], "pos2")
check("缺陷3 裸写「点击按钮」仍判歧义", "未说明位置" in r.stdout, r.stdout[-500:])

# ---------- 缺陷 4：短步骤按语义判 ----------
r = score([mk("TC-7", "升级中页面元素", "查验升级中页面元素",
              "应展示 ① 阶段名 ② 进度 ③ 提示")], "short")
check("缺陷4 「查验X」10 字步骤不再判过短", "过短" not in r.stdout, r.stdout[-500:])
check("缺陷4 含动词短步骤可执行性 100", "可执行 100" in r.stdout, r.stdout[-500:])

r = score([mk("TC-8", "元素", "看看这个", "1. 应显示")], "short2")
check("缺陷4 无动词步骤仍判不可执行", "可执行 25" in r.stdout or "缺少明确动作动词" in r.stdout,
      r.stdout[-500:])

# ---------- 存量库体检脚本 ----------
cases = [
    {"id": "L-1", "module": "订单", "name": "登录成功", "priority": "P0",
     "precondition": "1. 点击设置按钮\n2. 已登录", "steps": "点击按钮",
     "expected": "1. 应跳转", "test_data": {"账号": "test01"}},
    {"id": "L-2", "module": "订单", "name": "正确密码登录", "priority": "P2",
     "precondition": "已登录", "steps": "1. 输入账号\n2. 点击登录按钮",
     "expected": "1. 应进入首页", "test_data": {"账号": "test02"}},
    {"id": "L-3", "module": "订单", "name": "订单列表", "priority": "P2",
     "precondition": "已登录", "steps": "1. 进入页面", "expected": "1. 应显示列表",
     "test_data": {"账号": "xxx"}},
]
pj = os.path.join(TMP, "legacy.json")
json.dump(cases, open(pj, "w", encoding="utf-8"), ensure_ascii=False)
rep = os.path.join(TMP, "diag.md")
r = subprocess.run([PY, LEGACY, pj, "-o", rep], capture_output=True, text=True,
                   encoding="utf-8", errors="replace")
check("体检脚本 正常执行", r.returncode == 0, r.stdout[-400:] + r.stderr[-300:])
check("体检脚本 输出报告文件", os.path.exists(rep))
md = open(rep, encoding="utf-8").read() if os.path.exists(rep) else ""
check("体检脚本 抓到前置写操作（L-1）", "结构与语义错位" in md and "L-1" in md, md[:400])
check("体检脚本 抓到标题空泛词（L-1 登录成功）", "标题含空泛判定词" in md, md[:400])
check("体检脚本 抓到数据占位（L-3 xxx）", "测试数据无效" in md, md[:400])
check("体检脚本 抓到步骤不可执行（L-1 点击按钮）", "步骤不可执行" in md, md[:400])
check("体检脚本 报告含修复顺序", "建议顺序" in md, md[:400])

# xlsx 直读
try:
    from openpyxl import Workbook
    wb = Workbook(); ws = wb.active
    ws.append(["用例编号", "功能模块", "测试用例标题", "测试优先级", "测试类型",
               "测试环境", "前置条件", "测试步骤", "预期结果", "测试数据", "备注"])
    ws.append(["X-1", "订单", "登录成功", "P0", "功能测试", "已联网",
               "已登录", "点击按钮", "应跳转", "账号=test01", ""])
    px = os.path.join(TMP, "legacy.xlsx")
    wb.save(px)
    r = subprocess.run([PY, LEGACY, px], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    check("体检脚本 xlsx 直读", "体检 1 条用例" in r.stdout, r.stdout[-300:] + r.stderr[-300:])
except ImportError:
    print("SKIP xlsx 直读（无 openpyxl）")

print("\n" + "=" * 30)
print(f"通过 {PASS}/{PASS + FAIL}")
if FAILS:
    print("失败:", FAILS)
sys.exit(1 if FAIL else 0)
