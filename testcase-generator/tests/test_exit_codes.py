"""退出码语义回归：0=通过 / 1=不达标 / 2=输入·参数错误 / 3=脚本自身崩溃 / 4=环境缺依赖。

为什么单独立一个文件：
早期所有非 0 都返回 1，脚本崩溃会被当成"数据不达标"，让人对着不存在的
质量问题返工。退出码是调用方（流水线 / CI / agent）唯一的判据，
各态必须互不混用，且每个脚本都得有。

为什么后来又加了 4：缺 openpyxl 被报成 2（参数错）时，调用方会去查路径、
调参数——而该做的是 pip install。非 0 背后是几种完全不同的动作，
就必须有几种码。
"""
import io
import json
import os
import re
import subprocess
import sys
import tempfile

# 技能目录：可用环境变量 TC_SKILL 覆盖，默认取 tests/ 的上级目录。
# 这样脚本在"本地技能目录"与"仓库克隆副本"两处都能跑，不再依赖本机绝对路径。
SKILL = os.environ.get("TC_SKILL") or os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(SKILL, "scripts")
PY = sys.executable
TMP = tempfile.mkdtemp(prefix="exit_codes_")
ENV = dict(os.environ, PYTHONIOENCODING="utf-8")

PASS = FAIL = 0
FAILS = []

# 消费数据的脚本必须四态齐全；selftest_* 是测试脚本，只要求有 3 的兜底
REQUIRED = [
    "prescreen.py", "matrix_lint.py", "coverage_audit.py", "input_readiness.py",
    "score_testcases.py", "mutation_audit.py", "defect_audit.py",
    "extract_requirements.py", "map_coverage.py", "to_excel.py", "to_xmind.py",
    "memory_io.py", "read_xmind.py", "read_ui_image.py",
]


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"PASS {name}")
    else:
        FAIL += 1
        FAILS.append(name)
        print(f"FAIL {name}  {detail}")


def run(script, args):
    return subprocess.run([PY, os.path.join(SCRIPTS, script)] + args,
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", env=ENV)


# ---------- 静态：每个脚本都要有 3 的兜底 ----------
missing_wrapper = []
for name in REQUIRED:
    p = os.path.join(SCRIPTS, name)
    if not os.path.exists(p):
        missing_wrapper.append(f"{name}(不存在)")
        continue
    t = io.open(p, encoding="utf-8").read()
    ok = ("[内部错误]" in t) and ("sys.exit(3)" in t) and ("except SystemExit" in t)
    if not ok:
        missing_wrapper.append(name)
check("全部脚本都有 exit 3 崩溃兜底", not missing_wrapper, str(missing_wrapper))

# 兜底必须在 SystemExit 之前放行，否则 argparse --help（退出码 0）会被吞成 3
bad_order = []
for name in REQUIRED:
    p = os.path.join(SCRIPTS, name)
    if not os.path.exists(p):
        continue
    t = io.open(p, encoding="utf-8").read()
    i_se = t.find("except SystemExit")
    i_doc = t.find('if __name__ == "__main__":')
    if i_se != -1 and i_doc != -1 and i_se < i_doc:
        bad_order.append(name)   # SystemExit 处理写到了守卫外面
check("except SystemExit 都在守卫之内", not bad_order, str(bad_order))

# ---------- 动态：--help 必须 exit 0，不能被兜底误伤 ----------
help_bad = []
for name in REQUIRED:
    r = run(name, ["--help"])
    if r.returncode != 0:
        help_bad.append(f"{name}={r.returncode}")
check("--help 一律 exit 0（兜底不吞 SystemExit）", not help_bad, str(help_bad))

# ---------- 动态：输入错误一律 2 ----------
d = TMP
missing_file = os.path.join(d, "does_not_exist.json")
ok2, bad2 = 0, []
for name in ("prescreen.py", "score_testcases.py", "matrix_lint.py",
             "coverage_audit.py", "input_readiness.py", "mutation_audit.py"):
    r = run(name, [missing_file])
    if r.returncode == 2:
        ok2 += 1
    else:
        bad2.append(f"{name}={r.returncode}")
check("文件不存在一律 exit 2", not bad2, str(bad2))

# ---------- 动态：真正的内部崩溃一律 3 ----------
bad_cases = os.path.join(d, "bad.json")
with open(bad_cases, "w", encoding="utf-8") as f:
    json.dump(["not-a-dict"], f, ensure_ascii=False)

r_crash = run("prescreen.py", [bad_cases, "--coverage-min", "0"])
check("prescreen 内部崩溃 exit 3", r_crash.returncode == 3, f"exit={r_crash.returncode}")
check("prescreen 崩溃时明示『不是数据不达标』",
      "不是数据不达标" in r_crash.stderr, r_crash.stderr[-300:])
check("prescreen 崩溃时不打印『预审不通过』",
      "预审不通过" not in r_crash.stdout, r_crash.stdout[-300:])

r_crash2 = run("score_testcases.py", [bad_cases])
check("score_testcases 内部崩溃 exit 3", r_crash2.returncode == 3,
      f"exit={r_crash2.returncode}")

# ---------- 四态齐备 ----------
codes = {r_crash.returncode, r_crash2.returncode, r_crash and 2, 0}
check("四态 0/1/2/3 互不混用",
      {0, 1, 2, 3}.issuperset({r_crash.returncode}) and
      r_crash.returncode != 1 and r_crash.returncode != 2,
      f"crash={r_crash.returncode}")

# ---------- 静态：缺依赖不许伪装成「参数错」 ----------
# to_excel.py 早期在 import 期 sys.exit(2)：既让 --help 失效，又把"缺 openpyxl"
# 报成参数错。调用方看到 2 会去改参数，永远修不好。现在必须走 4。
p_excel = os.path.join(SCRIPTS, "to_excel.py")
t_excel = io.open(p_excel, encoding="utf-8").read()
guard = t_excel[:t_excel.find("COLUMNS = ")] if "COLUMNS = " in t_excel else t_excel
check("to_excel import 期不退出（--help 才可用）",
      "sys.exit" not in guard, "import 守卫里仍有 sys.exit")
check("to_excel 用 HAS_OPENPYXL 标志而非立即退出",
      "HAS_OPENPYXL" in t_excel, "未引入 HAS_OPENPYXL")
check("to_excel 缺依赖返回 4 而非 2",
      "return 4" in t_excel and "HAS_OPENPYXL" in t_excel, "未见 return 4")

# ---------- 文档同步：退出码表必须写进文档 ----------
corpus = {}
for fn in ("SKILL.md", os.path.join("references", "quality_prescreen.md")):
    p = os.path.join(SKILL, fn)
    if os.path.exists(p):
        corpus[fn] = io.open(p, encoding="utf-8").read()
joined = "\n".join(corpus.values())
check("文档含退出码 3 的说明", "3" in joined and ("内部" in joined or "崩溃" in joined),
      "文档未提 exit 3")
check("文档区分『崩溃』与『不达标』",
      ("不是" in joined and "不达标" in joined) or "崩溃" in joined,
      "文档未区分崩溃与不达标")
check("文档含退出码 4（环境缺依赖）的说明",
      "`4`" in joined or "4" in joined and "依赖" in joined,
      "文档未提 exit 4 / 依赖缺失")

print("\n" + "=" * 30)
print(f"通过 {PASS}/{PASS + FAIL}")
if FAILS:
    print("失败:", FAILS)
print("临时目录:", TMP)
sys.exit(1 if FAIL else 0)
