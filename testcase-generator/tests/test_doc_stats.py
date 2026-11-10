"""doc_stats.py 回归：文档计数必须能从代码派生，且能自动修回。

治的病：加了脚本忘了改 README 的「17 个」、加了闸门忘了改「13 项」。
这类漂移不会报错、不会崩溃，只会让文档慢慢变成假话。所以它必须能被机械检出，
而且修法要一条命令——否则没人修。
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.environ.get("TC_SKILL") or os.path.dirname(HERE)
PY = sys.executable
TMP = tempfile.mkdtemp(prefix="docstats_")

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


def run(script, args, skill=None):
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    if skill:
        env["TC_SKILL"] = skill
    return subprocess.run([PY, os.path.join(SKILL, "scripts", script)] + args,
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", env=env)


def stats(skill=None):
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    if skill:
        env["TC_SKILL"] = skill
    return subprocess.run([PY, os.path.join(SKILL, "scripts", "doc_stats.py"),
                           "--check", "--format", "json"],
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", env=env)


# ---------- 当前树应当一致 ----------
r = run("doc_stats.py", ["--check"])
check("当前技能树计数一致 exit 0", r.returncode == 0, f"exit={r.returncode} {r.stdout[-300:]}")
check("报告实测值", "实测" in r.stdout and "预审" in r.stdout, r.stdout[:200])
check("一致时打印 OK", "[OK]" in r.stdout, r.stdout[-200:])

# ---------- 注入漂移：把预审项数改错，--check 必须发现 ----------
copy = os.path.join(TMP, "sk")
shutil.copytree(SKILL, copy, ignore=shutil.ignore_patterns("tests", "__pycache__"))

qp = os.path.join(copy, "references", "quality_prescreen.md")
s = open(qp, encoding="utf-8").read()
s2 = s.replace("## 14 项检查 + 默认阈值", "## 13 项检查 + 默认阈值", 1)
assert s2 != s, "注入失败：找不到标题"
open(qp, "w", encoding="utf-8", newline="\n").write(s2)

r = run("doc_stats.py", ["--check"], skill=copy)
check("注入预审项数漂移 → exit 1", r.returncode == 1, f"exit={r.returncode}")
check("漂移被点名（含应为 N）", "漂移" in r.stdout and "应为 14" in r.stdout, r.stdout[-400:])

# ---------- --apply 能修回 ----------
r = run("doc_stats.py", ["--apply"], skill=copy)
check("--apply exit 0", r.returncode == 0, f"exit={r.returncode}")
r = run("doc_stats.py", ["--check"], skill=copy)
check("--apply 后复查一致", r.returncode == 0, f"exit={r.returncode} {r.stdout[-300:]}")

fixed = open(qp, encoding="utf-8").read()
check("--apply 只改数字、不动其余文本",
      re.sub(r"\d+", "#", s) == re.sub(r"\d+", "#", fixed),
      "除数字外还有其他文本被改动")
check("--apply 结果确实是 14", "## 14 项检查 + 默认阈值" in fixed, fixed[:120])

# ---------- scripts 数漂移也能修 ----------
rd = os.path.join(copy, "README.md")
s = open(rd, encoding="utf-8").read()
import re
s2, n = re.subn(r"# 可执行脚本（\d+ 个，Python", "# 可执行脚本（99 个，Python", s, count=1)
assert n == 1, "注入失败：找不到 scripts 计数行"
open(rd, "w", encoding="utf-8", newline="\n").write(s2)

r = run("doc_stats.py", ["--check"], skill=copy)
check("scripts 数漂移被发现", r.returncode == 1 and "可执行脚本" in r.stdout, r.stdout[-400:])
run("doc_stats.py", ["--apply"], skill=copy)
r = run("doc_stats.py", ["--check"], skill=copy)
check("scripts 数漂移可修回", r.returncode == 0, f"exit={r.returncode}")

# ---------- 文件缺失不应崩溃 ----------
os.remove(os.path.join(copy, "README.en.md"))
r = run("doc_stats.py", ["--check"], skill=copy)
check("缺文件只跳过不崩溃（exit 0 或 1，非 3）",
      r.returncode in (0, 1), f"exit={r.returncode}")
check("缺文件有提示", "文件不存在" in r.stdout, r.stdout[-300:])

# ---------- 路径不存在 → exit 2 ----------
r = run("doc_stats.py", ["--check"], skill=os.path.join(TMP, "no_such_dir"))
check("技能目录不存在 exit 2", r.returncode == 2, f"exit={r.returncode}")

# ---------- 互斥参数 ----------
import subprocess
rc = subprocess.run([PY, os.path.join(SKILL, "scripts", "doc_stats.py")],
                    capture_output=True, text=True, env=dict(os.environ, PYTHONIOENCODING="utf-8"))
check("既不 --check 也不 --apply 时报参数错（exit 2）", rc.returncode == 2,
      f"exit={rc.returncode}")

print("\n" + "=" * 30)
print(f"通过 {PASS}/{PASS + FAIL}")
if FAILS:
    print("失败:", FAILS)
print("临时目录:", TMP)
sys.exit(1 if FAIL else 0)
