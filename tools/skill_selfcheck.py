"""skill_selfcheck.py — testcase-generator 整体自检器（一致性 + 完整性）

为什么要有它：技能由 20 篇 references + 18 个 script 组成，改一处口径就要同步多处，
人工核对必然漏。本脚本把"能不能自洽"变成可复跑的检查，覆盖：

  A 引用完整性     文档里提到的 references/*.md 与 scripts/*.py 是否真实存在
  B 索引完整性     每个 references/*.md 是否在 SKILL.md 资源清单中被索引
  C 计数一致性     README 声称的篇数/脚本数是否与实际文件数一致
  D 预审项数       脚本 description 的项数 == quality_prescreen.md 标题项数 == SKILL.md 声明项数
  E 规则数一致     matrix_lint.py 实际规则代号数 == 文档声明数
  F CLI 参数存在   文档中针对各脚本写的 --参数 是否真在脚本 argparse 里
  G 闸门数量       workflow.md 闸门表行数 == 文中"N 道闸门"
  H 报告节数       analysis_gate.md 模板节数 == 文中声明节数
  I 版本单调       CHANGELOG 版本号是否递减
  J 口径冲突       出现 P4、"≤20 字"、预审旧项数(9/10/13 项) 等过期表述
  K 术语/路径      技能内是否残留绝对路径或旧仓库名
  L 编号连续性     SKILL.md 排障速查条目编号是否 1..N 不重不复
  M 字段契约       消费 cases.json 的脚本是否同时认 name 与 title
  N 规则数一致     文档声称 L1–LX 时 matrix_lint.py 是否真有 L1..LX

用法：python tools/skill_selfcheck.py [-o 报告.md] [--json] [-v] [--skill 技能目录]
  TC_REPO / TC_SKILL 可覆盖仓库根与技能目录，便于在任意克隆里跑。
  --skill 指向**同一技能的另一份副本**（仓库克隆 / 临时目录），不是"检任意技能"；
          指错目录会直接报错退出 2，不做半套检查。
退出码：0 全通过（可能有提示）｜1 存在 ERROR｜2 路径/参数错误
"""
import argparse
import io
import json
import os
import re
import sys

# 路径无关：脚本放在 <repo>/tools/ 下，仓库根即其上级目录。
# --skill 用于指向同一技能的另一份副本（仓库克隆 / 临时目录），不写死本机路径。
_HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.environ.get("TC_REPO") or os.path.dirname(_HERE)
SKILL = os.environ.get("TC_SKILL") or os.path.join(REPO, "testcase-generator")

issues = []   # (level, cat, msg)  level: ERROR / WARN / INFO


def add(level, cat, msg):
    issues.append((level, cat, msg))


def read(p):
    with io.open(p, encoding="utf-8") as f:
        return f.read()


def md_files(root):
    d = os.path.join(root, "references")
    return sorted(f for f in os.listdir(d) if f.endswith(".md")) if os.path.isdir(d) else []


def py_files(root):
    d = os.path.join(root, "scripts")
    return sorted(f for f in os.listdir(d) if f.endswith(".py")) if os.path.isdir(d) else []


def all_docs(root):
    out = [os.path.join(root, n) for n in ("SKILL.md", "README.md", "README.en.md")]
    for n in md_files(root):
        out.append(os.path.join(root, "references", n))
    return [p for p in out if os.path.exists(p)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skill", help="被测技能目录（默认内置 testcase-generator 路径）")
    ap.add_argument("-o", "--output")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    global SKILL
    if args.skill:
        SKILL = os.path.abspath(args.skill)

    if not os.path.isdir(SKILL):
        print(f"[错误] 技能目录不存在: {SKILL}", file=sys.stderr)
        return 2

    # 本自检器的检查项（D 预审项数 / E 矩阵规则 / H 报告节数 …）全部针对
    # testcase-generator 的文件结构写死。--skill 的用途是「指向同一技能的另一份
    # 副本」（仓库克隆 / 临时目录），不是「检任意技能」。
    # 指错目录时不能裸崩：那会把"你没有这个文件"报成"自检器崩了"，退出码还是 1。
    must_have = [os.path.join("scripts", "prescreen.py"),
                 os.path.join("references", "quality_prescreen.md")]
    missing = [m for m in must_have if not os.path.exists(os.path.join(SKILL, m))]
    if missing:
        print(f"[错误] {SKILL} 不是 testcase-generator 技能目录（缺 {missing}）。",
              file=sys.stderr)
        print("       --skill 只用于指向同一技能的另一份副本，不能用来检其他技能。",
              file=sys.stderr)
        return 2

    docs = all_docs(SKILL)
    refs, scripts = md_files(SKILL), py_files(SKILL)
    corpus = {p: read(p) for p in docs}
    joined = "\n".join(corpus.values())

    # ---------- A 引用完整性 ----------
    for p, text in corpus.items():
        base = os.path.basename(p)
        for rel in set(re.findall(r"(?:references|scripts)/[A-Za-z0-9_\-]+\.(?:md|py)", text)):
            if not os.path.exists(os.path.join(SKILL, rel)):
                add("ERROR", "A 引用完整性", f"{base} 引用了不存在的文件 `{rel}`")

    # ---------- B 索引完整性 ----------
    skill_md = corpus.get(os.path.join(SKILL, "SKILL.md"), "")
    for f in refs:
        if f not in skill_md:
            add("WARN", "B 索引完整性", f"`references/{f}` 未出现在 SKILL.md 的资源清单中")
    for f in scripts:
        if f not in skill_md:
            add("WARN", "B 索引完整性", f"`scripts/{f}` 未出现在 SKILL.md 的资源清单中")

    # ---------- C 计数一致性 ----------
    readme = corpus.get(os.path.join(SKILL, "README.md"), "")
    readme_en = corpus.get(os.path.join(SKILL, "README.en.md"), "")
    m = re.search(r"references/\s+#[^\n]*?（(\d+)\s*篇", readme)
    if m and int(m.group(1)) != len(refs):
        add("ERROR", "C 计数一致性", f"README 声称 references {m.group(1)} 篇，实际 {len(refs)} 篇")
    m = re.search(r"scripts/\s+#[^\n]*?（(\d+)\s*个", readme)
    if m and int(m.group(1)) != len(scripts):
        add("ERROR", "C 计数一致性", f"README 声称 scripts {m.group(1)} 个，实际 {len(scripts)} 个")
    m = re.search(r"references/\s+#[^\n]*?\((\d+)\s*files", readme_en)
    if m and int(m.group(1)) != len(refs):
        add("ERROR", "C 计数一致性", f"README.en 声称 references {m.group(1)} files，实际 {len(refs)}")
    m = re.search(r"scripts/\s+#[^\n]*?\((\d+),", readme_en)
    if m and int(m.group(1)) != len(scripts):
        add("ERROR", "C 计数一致性", f"README.en 声称 scripts {m.group(1)}，实际 {len(scripts)}")

    # ---------- D 预审项数 ----------
    pre_src = read(os.path.join(SKILL, "scripts", "prescreen.py"))
    m = re.search(r"description=\"[^\"]*?（(\d+)\s*项", pre_src)
    pre_n = int(m.group(1)) if m else None
    qp = corpus.get(os.path.join(SKILL, "references", "quality_prescreen.md"), "")
    m = re.search(r"##\s*(\d+)\s*项检查", qp)
    qp_n = int(m.group(1)) if m else None
    m = re.search(r"共\s*\*\*(\d+)\s*项\*\*", skill_md)
    sk_n = int(m.group(1)) if m else None
    vals = {"prescreen.py": pre_n, "quality_prescreen.md": qp_n, "SKILL.md": sk_n}
    if len({v for v in vals.values() if v}) > 1:
        add("ERROR", "D 预审项数", f"三处口径不一致: {vals}")

    # ---------- E 规则数一致 ----------
    ml_src = read(os.path.join(SKILL, "scripts", "matrix_lint.py"))
    codes = set(re.findall(r"\(\"(?:block|warn)\",\s*\"(L\d+b?)\"", ml_src))
    ml_docs = re.findall(r"lint\s*(\d+)\s*项|(\d+)\s*项规则", joined)
    claimed = {int(a or b) for a, b in ml_docs if (a or b)} if ml_docs else set()
    if not codes:
        add("WARN", "E 规则数一致", "未能从 matrix_lint.py 提取规则代号（代码结构变了？）")
    if claimed and len(codes) not in claimed:
        add("ERROR", "E 规则数一致",
            f"matrix_lint.py 实际规则代号 {len(codes)} 个（{sorted(codes)}），文档声明 {sorted(claimed)}")

    # ---------- F CLI 参数存在性 ----------
    script_args = {}
    for f in scripts:
        src = read(os.path.join(SKILL, "scripts", f))
        script_args[f] = set(re.findall(r'add_argument\(\s*"(--[A-Za-z0-9\-]+)"', src))
    # 只在"成对出现"的段落里校验：文档里 `脚本名 ... --参数`
    for p, text in corpus.items():
        base = os.path.basename(p)
        for m in re.finditer(r"([a-z_]+\.py)([^\n`]{0,400})", text):
            script, tail = m.group(1), m.group(2)
            if script not in script_args:
                continue
            for flag in set(re.findall(r"(--[a-z0-9\-]+)", tail)):
                if flag not in script_args[script]:
                    add("ERROR", "F CLI 参数", f"{base}: `{script} {flag}` —— 该脚本无此参数")

    # ---------- G 闸门数量 ----------
    wf = corpus.get(os.path.join(SKILL, "references", "workflow.md"), "")
    m = re.search(r"\*\*([一二三四五六七八九十]+)道闸门", wf)
    cn_num = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8}
    claimed_gate = cn_num.get(m.group(1)) if m else None
    rows_g = re.findall(r"^\|\s*\*\*([^*]+)\*\*\s*\|\s*Step", wf, re.M)
    # "N 道闸门 + 一道事后复盘"：事后复盘（缺陷反哺）不计入闸门数
    post = [r for r in rows_g if any(k in r for k in ("缺陷反哺", "事后复盘", "defect"))]
    tbl_gate = len(rows_g) - len(post)
    if claimed_gate and tbl_gate != claimed_gate:
        add("ERROR", "G 闸门数量",
            f"workflow.md 文中说 {claimed_gate} 道闸门，表格闸门行 {tbl_gate}"
            f"（另有 {len(post)} 行事后复盘，不计入）")

    # ---------- H 报告节数 ----------
    ag = corpus.get(os.path.join(SKILL, "references", "analysis_gate.md"), "")
    tpl = re.search(r"```markdown\n(.*?)```", ag, re.S)
    if tpl:
        secs = len(re.findall(r"^##\s*\d+\.", tpl.group(1), re.M))
        m = re.search(r"报告\s*([一二三四五六七八九十]+)节", skill_md)
        claimed_sec = cn_num.get(m.group(1)) if m else None
        if claimed_sec and claimed_sec != secs:
            add("ERROR", "H 报告节数", f"analysis_gate 模板 {secs} 节，SKILL.md 声称 {claimed_sec} 节")

    # ---------- I 版本单调 ----------
    clog = os.path.join(REPO, "CHANGELOG.md")
    if os.path.exists(clog):
        vers = re.findall(r"^## \[(\d+)\.(\d+)\.(\d+)\]", read(clog), re.M)
        nums = [tuple(int(x) for x in v) for v in vers]
        if nums != sorted(nums, reverse=True):
            add("ERROR", "I 版本单调", f"CHANGELOG 版本未递减: {['.'.join(map(str, v)) for v in nums[:6]]}")
        dup = [v for v in set(nums) if nums.count(v) > 1]
        if dup:
            add("ERROR", "I 版本单调", f"CHANGELOG 版本重复: {sorted(dup)}")
    else:
        add("INFO", "I 版本单调", "未找到仓库 CHANGELOG（跳过）")

    # ---------- J 口径冲突 ----------
    # P4：只有"被当作可用等级"才算冲突；"无 P4 / 不得出现 P4 / P1-P4 体系 / 实证分布含 P4" 是正常说明
    neg_ok = ("无 P4", "no P4", "不得", "禁止", "不再", "P1–P4", "P1-P4", "实证", "%")
    p4_bad = []
    for p, t in corpus.items():
        for line in t.splitlines():
            if re.search(r"\bP4\b|P0[–-]P4", line) and not any(k in line for k in neg_ok):
                p4_bad.append((os.path.basename(p), line.strip()[:70]))
    if p4_bad:
        add("ERROR", "J 口径冲突", f"P4 被当作可用等级: {p4_bad[:5]}")
    if "≤20 字" in joined or "≤ 20 字" in joined:
        hits = [os.path.basename(p) for p, t in corpus.items() if "≤20 字" in t or "≤ 20 字" in t]
        add("ERROR", "J 口径冲突", f"标题长度口径冲突（权威为 ≤30 字）: {hits}")
    for old in ("预审 9 项", "预审 10 项", "（9 项）", "（10 项）", "9 项检查", "10 项检查"):
        if old in joined:
            hits = [os.path.basename(p) for p, t in corpus.items() if old in t]
            add("ERROR", "J 口径冲突", f"残留过期预审项数表述 `{old}`: {hits}")

    # ---------- K 残留路径/旧名 ----------
    for p, t in corpus.items():
        base = os.path.basename(p)
        for bad in ("/Users/", "C:/Users/", "songgeluobo123/Skills", "ima_upload"):
            if bad in t:
                add("WARN", "K 残留", f"{base} 含 `{bad}`（技能文档不应带本机路径/旧仓库名）")

    # ---------- L 章节内编号连续性（SKILL.md 速查条目的编号必须 1..N 不重不复） ----------
    skill_md = corpus.get(os.path.join(SKILL, "SKILL.md")) or read(os.path.join(SKILL, "SKILL.md"))
    if skill_md:
        nums = [int(m.group(1)) for m in
                re.finditer(r"^\*\*(\d+)\.", skill_md, re.M)]
        if nums:
            dup = sorted({n for n in nums if nums.count(n) > 1})
            if dup:
                add("ERROR", "L 编号连续性",
                    f"SKILL.md 排障速查条目编号重复: {dup}（应连续 1..{len(nums)}，"
                    f"重复说明早期新增时没重排后续编号）")
            gaps = [n for n in range(1, max(nums) + 1) if n not in nums]
            if gaps:
                add("WARN", "L 编号连续性",
                    f"SKILL.md 排障速查条目编号缺号: {gaps}")

    # ---------- M 字段契约一致性（title / name 必须全链路同口径） ----------
    # 曾经的严重缺陷：output_format 与 to_excel 用 name，prescreen/coverage_audit 只读 title
    # → 完全按规范写出的用例被判「标题为空」。这里检查每个读用例的脚本是否两者都收。
    # 只查消费 cases.json 的脚本；read_xmind.py 读的是 XMind 节点的 `title`，与本契约无关。
    CASE_READERS = ("prescreen.py", "coverage_audit.py", "to_excel.py",
                    "score_testcases.py", "map_coverage.py",
                    "mutation_audit.py", "defect_audit.py")
    for base in py_files(SKILL):
        if base not in CASE_READERS:
            continue
        t = read(os.path.join(SKILL, "scripts", base))
        has_t = '"title"' in t or "'title'" in t
        has_n = '"name"' in t or "'name'" in t
        if has_t != has_n:
            miss = "name" if has_t else "title"
            add("ERROR", "M 字段契约",
                f"{base} 只认 `{'title' if has_t else 'name'}`、不认 `{miss}`"
                f"（规范字段是 name，别名 title 必须同时兼容，否则按规范写出的用例会被误判标题为空）")

    # ---------- N 矩阵 lint 规则数一致性（文档写 L1–LX，代码里就得有 L1..LX） ----------
    ml = read(os.path.join(SKILL, "scripts", "matrix_lint.py"))
    if ml:
        code_rules = sorted({int(x) for x in re.findall(r"\bL(\d+)b?\b", ml)})
        for p, t in corpus.items():
            for m in re.finditer(r"L1\s*[–\-~]\s*L(\d+)", t):
                top = int(m.group(1))
                missing = [n for n in range(1, top + 1) if n not in code_rules]
                if missing:
                    add("ERROR", "N 规则数一致",
                        f"{os.path.basename(p)} 声称 `L1–L{top}`，但 matrix_lint.py 缺规则 {missing}")

    # ---------- 统计 ----------
    errs = [i for i in issues if i[0] == "ERROR"]
    warns = [i for i in issues if i[0] == "WARN"]
    infos = [i for i in issues if i[0] == "INFO"]

    if args.json:
        out = json.dumps({"skill": SKILL, "references": len(refs), "scripts": len(scripts),
                          "error": len(errs), "warn": len(warns),
                          "issues": [{"level": l, "cat": c, "msg": m} for l, c, m in issues]},
                         ensure_ascii=False, indent=2)
    else:
        L = ["# testcase-generator 自检报告\n",
             f"- references: {len(refs)} 篇｜scripts: {len(scripts)} 个｜被检文档: {len(docs)} 个",
             f"- 结果：**{len(errs)} ERROR / {len(warns)} WARN / {len(infos)} INFO**\n"]
        if errs:
            L.append("## 一、ERROR（必须修）\n")
            for _, c, m in errs:
                L.append(f"- `{c}` {m}")
            L.append("")
        if warns:
            L.append("## 二、WARN（建议修）\n")
            for _, c, m in warns:
                L.append(f"- `{c}` {m}")
            L.append("")
        if not errs and not warns:
            L.append("## 结论\n\n**全部一致**：引用、索引、计数、项数、规则数、CLI 参数、闸门数、版本、口径均自洽。\n")
        out = "\n".join(L)

    if args.output:
        io.open(args.output, "w", encoding="utf-8").write(out)
        print(f"[已写出] {args.output}")
        print(f"ERROR {len(errs)} / WARN {len(warns)}")
    else:
        print(out)
    return 0 if not errs else 1


if __name__ == "__main__":
    sys.exit(main())
