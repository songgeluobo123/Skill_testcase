"""第 14 项「预期断言条数」口径回归。

守的是一个已经踩过的坑：
**真实 Excel 用例库把多条断言塞进同一个单元格**，连 "2." 都直接贴在上句末尾
（"…无中文残留2. 特殊字符…"），既不换行也不空格。只数换行 → 把 5 条断言当 1 条
→ 正常的多断言用例被判成"范围性用例"。

实测某真实库：只数换行命中 234 条，改 max(换行, 顺序编号) 后 14 条，220 条假阳性。
假阳性的代价不是"多报几条"，而是使用者按清单去拆根本不用拆的用例。

同时守反方向：3.8-4.4 km/h、v1.0、1.15 秒 这类数值不能被当成编号，
否则会把真范围性用例洗成合格（假阴性），那是更危险的失败方向。
"""
import os
import sys

SKILL = os.environ.get("TC_SKILL") or os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(SKILL, "scripts"))
import prescreen as ps  # noqa: E402

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


def ev(steps, expected, remark=""):
    return ps.range_evidence({"steps": steps, "expected": expected, "remark": remark})


# ---------- 一、编号条目计数本身 ----------
check("n_assert 单行三条编号 → 3",
      ps.n_assert("1. 甲应成立2. 乙应成立3. 丙应成立") == 3,
      ps.n_assert("1. 甲应成立2. 乙应成立3. 丙应成立"))

check("n_assert 换行三条 → 3",
      ps.n_assert("1. 甲应成立\n2. 乙应成立\n3. 丙应成立") == 3)

check("n_assert 数组三条 → 3",
      ps.n_assert(["1. 甲应成立", "2. 乙应成立", "3. 丙应成立"]) == 3)

check("n_assert 无编号单句 → 1", ps.n_assert("应跳转至首页") == 1)

check("n_assert 空值 → 0", ps.n_assert("") == 0)

# ---------- 二、数值不能被当成编号（防假阴性） ----------
check("n_assert 3.8-4.4 km/h 不算编号",
      ps.n_assert("1. 舒适走速度区间=3.8-4.4 km/h") == 1,
      ps.n_assert("1. 舒适走速度区间=3.8-4.4 km/h"))

check("n_assert 版本号 v1.0 不算编号", ps.n_assert("1. 应显示版本 v1.0") == 1)

check("n_assert 1.15 秒不算第二条",
      ps.n_assert("1. 15 秒可正常保存，误差 ≤2 秒") == 1,
      ps.n_assert("1. 15 秒可正常保存，误差 ≤2 秒"))

check("n_assert 编号断链 → 只认前段（1、2 有，4 之前断了）",
      ps.n_assert("1. 甲2. 乙3.8-4.4 km/h 应达标4. 丙") == 2,
      ps.n_assert("1. 甲2. 乙3.8-4.4 km/h 应达标4. 丙"))

check("n_assert 1|4、2|4 分段标记不算编号",
      ps.n_assert("1. 段标签按 1|4、2|4、3|4、4|4 递增") == 1,
      ps.n_assert("1. 段标签按 1|4、2|4、3|4、4|4 递增"))

# ---------- 三、真实库形态：不该再被判范围性 ----------
STEPS4 = "1. 分别切换至 简体中文 / English / Deutsch / Español 四语种2. 冷启动观察品牌语"

# 真实原文：TC-启动-004（换行 1，实际 5 条断言）
R1 = "1. 各语种下品牌语与进度提示均按对应语种正确渲染，无中文/英文残留2. 特殊字符（如 Deutsch 的 ä/ö/ü/ß）应正常显示3. 长文案应自动换行不截断"
hit, objs, n, _ = ev(STEPS4, R1)
check("真实形态 单行 3 条编号 → 不再判范围性",
      hit and objs >= 3 and n >= 3,
      f"hit={hit} objs={objs} n={n}")
check("真实形态 走 warning 而不是 strong",
      n > 1, f"n={n}")

# 真实原文：TC-引导-156（换行 1，实际 4 条，含冒号引号）
R2 = '1.标题："智能训练"白色加粗2.副标题："基础信息1/3"3."男生""女生""保密"选项按钮展示正确4.出生日期显示正确'
hit, objs, n, _ = ev("1. 逐项核对 标题、副标题、选项按钮、出生日期 四处文案",
                     R2)
check("真实形态 带引号的中文标点内编号 → 计到 4 条", n == 4, f"n={n}")
check("真实形态 带引号 不判范围性", n > 1, f"n={n}")

# ---------- 四、真范围性用例必须照旧报出（防假阴性） ----------
hit, objs, n, words = ev("1. 依次查看 基础信息、当前能力、节奏与方向页 的步骤指示",
                         "1.步骤指示正确")
check("真范围性 单条断言仍被报出", hit and objs >= 3 and n == 1,
      f"hit={hit} objs={objs} n={n}")

hit, objs, n, _ = ev("1.逐项核对 全部选项、全部文案、全部按钮 的展示",
                     "1.各等级徽章（灰色/紫色/金色）样式正确展示")
check("真范围性 括号内并列不算多条断言", n == 1, f"n={n}")

# 备注列已展开 → 降级，不因口径改动而失去豁免
hit, objs, n, _ = ev("1. 分别校验 亮度、音量、亮度记忆",
                     "1. 全部应生效",
                     remark="亮度=50 应生效；音量=80 应生效；亮度记忆=开 应生效")
check("备注展开 仍算出 n=1（豁免由外层判定）", n == 1, f"n={n}")

# ---------- 五、源码级防回退 ----------
SRC = open(os.path.join(SKILL, "scripts", "prescreen.py"), encoding="utf-8").read()
check("源码 第 14 项用的是 n_assert 而不是 len(_lines(...))",
      "n_assert(c.get(\"expected\"))" in SRC)
check("源码 保留了 ITEM_SEQ_RE 的负向断言（不把数值当编号）",
      "ITEM_SEQ_RE = re.compile" in SRC
      and "(?<!\\d)" in SRC and '(?!\\d)")' in SRC)

print("\n" + "=" * 30)
print(f"通过 {PASS}/{PASS + FAIL}")
if FAILS:
    print("失败:", FAILS)
sys.exit(1 if FAIL else 0)
