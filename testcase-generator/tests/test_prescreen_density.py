"""prescreen.py 第 11/12/13 项（需求密度 / 方法一致性 / 需求级场景配额）回归测试。

设计原则：
  - 每个断言只让**目标检查项**可能失败：P0/P2 占比放宽到 [0,1]、模块级第 9 项用
    --scene-min-cases 99 禁用，避免旧检查的噪声掩盖新检查的判决。
  - 每条"应该通过"的样例都对应一个真实的误判坑（标题含"不等于"、0% 下界、
    四组合判定表、"无" 作为合法取值），这些坑都是 196 条历史库回放时踩出来的。

运行：python test_prescreen_density.py
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
SCRIPT = os.path.join(SKILL, "scripts", "prescreen.py")
PY = sys.executable

# 只放行本次要验的检查项，其余全部放宽/禁用
RELAX = [
    "--coverage-min", "0",        # 单用例样例不可能覆盖全部规则
    "--p0-min", "0", "--p0-max", "1",
    "--p2-min", "0", "--p2-max", "1",
    "--scene-min-cases", "99",
]


def mk(cid, title, pri="P1", ttype="功能测试", rule="R-001",
       method=("场景法",), steps="1. 进入页面\n2. 执行操作",
       expected="1. 进入页面\n2. 应提示「操作成功」且列表刷新", data=None, module="订单"):
    return {
        "id": cid, "name": title, "module": module,
        "priority": pri, "test_type": ttype,
        "precondition": "已登录并进入对应页面",
        "steps": steps, "expected": expected,
        "test_data": data if data is not None else {"账号": "test01"},
        "coverage_rule": rule, "design_method": list(method), "stage": "功能测试",
    }


tmp = tempfile.mkdtemp(prefix="prescreen_density_")
RULES = os.path.join(tmp, "rules.json")
json.dump(["R-001", "R-002", "R-003"], open(RULES, "w", encoding="utf-8"),
          ensure_ascii=False)

results = {}


def run(cases, name, extra=()):
    p = os.path.join(tmp, f"{name}.json")
    json.dump(cases, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    r = subprocess.run([PY, SCRIPT, p, "--requirement-rules", RULES] + RELAX + list(extra),
                       capture_output=True, text=True)
    print("=" * 16, name, " ".join(extra) or "(默认)", "=" * 16)
    print(r.stdout.strip()[:1600])
    if r.returncode not in (0, 1):
        print("STDERR:", r.stderr[:800])
    print()
    return r


# ---------- M1 需求密度 ----------
# 3 条需求各 2 条用例，阈值 4 → 3 个需求各缺 2 条，合计缺口 6
# （每条用例的步骤/预期都必须唯一，否则先被第 6 项判语义重复、污染退出码）
sparse = []
for i, rid in enumerate(["R-001", "R-002", "R-003"], 1):
    for j in (1, 2):
        sparse.append(mk(f"TC-{i:02d}-{j:03d}", f"单据{i}操作{j}", rule=rid,
                         ttype="异常测试" if j == 2 else "功能测试",
                         steps=f"1. 进入单据{i}页面\n2. 执行第{j}项操作",
                         expected=f"1. 进入单据{i}页面\n2. 应提示「第{j}项成功」"))

d1 = run(sparse, "M1_warn", ["--min-cases-per-rule", "4"])
d2 = run(sparse, "M1_block", ["--min-cases-per-rule", "4", "--density-mode", "block"])
d3 = run(sparse, "M1_exempt", ["--min-cases-per-rule", "4", "--density-exempt", "R-001,R-002"])
d4 = run(sparse, "M1_off")  # 不传阈值 → 默认 0 → 本项不生效

# ---------- M2 方法一致性 ----------
ONE = [mk("TC-001", "占位", method=("场景法",))]  # 骨架，用于保证覆盖率 100%

m_bad = run([mk("TC-001", "关机时长边界值", method=("边界值分析",),
                steps="1. 进入设置\n2. 查看关机选项",
                expected="1. 进入设置\n2. 展示默认时长")],
            "M2_bad_boundary", ["--method-check", "block", "--scene-rule-mode", "off"])

m_zero = run([mk("TC-001", "有效零值展示", method=("边界值分析",),
                 steps="1. 进入车辆页\n2. 查看电量卡片",
                 expected="1. 进入车辆页\n2. 应展示 0%，不误判为缺失")],
             "M2_ok_zero", ["--method-check", "block", "--scene-rule-mode", "off"])

m_maxmin = run([mk("TC-001", "关机时长边界", method=("边界值分析",),
                   steps="1. 分别选择最小时长\n2. 选择最大时长\n3. 应用并回读",
                   expected="1. 最小时长生效\n2. 最大时长生效\n3. 两端边界值写入正确")],
               "M2_ok_maxmin", ["--method-check", "block", "--scene-rule-mode", "off"])

m_title = run([mk("TC-001", "下载完成不等于安装", method=("边界值分析",),
                  steps="1. 查看下载状态\n2. 查看升级状态",
                  expected="1. 显示下载完成\n2. 仍显示待安装")],
              "M2_title_not_evidence", ["--method-check", "block", "--scene-rule-mode", "off"])

m_eq2 = run([mk("TC-001", "枚举取值展示", method=("等价类划分",),
                steps="1. 进入设置\n2. 查看取值",
                expected="1. 进入设置\n2. 应展示「公制」",
                data={"单位": "公制", "备选": "英制"})],
            "M2_ok_eq2", ["--method-check", "block", "--scene-rule-mode", "off"])

m_eq1 = run([mk("TC-001", "未知状态不画成关闭", method=("等价类划分",),
                steps="1. 进入灯光设置\n2. 查看灯态",
                expected="1. 进入灯光设置\n2. 应显示未知，不误显示为已关闭",
                data={"灯光": "未知"})],
            "M2_thin_eq1", ["--method-check", "block", "--scene-rule-mode", "off"])

m_dt = run([mk("TC-001", "四种组合结果提示准确", method=("判定表法",),
               steps="1. 分别构造已添加已连接/已添加未连接/未添加已连接/未添加未连接\n"
                     "2. 逐一查看状态提示",
               expected="1. 四态构造完成\n2. 各态提示与真实状态一致")],
           "M2_ok_decision_table", ["--method-check", "block", "--scene-rule-mode", "off"])

m_dt_bad = run([mk("TC-001", "提交结果提示", method=("判定表法",),
                   steps="1. 进入流程\n2. 点击提交",
                   expected="1. 进入流程\n2. 应提示成功")],
               "M2_bad_decision_table", ["--method-check", "block", "--scene-rule-mode", "off"])

# ---------- M6 需求级场景配额 ----------
# R-001 三条全正向；R-002 一条异常 → 仅 R-001 应被判缺负向
# （三条正向必须步骤/预期各不相同，否则会被第 6 项判为语义重复，污染退出码）
m6 = [mk("TC-001", "提交订单", rule="R-001", ttype="功能测试",
         steps="1. 进入订单页\n2. 填写金额后提交", expected="1. 进入订单页\n2. 应提示「提交成功」"),
      mk("TC-002", "保存草稿", rule="R-001", ttype="功能测试",
         steps="1. 进入订单页\n2. 点击保存草稿", expected="1. 进入订单页\n2. 应提示「已保存」"),
      mk("TC-003", "查询订单", rule="R-001", ttype="功能测试",
         steps="1. 进入订单列表\n2. 按单号查询", expected="1. 进入订单列表\n2. 应展示对应订单"),
      mk("TC-004", "金额为空提交", rule="R-002", ttype="异常测试",
         steps="1. 清空金额\n2. 点击提交", expected="1. 金额为空\n2. 应提示「金额不能为空」")]
r1 = run(m6, "M6_warn", ["--scene-rule-mode", "warn", "--method-check", "off"])
r2 = run(m6, "M6_block", ["--scene-rule-mode", "block", "--method-check", "off"])
r3 = run(m6, "M6_off", ["--scene-rule-mode", "off", "--method-check", "off"])

checks = {
    # M1
    "M1 命中 3 个低密度需求且合计缺口 6": ("3 个需求用例密度不足" in d1.stdout
                                    and "合计缺口 6 条" in d1.stdout),
    "M1 warn 不改变退出码": d1.returncode == 0,
    "M1 block 阻断": d2.returncode == 1,
    "M1 豁免生效（仅剩 1 个需求）": ("1 个需求用例密度不足" in d3.stdout
                                and "已豁免 2 个" in d3.stdout),
    "M1 阈值 0 时本项不生效": "需求密度" not in d4.stdout,
    # M2
    "M2 边界值无断言判虚标": "方法虚标" in m_bad.stdout and m_bad.returncode == 1,
    "M2 「0%」下界不误判": "条方法虚标" not in m_zero.stdout and m_zero.returncode == 0,
    "M2 「最小值/最大值」不误判": "条方法虚标" not in m_maxmin.stdout and m_maxmin.returncode == 0,
    "M2 标题「不等于」不当作边界证据": "方法虚标" in m_title.stdout,
    "M2 等价类 2 取值不误判": "条方法虚标" not in m_eq2.stdout and m_eq2.returncode == 0,
    "M2 等价类仅 1 取值记为欠展开而非虚标": ("只枚举了 1 个取值" in m_eq1.stdout
                                     and "条方法虚标" not in m_eq1.stdout
                                     and m_eq1.returncode == 0),
    "M2 四组合判定表不误判": "条方法虚标" not in m_dt.stdout and m_dt.returncode == 0,
    "M2 单路径标判定表判虚标": "方法虚标" in m_dt_bad.stdout,
    # M6
    "M6 命中无负向的需求且不误伤 R-002": ("1 个需求无任何异常/边界用例" in r1.stdout
                                   and "R-001" in r1.stdout),
    "M6 block 阻断": r2.returncode == 1,
    "M6 off 不输出": "异常/边界用例（需求级）" not in r3.stdout
                     and "无任何异常/边界用例" not in r3.stdout,
}

print("--- 断言 ---")
bad = 0
for k, v in checks.items():
    print(("PASS " if v else "FAIL ") + k)
    if not v:
        bad += 1
print(f"\n{len(checks) - bad}/{len(checks)} 通过")
print("临时目录:", tmp)
sys.exit(1 if bad else 0)
