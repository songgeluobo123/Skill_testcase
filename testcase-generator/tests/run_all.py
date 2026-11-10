#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一键跑技能的全部回归。改任何脚本前先跑这个，全绿再动手。

用法：
  python tests/run_all.py              # 跑全部
  python tests/run_all.py prescreen    # 只跑文件名含 prescreen 的
  python tests/run_all.py --list       # 只列不跑

退出码：0 全绿｜1 有失败｜2 找不到用例或环境错误（3 = 运行器自身崩溃，理论上不该出现）

为什么要有这个入口：
回归散在多个文件里时，"改完脚本要跑哪些"靠人记。记漏一次，一次回归失效；
失效的回归等于没有回归，而且比没有更糟——它给你一个"我验证过了"的错觉。
"""
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.environ.get("TC_SKILL") or os.path.dirname(HERE)


def find_tests(keyword=None):
    """两类都收：tests/test_*.py（本目录）+ scripts/selftest_*.py（随技能发布的离线自测）。

    自测脚本用"通过 N/M"汇总、不打逐条 PASS 行，计数逻辑在下面按退出码兜底。
    """
    out = []
    for fn in sorted(os.listdir(HERE)):
        if fn.startswith("test_") and fn.endswith(".py"):
            if not keyword or keyword in fn:
                out.append((fn, os.path.join(HERE, fn)))
    sd = os.path.join(SKILL, "scripts")
    if os.path.isdir(sd):
        for fn in sorted(os.listdir(sd)):
            if fn.startswith("selftest_") and fn.endswith(".py"):
                if not keyword or keyword in fn:
                    out.append((fn, os.path.join(sd, fn)))
    return out


def preflight():
    """跑之前先查解释器依赖，缺了就先喊出来。

    为什么：openpyxl 只装在部分解释器里，缺它时 to_excel/selftest_rtm 会报
    ModuleNotFoundError，看起来像"脚本写错了"，实际只是换了个 python 跑。
    环境问题伪装成代码问题，会让人去改本来没坏的代码。
    """
    warn = []
    try:
        import openpyxl  # noqa: F401
    except ImportError:
        warn.append(("openpyxl 不可用", "to_excel / selftest_rtm 会失败（模块导入错误），"
                                      "这不是脚本 bug。请换含 openpyxl 的解释器重跑"))
    return warn


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    keyword = args[0] if args else None
    tests = find_tests(keyword)

    if "--list" in sys.argv:
        for fn, _ in tests:
            print(fn)
        return 0
    if not tests:
        print(f"[错误] 没有匹配的回归脚本（keyword={keyword!r}）", file=sys.stderr)
        return 2

    print(f"技能目录: {SKILL}")
    print(f"解释器: {sys.executable}")
    print(f"用例文件: {len(tests)}\n")

    warns = preflight()
    if warns:
        print("[!] 环境预检未通过，以下失败可能与代码无关：")
        for name, why in warns:
            print(f"    - {name}：{why}")
        print()

    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    env.setdefault("TC_SKILL", SKILL)

    total_pass = total_fail = 0
    failed_files = []
    for fn, path in tests:
        r = subprocess.run([sys.executable, path], capture_output=True,
                           text=True, encoding="utf-8", errors="replace", env=env)
        out = r.stdout + r.stderr
        # 「FAIL = 0」是 selftest_rtm 的汇总行，不是失败行；用负向前瞻排掉
        n_pass = sum(1 for l in out.split("\n") if re.match(r"^PASS\b", l))
        n_fail = sum(1 for l in out.split("\n") if re.match(r"^FAIL(?!\s*=)", l))
        # 有些脚本用"通过 N/M"汇总格式，没有逐条 PASS 行
        if n_pass == 0 and n_fail == 0:
            n_pass = 1 if r.returncode == 0 else 0
            n_fail = 0 if r.returncode == 0 else 1
        # 非 0 退出但没打出 FAIL 行 → 脚本崩了（traceback / 断言异常）。
        # 不补这一条就会出现"合计全部通过 + 失败文件: [...]"这种自相矛盾的汇总。
        if r.returncode != 0 and n_fail == 0:
            n_fail = 1
        total_pass += n_pass
        total_fail += n_fail
        flag = "OK  " if r.returncode == 0 else "FAIL"
        print(f"[{flag}] {fn:32s} pass={n_pass:3d} fail={n_fail}")
        if r.returncode != 0:
            failed_files.append(fn)
            for l in out.split("\n"):
                if l.startswith("FAIL") or "Error" in l or "错误" in l:
                    print(f"        {l[:160]}")

    print(f"\n{'=' * 46}")
    print(f"合计 {total_pass + total_fail} 项：通过 {total_pass} / 失败 {total_fail}")
    if failed_files:
        print("失败文件:", failed_files)
        if warns:
            print(f"[!] 注意：本次有环境预检告警（{', '.join(n for n, _ in warns)}），"
                  "先换解释器复跑排除环境因素，再改代码")
        return 1
    print("全部通过")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception:
        import traceback
        print("\n[内部错误] run_all.py 自身崩溃（exit 3）", file=sys.stderr)
        traceback.print_exc()
        sys.exit(3)
