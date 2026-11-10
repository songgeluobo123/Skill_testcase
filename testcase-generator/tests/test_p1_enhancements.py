"""P1 三项增强的回归：方法词表外置 / 数据规则库可执行 / 矩阵假设占比可观测。

这三项的共同动机都是同一类缺陷：
**"配了就等于生效了吗？"——不是。** 早期的 `--rules` 是整体替换，
项目一传自己的规则，内置三条就静默失效了；词表写死在代码里，
换个中文说法就漏判。所以这里的重点全是"增补而不是替换"和"配错要能看见"。
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
PY = sys.executable
ENV = dict(os.environ, PYTHONIOENCODING="utf-8")
TMP = tempfile.mkdtemp(prefix="p1_")

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


def write(name, obj):
    p = os.path.join(TMP, name)
    with open(p, "w", encoding="utf-8") as f:
        if isinstance(obj, str):
            f.write(obj)
        else:
            json.dump(obj, f, ensure_ascii=False)
    return p


def run(script, args):
    return subprocess.run([PY, os.path.join(SKILL, "scripts", script)] + args,
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", env=ENV)


def case(**over):
    c = {
        "id": "TC-A-001", "name": "档位触顶判定", "module": "设置",
        "priority": "P2", "test_type": "功能测试", "precondition": "已登录",
        "steps": "把档位调到触顶位置并观察", "expected": "1. 应显示 5 档",
        "test_data": {"档位": "5"}, "coverage_rule": "R-001",
        "design_method": ["边界值分析"],
    }
    c.update(over)
    return c


# ==================== P1-4 方法一致性词表外置 ====================
def prescreen_words(lex_path=None):
    p = write("c_lex.json", [case()])
    args = [p, "--coverage-min", "0"]
    if lex_path:
        args += ["--method-lexicon", lex_path]
    return run("prescreen.py", args)


r = prescreen_words()
check("词表·内置词表无『触顶』→ 判边界值虚标",
      "方法虚标" in r.stdout, r.stdout[-400:])

lex = write("lex.json", {"boundary": ["触顶"]})
r = prescreen_words(lex)
check("词表·增补『触顶』后转通过", "方法虚标" not in r.stdout, r.stdout[-400:])
check("词表·提示已合并条数", "方法词表已合并" in r.stdout, r.stdout[-300:])

# 关键：增补不能顶掉内置词。换一条只用内置词（"上限"）的用例，加词表后仍应通过
p2 = write("c_builtin.json", [case(steps="把档位调到上限并观察",
                                   expected="1. 应显示 5 档")])
lex2 = write("lex2.json", {"boundary": ["触顶"]})
r2 = run("prescreen.py", [p2, "--coverage-min", "0", "--method-lexicon", lex2])
check("词表·增补不顶掉内置词（『上限』仍生效）",
      "方法虚标" not in r2.stdout, r2.stdout[-400:])

bad = write("lex_bad.json", '{"boundary": 123}')
r = prescreen_words(bad)
check("词表·格式错 exit 2", r.returncode == 2, f"exit={r.returncode}")
check("词表·格式错有明确提示", "必须是字符串数组" in r.stderr, r.stderr[-200:])

bad2 = write("lex_bad2.json", '{"boundary_literal": "[unclosed"}')
r = prescreen_words(bad2)
check("词表·正则语法错 exit 2（不在判用例时才炸）",
      r.returncode == 2, f"exit={r.returncode}")

# 内置类归属词补了「X值」型表述
p3 = write("c_eq.json", [case(steps="输入空值后提交", expected="1. 应提示不能为空",
                             test_data={"档位": "5"},
                             design_method=["等价类划分"])])
r3 = run("prescreen.py", [p3, "--coverage-min", "0"])
check("等价类·『空值』算类归属证据（不再判虚标）",
      "方法虚标" not in r3.stdout, r3.stdout[-400:])

# ==================== P1-6 数据规则库 ====================
def score(data, rules=None, mode=None):
    p = write("cs.json", [case(test_data=data, priority="P1",
                              steps="在页面填表并点击提交按钮查看返回结果",
                              expected="1. 应提示保存成功")])
    args = [p]
    if rules:
        args += ["--rules", rules]
    if mode:
        args += ["--rules-mode", mode]
    return run("score_testcases.py", args)


# 内置规则：手机号 12345 应被指出
r = score({"手机号": "12345"})
check("数据规则·内置 phone 规则生效", "不符合" in r.stdout, r.stdout[-400:])

ext = write("rules.json", {"助力档位": {"type": "range", "min": 0, "max": 5, "hint": "0~5 档"}})
r = score({"手机号": "12345", "助力档位": "7"}, rules=ext)
check("数据规则·merge 默认同时命中内置与外部规则",
      "手机号" in r.stdout and "助力档位" in r.stdout, r.stdout[-500:])
check("数据规则·merge 提示条数", "内置 3 条 + 外部 1 条" in r.stdout, r.stdout[-400:])

r = score({"手机号": "12345", "助力档位": "7"}, rules=ext, mode="replace")
check("数据规则·replace 模式确实丢掉内置规则（证明旧行为有害）",
      "手机号" not in r.stdout and "助力档位" in r.stdout, r.stdout[-500:])

# 新类型：length / regex
r = score({"验证码": "123"}, rules=write("r_len.json", {"验证码": {"type": "length", "min": 6, "max": 6}}))
check("数据规则·length 类型命中", "长度" in r.stdout, r.stdout[-400:])

r = score({"MAC地址": "zz:zz"}, rules=write(
    "r_re.json", {"MAC地址": {"type": "regex", "pattern": "^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$",
                           "hint": "6 组冒号分隔十六进制"}}))
check("数据规则·regex 类型命中", "不符合" in r.stdout, r.stdout[-400:])

# 未知 type 不能静默放行
r = score({"奇怪字段": "x"}, rules=write(
    "r_bad.json", {"奇怪字段": {"type": "no_such_type"}}))
check("数据规则·未知 type 不静默放行", "不受支持" in r.stdout, r.stdout[-400:])

# 合法值不应误报
r = score({"手机号": "13800138000", "订单金额": "0.01"})
check("数据规则·合法值零误报", "不符合" not in r.stdout and "大于最大值" not in r.stdout,
      r.stdout[-400:])

# ==================== P1-5 矩阵假设占比可观测 ====================
matrix = """# 测试矩阵

| 字段 | 类型 | 取值域 | 类/边界点 | 类别 | 预期要点 | 覆盖 R-ID | 用例 ID |
|---|---|---|---|---|---|---|---|
| SOC | 数值 | 0~100 | 0 | 边界 | 显示 0% | R-001 |  |
| SOC | 数值 | 0~100 | 100 | 边界 | 显示 100% | R-001 |  |
| SOC | 数值 | 0~100 | 50 | 有效类 | 显示 50% | R-001 |  |
| SOC | 数值 | 0~100 | -1 | 无效类 | 提示越界 | R-001 |  |
| SOC | 数值 | 0~100 | 101 | 无效类 | 提示越界 | R-001 |  |
| 档位 | 枚举 | 0~5 | 0 | 边界 | 无助力 | R-002 |  |
| 档位 | 枚举 | 0~5 | 5 | 边界 | 最高档 | R-002 |  |
| 档位 | 枚举 | 0~5 | 3 | 有效类 | 中档 | R-002 |  |
| 档位 | 枚举 | 0~5 | 6 [假设] | 无效类 | 提示越界 | R-002 |  |
"""
mp = write("m.md", matrix)
r = run("matrix_lint.py", [mp, "--stage", "design", "--assume-stats"])
check("矩阵·--assume-stats 输出分布表",
      "假设] 行分布" in r.stdout and "档位" in r.stdout, r.stdout[-500:])
check("矩阵·--assume-stats 给出校准方法与样本要求",
      "P90" in r.stdout and "5 份" in r.stdout, r.stdout[-600:])
check("矩阵·--assume-stats 明示默认值未校准",
      "经验值" in r.stdout or "未校准" in r.stdout, r.stdout[-600:])
check("矩阵·[假设] 行确实被计为假设（1 条）",
      "1" in r.stdout.split("档位")[1][:40] if "档位" in r.stdout else False,
      r.stdout[-500:])

# 不带 --assume-stats 时不应打印分布
r = run("matrix_lint.py", [mp, "--stage", "design"])
check("矩阵·默认不打印分布（不污染常规输出）",
      "假设] 行分布" not in r.stdout, r.stdout[-300:])

print("\n" + "=" * 30)
print(f"通过 {PASS}/{PASS + FAIL}")
if FAILS:
    print("失败:", FAILS)
print("临时目录:", TMP)
sys.exit(1 if FAIL else 0)
