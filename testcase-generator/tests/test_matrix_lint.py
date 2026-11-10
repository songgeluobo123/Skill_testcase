"""matrix_lint.py（Step 3.5 等价类/边界值矩阵）回归测试。

每个反例都对应一个真实会犯的写法错误；两条"应通过"样例对应两个真实的误判坑：
  · 字符串字段不强制边界点（否则每次都被逼着给文本造边界）
  · [假设] 行必须从边界点计数里剔除（否则靠编数据就能"凑够 3 个边界"）

运行：python test_matrix_lint.py
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
SCRIPT = os.path.join(SKILL, "scripts", "matrix_lint.py")
PY = sys.executable
TMP = tempfile.mkdtemp(prefix="matrix_lint_")

HEAD = "| # | 字段 | 类型 | 取值域 | 类/边界点 | 类别 | 预期要点 | 覆盖 R-ID | 用例 ID |\n" \
       "|---|---|---|---|---|---|---|---|---|\n"


def row(n, f, tp, dom, pt, kd, exp, rid, cid):
    return f"| {n} | {f} | {tp} | {dom} | {pt} | {kd} | {exp} | {rid} | {cid} |\n"


def write(name, body):
    p = os.path.join(TMP, f"{name}.md")
    with open(p, "w", encoding="utf-8") as fh:
        fh.write(body)
    return p


def run(path, extra=()):
    r = subprocess.run([PY, SCRIPT, path] + list(extra), capture_output=True, text=True)
    return r


results = {}

# ---------- 1. 合规样例：数值 3 边界 + 枚举 3 边界 + 字符串不强制 ----------
good = "# 合规样例\n\n" + HEAD
good += row(1, "SOC", "数值(0–100%)", "0–100%", "1–99", "有效类", "展示真实值与单位", "R-001", "TC-001")
good += row(2, "SOC", "数值(0–100%)", "0–100%", "0", "边界", "应展示 0%，不误判为缺失", "R-001", "TC-002")
good += row(3, "SOC", "数值(0–100%)", "0–100%", "100", "边界", "应展示 100%，不回绕为 0", "R-001", "TC-003")
good += row(4, "SOC", "数值(0–100%)", "0–100%", "101", "边界", "应提示超范围", "R-001", "TC-004")
good += row(5, "SOC", "数值(0–100%)", "0–100%", "0xFF", "无效类", "显示不可用", "R-001", "TC-005")
good += row(6, "档位", "枚举(0–5)", "0–5", "1–4", "有效类", "展示真实档位", "R-002", "TC-006")
good += row(7, "档位", "枚举(0–5)", "0–5", "0", "边界", "应展示 0 档", "R-002", "TC-007")
good += row(8, "档位", "枚举(0–5)", "0–5", "5", "边界", "应展示 5 档", "R-002", "TC-008")
good += row(9, "档位", "枚举(0–5)", "0–5", "6", "边界", "显示不可用，不映射为 5 档", "R-002", "TC-009")
good += row(10, "档位", "枚举(0–5)", "0–5", "未知", "无效类", "显示不可用", "R-002", "TC-010")
good += row(11, "车型名", "字符串", "≤32 字", "普通车型名", "有效类", "应完整展示", "R-003", "TC-011")
good += row(12, "车型名", "字符串", "≤32 字", "33 字超长名", "无效类", "应提示超长/截断", "R-003", "TC-012")
gp = write("good", good)
g = run(gp)

# ---------- 2. 列数少一列（漏「类/边界点」）→ 必须阻断而非静默错位 ----------
bad_col = "# 少一列\n\n" + HEAD
bad_col += "| 1 | SOC | 数值 | 0–100% | 有效类 | 展示真实值 | R-001 | TC-001 |\n"
bp = write("bad_col", bad_col)
b_col = run(bp)

# ---------- 3. 数值字段边界点不足（只有 2 个） ----------
few = "# 边界不足\n\n" + HEAD
few += row(1, "SOC", "数值(0–100%)", "0–100%", "1–99", "有效类", "展示真实值", "R-001", "TC-001")
few += row(2, "SOC", "数值(0–100%)", "0–100%", "0", "边界", "应展示 0%", "R-001", "TC-002")
few += row(3, "SOC", "数值(0–100%)", "0–100%", "100", "边界", "应展示 100%", "R-001", "TC-003")
few += row(4, "SOC", "数值(0–100%)", "0–100%", "0xFF", "无效类", "显示不可用", "R-001", "TC-004")
fp = write("few", few)
f = run(fp)

# ---------- 4. 未消费等价类（用例 ID 为空） ----------
unc = "# 未消费\n\n" + HEAD
unc += row(1, "SOC", "数值(0–100%)", "0–100%", "0", "边界", "应展示 0%", "R-001", "TC-001")
unc += row(2, "SOC", "数值(0–100%)", "0–100%", "100", "边界", "应展示 100%", "R-001", "")
unc += row(3, "SOC", "数值(0–100%)", "0–100%", "101", "边界", "应提示超范围", "R-001", "TC-003")
unc += row(4, "SOC", "数值(0–100%)", "0–100%", "0xFF", "无效类", "显示不可用", "R-001", "TC-004")
up = write("unc", unc)
u = run(up, ["--stage", "full"])     # L3 只在 full 档阻断
u_design = run(up)                  # design 档（建矩阵阶段）不得死锁

# ---------- 5. 编造需求 ID ----------
fab = "# 编造需求\n\n" + HEAD
fab += row(1, "SOC", "数值", "0–100%", "0", "边界", "应展示 0%", "R-001", "TC-001")
fab += row(2, "SOC", "数值", "0–100%", "100", "边界", "应展示 100%", "R-999", "TC-002")
fab += row(3, "SOC", "数值", "0–100%", "101", "边界", "应提示超范围", "R-001", "TC-003")
fab += row(4, "SOC", "数值", "0–100%", "0xFF", "无效类", "显示不可用", "R-001", "TC-004")
rul = os.path.join(TMP, "rules.json")
json.dump(["R-001", "R-002", "R-003"], open(rul, "w", encoding="utf-8"), ensure_ascii=False)
fb = run(write("fab", fab), ["--requirement-rules", rul])

# ---------- 6. [假设] 行占比超限 ----------
asm = "# 假设超限\n\n" + HEAD
asm += row(1, "SOC", "数值", "0–100%", "0", "边界", "应展示 0% [假设]", "R-001", "TC-001")
asm += row(2, "SOC", "数值", "0–100%", "100", "边界", "应展示 100% [假设]", "R-001", "TC-002")
asm += row(3, "SOC", "数值", "0–100%", "101", "边界", "应提示超范围 [假设]", "R-001", "TC-003")
asm += row(4, "SOC", "数值", "0–100%", "0xFF", "无效类", "显示不可用", "R-001", "TC-004")
ap = write("asm", asm)
a = run(ap, ["--assume-max", "0.5"])

# ---------- 7. [假设] 行不得计入边界点数（关键） ----------
# 2 个真边界 + 2 个假设边界：若把假设算进去就"凑够 3 个"，那就白设这道闸门了
mix = "# 假设凑数\n\n" + HEAD
mix += row(1, "SOC", "数值", "0–100%", "1–99", "有效类", "展示真实值", "R-001", "TC-001")
mix += row(2, "SOC", "数值", "0–100%", "0", "边界", "应展示 0%", "R-001", "TC-002")
mix += row(3, "SOC", "数值", "0–100%", "100", "边界", "应展示 100%", "R-001", "TC-003")
mix += row(4, "SOC", "数值", "0–100%", "-1 [假设]", "边界", "应提示非法", "R-001", "TC-004")
mix += row(5, "SOC", "数值", "0–100%", "101 [假设]", "边界", "应提示超范围", "R-001", "TC-005")
mix += row(6, "SOC", "数值", "0–100%", "0xFF", "无效类", "显示不可用", "R-001", "TC-006")
mp = write("mix", mix)
mx = run(mp, ["--assume-max", "0.9"])

# ---------- 8. 引用不存在的用例 ID ----------
cases = os.path.join(TMP, "cases.json")
json.dump([{"id": "TC-001"}, {"id": "TC-002"}], open(cases, "w", encoding="utf-8"))
np_ = run(gp, ["--cases", cases])

# ---------- 8b. L10 反向校验：用例库中存在矩阵未引用的用例 ----------
cases_extra = os.path.join(TMP, "cases_extra.json")
json.dump([{"id": "TC-001"}, {"id": "TC-002"}, {"id": "TC-999"}],
          open(cases_extra, "w", encoding="utf-8"))
l10 = run(gp, ["--stage", "full", "--cases", cases_extra])

# ---------- 9. 表头缺「用例 ID」列 → 退出码 2 ----------
noh = "# 缺列\n\n| # | 字段 | 类/边界点 | 类别 |\n|---|---|---|---|\n| 1 | SOC | 0 | 边界 |\n"
nh = run(write("noh", noh))

# ---------- 10. 分模块多表合并 ----------
multi = "# 分模块\n\n## A\n\n" + HEAD
multi += row(1, "SOC", "数值", "0–100%", "0", "边界", "应展示 0%", "R-001", "TC-001")
multi += row(2, "SOC", "数值", "0–100%", "100", "边界", "应展示 100%", "R-001", "TC-002")
multi += row(3, "SOC", "数值", "0–100%", "101", "边界", "应提示超范围", "R-001", "TC-003")
multi += row(4, "SOC", "数值", "0–100%", "0xFF", "无效类", "显示不可用", "R-001", "TC-004")
multi += "\n## B\n\n" + HEAD
multi += row(5, "档位", "枚举", "0–5", "0", "边界", "应展示 0 档", "R-002", "TC-005")
multi += row(6, "档位", "枚举", "0–5", "5", "边界", "应展示 5 档", "R-002", "TC-006")
multi += row(7, "档位", "枚举", "0–5", "6", "边界", "显示不可用", "R-002", "TC-007")
multi += row(8, "档位", "枚举", "0–5", "未知", "无效类", "显示不可用", "R-002", "TC-008")
ml = run(write("multi", multi), ["--format", "json"])

# ---------- 断言 ----------
checks = {
    "合规矩阵通过（exit=0）": g.returncode == 0,
    "字符串字段不强制边界点": "该类型不强制边界" in g.stdout and "| 车型名 | 字符串 | 1 | 1 | 0 | ✅ 该类型不强制边界 |" in g.stdout,
    "列数少一列被阻断（L1b）": b_col.returncode == 1 and "L1b" in b_col.stdout,
    "列数错误不静默错位（不出现误判类别）": "类别 `" not in b_col.stdout,
    "数值字段边界点不足被阻断（L2）": f.returncode == 1 and "L2" in f.stdout and "边界点仅 2" in f.stdout,
    "未消费等价类被阻断（L3，full 档）": u.returncode == 1 and "未消费" in u.stdout,
    "建矩阵阶段不因用例 ID 为空而死锁（design 档 exit=0）": u_design.returncode == 0,
    "design 档把空用例 ID 记为待回填": "待回填用例 ID" in u_design.stdout,
    "full 档反向查出未被矩阵引用的用例（L10）": (
        "未被任何矩阵行引用" in l10.stdout and "TC-999" in l10.stdout),
    "编造需求 ID 被阻断（L4）": fb.returncode == 1 and "R-999" in fb.stdout,
    "假设行占比超限被阻断（L5）": a.returncode == 1 and "L5" in a.stdout,
    "[假设] 行不计入边界点数": mx.returncode == 1 and "边界点仅 2" in mx.stdout,
    "引用不存在用例被阻断（L9）": np_.returncode == 1 and "不存在的用例" in np_.stdout,
    "表头缺列退出码 2": nh.returncode == 2,
    "多表合并字段数为 2": ml.returncode == 0 and json.loads(ml.stdout)["fields"] and
                          len(json.loads(ml.stdout)["fields"]) == 2,
    "json 输出含 pass 字段": json.loads(ml.stdout)["pass"] is True,
}

print("--- 断言 ---")
bad = 0
for k, v in checks.items():
    print(("PASS " if v else "FAIL ") + k)
    if not v:
        bad += 1
        if k in ("列数少一列被阻断（L1b）", "列数错误不静默错位（不出现误判类别）"):
            print("  stdout:", b_col.stdout[:500])
        if k == "字符串字段不强制边界点":
            print("  stdout 片段:", g.stdout[:800])
print(f"\n{len(checks) - bad}/{len(checks)} 通过")
print("临时目录:", TMP)
sys.exit(1 if bad else 0)
